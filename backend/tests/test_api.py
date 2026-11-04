"""HTTP behaviour that can be checked without a database: auth, validation, limits, routing."""
import pytest

from app.core.security import create_access_token

PROTECTED = [
    ("GET", "/api/documents"),
    ("POST", "/api/documents"),
    ("GET", "/api/documents/1/entities"),
    ("GET", "/api/documents/1/graph"),
    ("POST", "/api/documents/1/chat"),
    ("GET", "/api/graph"),
]


def test_liveness(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_an_unreachable_database_without_details(client):
    response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "checks": {"database": "error"}}


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_protected_routes_require_a_token(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_tokens_in_the_query_string_are_ignored(client, method, path):
    response = client.request(method, f"{path}?token={create_access_token(1)}")
    assert response.status_code == 401


@pytest.mark.parametrize("header", ["Bearer not-a-jwt", "Bearer ", "Basic dXNlcjpwYXNz", "not-even-a-scheme"])
def test_malformed_authorization_headers_are_rejected(client, header):
    response = client.get("/api/documents", headers={"Authorization": header})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "password": "long-enough-password"},
        {"email": "a@documind.dev", "password": "short"},
        {"email": "a@documind.dev", "password": ""},
        {"email": "a@documind.dev", "password": "x" * 129},
        {"email": "a@documind.dev"},
    ],
)
def test_signup_validates_input(client, body):
    assert client.post("/api/auth/signup", json=body).status_code == 422


def test_login_validates_email(client):
    assert client.post("/api/auth/login", json={"email": "nope", "password": "x"}).status_code == 422


def test_oversized_upload_is_rejected_before_reading_the_body(client):
    # MAX_UPLOAD_MB is 1 in tests; the size check runs before authentication
    files = {"file": ("big.txt", b"a" * (3 * 1024 * 1024), "text/plain")}
    response = client.post("/api/documents", files=files)
    assert response.status_code == 413
    assert response.json() == {"detail": "File is larger than 1 MB"}


def test_unknown_api_routes_return_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "API route not found"}


def test_api_docs_are_hidden_by_default(client):
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/..%2f..%2freadme.md",
        "/%2e%2e/%2e%2e/readme.md",
        "/..%2f..%2fbackend%2f.env",
        "/..%2f..%2fbackend%2fapp%2fcore%2fconfig.py",
        "/assets/..%2f..%2f..%2freadme.md",
    ],
)
def test_spa_route_does_not_serve_files_outside_the_build(client, path):
    response = client.get(path)
    assert "# DocuMind" not in response.text
    assert "SECRET_KEY" not in response.text
    assert "BaseSettings" not in response.text


def test_spa_fallback_serves_the_app_for_client_side_routes(client):
    from app.main import frontend_dist

    if frontend_dist is None:
        pytest.skip("frontend/dist is not built")
    response = client.get("/library/some/page")
    assert response.status_code == 200
