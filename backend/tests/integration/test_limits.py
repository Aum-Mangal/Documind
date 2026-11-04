"""Rate limits, quotas, answer caching and logout, against a real database."""
import pytest

from app.core.config import get_settings
from tests.integration.conftest import make_user, run
from tests.integration.test_ingestion import doc_row, make_pdf, upload


@pytest.fixture
def settings():
    return get_settings()


def test_login_is_limited_per_email(api, settings, monkeypatch):
    make_user(api, "target@documind.dev")  # its own sign-in counts as the first attempt
    monkeypatch.setattr(settings, "login_per_email_per_15min", 4)
    wrong = {"email": "target@documind.dev", "password": "guess"}
    assert [api.post("/api/auth/login", json=wrong).status_code for _ in range(3)] == [401, 401, 401]
    blocked = api.post("/api/auth/login", json=wrong)
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    # Even the right password waits out the window, or guessing would still pay off
    assert api.post("/api/auth/login", json={**wrong, "password": "integration-pass"}).status_code == 429
    # Other accounts are unaffected
    make_user(api, "bystander@documind.dev")


def test_signup_is_limited_per_network(api, settings, monkeypatch):
    monkeypatch.setattr(settings, "signup_per_hour", 2)
    codes = [api.post("/api/auth/signup", json={"email": f"u{i}@documind.dev", "password": "long-enough-1"}).status_code
             for i in range(3)]
    assert codes == [200, 200, 429]


def test_chat_is_limited_per_user(api, worker, settings, monkeypatch):
    headers = make_user(api)
    upload(api, headers)
    run(worker.run_until_idle())
    monkeypatch.setattr(settings, "chat_per_minute", 2)
    codes = [api.post("/api/chat", headers=headers, json={"question": f"Who leads Porto? ({i})"}).status_code
             for i in range(3)]
    assert codes == [200, 200, 429]


def test_daily_ai_allowance(api, worker, settings, monkeypatch, llm):
    headers = make_user(api)
    upload(api, headers)
    run(worker.run_until_idle())  # relation extraction and the summary each cost 120 tokens with the fake LLM

    me = api.get("/api/auth/me", headers=headers).json()
    used = me["usage"]["ai_tokens_today"]["used"]
    assert used > 0 and used % 120 == 0

    # Allow exactly one more answer (120 tokens)
    monkeypatch.setattr(settings, "daily_token_quota", used + 100)
    ask = lambda q: api.post("/api/chat", headers=headers, json={"question": q})  # noqa: E731
    assert ask("Who was appointed chief operating officer?").status_code == 200
    refused = ask("Why was the Atlas launch delayed?")
    assert refused.status_code == 429 and "allowance" in refused.json()["detail"]
    assert api.get("/api/auth/me", headers=headers).json()["usage"]["ai_tokens_today"]["used"] == used + 120


def test_summaries_are_skipped_once_the_allowance_is_used(api, worker, session_factory, settings, monkeypatch):
    headers = make_user(api)
    monkeypatch.setattr(settings, "daily_token_quota", 1)
    upload(api, headers)
    doc_id = upload(api, headers, "second.pdf", make_pdf(["A second report about the Porto office. " * 8])).json()["document"]["id"]
    run(worker.run_until_idle())
    doc = doc_row(session_factory, doc_id)
    assert doc.status == "ready" and doc.summary is None  # still searchable, just unsummarised


def test_repeated_questions_are_answered_from_the_cache(api, worker, llm):
    headers = make_user(api)
    upload(api, headers)
    run(worker.run_until_idle())

    question = {"question": "Who was appointed chief operating officer?"}
    first = api.post("/api/chat", headers=headers, json=question).json()
    calls = len(llm.calls)
    second = api.post("/api/chat", headers=headers, json={"question": "  who WAS appointed chief operating officer? "}).json()
    assert (first["cached"], second["cached"]) == (False, True)
    assert second["message"]["content"] == first["message"]["content"]
    assert second["message"]["sources"] == first["message"]["sources"]
    assert len(llm.calls) == calls  # no model call
    # Still saved as its own conversation
    assert second["conversation"]["id"] != first["conversation"]["id"]

    # A new document changes what could be found, so the cached answer no longer applies
    upload(api, headers, "new.pdf", make_pdf(["Maria Okafor previously ran the Lisbon office. " * 6]))
    run(worker.run_until_idle())
    third = api.post("/api/chat", headers=headers, json=question).json()
    assert third["cached"] is False


def test_follow_ups_are_never_served_from_the_cache(api, worker):
    headers = make_user(api)
    upload(api, headers)
    run(worker.run_until_idle())
    first = api.post("/api/chat", headers=headers, json={"question": "Tell me about Atlas."}).json()
    follow = {"question": "Tell me about Atlas.", "conversation_id": first["conversation"]["id"]}
    assert api.post("/api/chat", headers=headers, json=follow).json()["cached"] is False


def test_document_count_and_storage_quotas(api, settings, monkeypatch):
    headers = make_user(api)
    monkeypatch.setattr(settings, "max_documents_per_user", 1)
    assert upload(api, headers).status_code == 202
    refused = upload(api, headers, "another.pdf", make_pdf(["Different content entirely. " * 5]))
    assert refused.status_code == 403 and "limit of 1 documents" in refused.json()["detail"]

    monkeypatch.setattr(settings, "max_documents_per_user", 100)
    monkeypatch.setattr(settings, "max_storage_mb_per_user", 0)  # 0 disables
    assert upload(api, headers, "third.pdf", make_pdf(["Yet more content. " * 5])).status_code == 202


def test_uploads_are_rate_limited_per_user(api, settings, monkeypatch):
    headers = make_user(api)
    monkeypatch.setattr(settings, "upload_per_hour", 2)
    codes = [upload(api, headers, f"f{i}.pdf", make_pdf([f"File number {i}. " * 10])).status_code for i in range(3)]
    assert codes == [202, 202, 429]


def test_logout_revokes_only_that_token(api):
    make_user(api, "two-devices@documind.dev")
    login = lambda: api.post("/api/auth/login", json={"email": "two-devices@documind.dev", "password": "integration-pass"})  # noqa: E731
    laptop = {"Authorization": f"Bearer {login().json()['access_token']}"}
    phone = {"Authorization": f"Bearer {login().json()['access_token']}"}
    assert api.post("/api/auth/logout", headers=laptop).status_code == 204
    assert api.get("/api/documents", headers=laptop).status_code == 401
    assert api.get("/api/documents", headers=phone).status_code == 200


def test_me_reports_usage(api):
    headers = make_user(api)
    upload(api, headers)
    me = api.get("/api/auth/me", headers=headers).json()
    assert me["email"] == "reader@documind.dev"
    assert me["usage"]["documents"] == {"used": 1, "limit": 200}
    assert me["usage"]["storage_bytes"]["used"] > 0
