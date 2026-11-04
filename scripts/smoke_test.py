"""End-to-end smoke test against a running DocuMind stack (e.g. `docker compose up`).

    python scripts/smoke_test.py --base http://127.0.0.1:8000 --secret-key "$SECRET_KEY"

Uses only the standard library plus PyJWT (to forge tokens the server must reject).
Creates two throwaway accounts; run it against a local or CI stack, never production.
"""
import argparse
import datetime as dt
import json
import re
import socket
import sys
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit

import jwt

CRLF = "\r\n"


class Smoke:
    def __init__(self, base: str, secret_key: str):
        self.base = base.rstrip("/")
        parts = urlsplit(self.base)
        self.host, self.port = parts.hostname, parts.port or 80
        self.key = secret_key
        self.results: list[bool] = []

    def check(self, name, cond, info=""):
        self.results.append(bool(cond))
        print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info and not cond else ""))

    def raw(self, request: str) -> tuple[int, bytes]:
        """Send bytes exactly as given, so paths like /../ reach the server unnormalised."""
        with socket.create_connection((self.host, self.port), timeout=15) as s:
            s.sendall(request.encode())
            data = b""
            while chunk := s.recv(65536):
                data += chunk
                if request.startswith("POST") and data:
                    break
        head, _, body = data.partition(b"\r\n\r\n")
        return int(head.split()[1]), body

    def get_raw(self, path):
        return self.raw(f"GET {path} HTTP/1.1{CRLF}Host: x{CRLF}Connection: close{CRLF}{CRLF}")

    def call(self, method, path, body=None, headers=None, raw_body=None):
        h = dict(headers or {})
        data = raw_body
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            text = e.read()
            try:
                return e.code, json.loads(text)
            except ValueError:
                return e.code, text[:120]

    def upload(self, name, content, token):
        b = uuid.uuid4().hex
        body = (
            f"--{b}{CRLF}Content-Disposition: form-data; name=\"file\"; filename=\"{name}\"{CRLF}"
            f"Content-Type: application/octet-stream{CRLF}{CRLF}"
        ).encode() + content + f"{CRLF}--{b}--{CRLF}".encode()
        return self.call("POST", "/api/documents", raw_body=body, headers={
            "Content-Type": f"multipart/form-data; boundary={b}", "Authorization": f"Bearer {token}",
        })

    def login(self, email, password):
        self.call("POST", "/api/auth/signup", {"email": email, "password": password})
        status, res = self.call("POST", "/api/auth/login", {"email": email, "password": password})
        return status, res

    def run(self) -> bool:
        check = self.check

        # Health
        st, res = self.call("GET", "/api/health/ready")
        check("readiness: database, redis and storage all ok",
              st == 200 and res.get("checks") == {"database": "ok", "redis": "ok", "storage": "ok"}, f"{st} {res}")

        # Frontend and path traversal
        st, index = self.get_raw("/")
        check("frontend is served", st == 200 and b"<div id=\"root\">" in index, st)
        asset = re.search(rb'src="(/assets/[^"]+\.js)"', index)
        check("built JS asset is served", asset and self.get_raw(asset.group(1).decode())[0] == 200)
        for p in ["/../../readme.md", "/..%2f..%2freadme.md", "/%2e%2e/%2e%2e/backend/.env", "/..%2f..%2fetc%2fpasswd"]:
            _, body = self.get_raw(p)
            check(f"traversal blocked: {p}", b"# DocuMind" not in body and b"root:" not in body and b"SECRET_KEY" not in body)
        check("API docs hidden", self.get_raw("/api/docs")[0] == 404)

        # Accounts
        email = f"smoke-{uuid.uuid4().hex[:8]}@documind.dev"
        check("signup rejects short password",
              self.call("POST", "/api/auth/signup", {"email": email, "password": "short"})[0] == 422)
        check("signup ok", self.call("POST", "/api/auth/signup", {"email": email.title(), "password": "smoke-pass-123"})[0] == 200)
        check("duplicate email in other case rejected",
              self.call("POST", "/api/auth/signup", {"email": email.upper(), "password": "smoke-pass-123"})[0] == 400)
        check("wrong password -> 401", self.call("POST", "/api/auth/login", {"email": email, "password": "nope"})[0] == 401)
        st, res = self.call("POST", "/api/auth/login", {"email": email.upper(), "password": "smoke-pass-123"})
        check("login (case-insensitive email)", st == 200 and "access_token" in res, f"{st} {res}")
        token = res["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        # Tokens
        now = dt.datetime.now(dt.UTC)
        check("no token -> 401", self.call("GET", "/api/documents")[0] == 401)
        check("token in query string ignored", self.call("GET", f"/api/documents?token={token}")[0] == 401)
        forged = jwt.encode({"sub": "1", "exp": now + dt.timedelta(hours=1)}, "x" * 40, algorithm="HS256")
        check("token signed with another key -> 401",
              self.call("GET", "/api/documents", headers={"Authorization": f"Bearer {forged}"})[0] == 401)
        expired = jwt.encode({"sub": "1", "exp": now - dt.timedelta(minutes=1)}, self.key, algorithm="HS256")
        check("expired token -> 401",
              self.call("GET", "/api/documents", headers={"Authorization": f"Bearer {expired}"})[0] == 401)

        # Uploads
        st, res = self.upload("first.txt", b"short text", token)
        check("text upload stored", st == 200 and res.get("filename") == "first.txt", f"{st} {res}")
        doc_id = res.get("document_id") if isinstance(res, dict) else None
        st, res = self.upload("../../etc/second.txt", b"another short one", token)
        check("folder path stripped from filename", st == 200 and res.get("filename") == "second.txt", f"{st} {res}")
        check("renamed file rejected", self.upload("fake.pdf", b"not a pdf", token)[0] == 400)
        check("corrupt PDF rejected cleanly", self.upload("broken.pdf", b"%PDF-1.4 garbage", token)[0] == 400)
        status, _ = self.raw(
            f"POST /api/documents HTTP/1.1{CRLF}Host: x{CRLF}Authorization: Bearer {token}{CRLF}"
            f"Content-Type: multipart/form-data; boundary=zz{CRLF}Content-Length: {500 * 1024 * 1024}{CRLF}{CRLF}"
        )
        check("500 MB upload refused before the body is sent", status == 413, status)

        # Listing and ownership
        st, docs = self.call("GET", "/api/documents", headers=auth)
        check("list shows both uploads, newest first",
              st == 200 and [d["filename"] for d in docs] == ["second.txt", "first.txt"], f"{st} {docs}")
        st, ents = self.call("GET", f"/api/documents/{doc_id}/entities", headers=auth)
        check("entities endpoint works", st == 200 and "entities" in ents, f"{st} {ents}")
        st, graph = self.call("GET", "/api/graph", headers=auth)
        check("global graph endpoint works", st == 200 and "nodes" in graph, f"{st} {graph}")

        st, res = self.login(f"other-{uuid.uuid4().hex[:8]}@documind.dev", "other-pass-123")
        other = {"Authorization": f"Bearer {res['access_token']}"}
        check("another user sees none of these documents", self.call("GET", "/api/documents", headers=other)[1] == [])
        check("another user can't open this document",
              self.call("GET", f"/api/documents/{doc_id}/entities", headers=other)[0] == 404)

        check("chat question length is limited",
              self.call("POST", f"/api/documents/{doc_id}/chat", {"question": "x" * 2001}, auth)[0] == 422)

        passed, total = sum(self.results), len(self.results)
        print(f"\n{passed}/{total} passed")
        return passed == total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--secret-key", required=True, help="the SECRET_KEY the server runs with")
    args = parser.parse_args()
    sys.exit(0 if Smoke(args.base, args.secret_key).run() else 1)
