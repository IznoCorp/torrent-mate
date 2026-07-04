"""Integration tests for auth routes (tm-shell feature).

Uses ``TestClient`` with ``base_url="https://testserver"`` so the ``Secure``
session cookie is replayed across requests.  See
docs/features/tm-shell/plan/phase-02-auth.md §2.4.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.web.app import create_app
from personalscraper.web.auth.passwords import hash_password

# ── Test constants ──────────────────────────────────────────────────────────
TEST_USERNAME = "testuser"
TEST_PASSWORD = "test-password"
TEST_HASH = hash_password(TEST_PASSWORD)
TEST_SECRET = "auth-integration-test-secret"


@pytest.fixture
def auth_client(test_config):
    """Create a TestClient with known credentials and ``https`` base_url.

    Injects a pre-computed scrypt hash and a known JWT secret into the
    application settings so the login route can actually verify credentials
    and issue tokens.  Uses ``base_url="https://testserver"`` because the
    session cookie is set with ``Secure`` — without this the cookie is not
    replayed and ``/me`` stays 401.

    Args:
        test_config: Synthetic ``Config`` fixture.

    Returns:
        A ``TestClient`` with ``base_url="https://testserver"`` wired to an
        app carrying the known test credentials.
    """
    web_cfg = test_config.web.model_copy(update={"username": TEST_USERNAME})
    cfg = test_config.model_copy(update={"web": web_cfg})
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        web_password_hash=TEST_HASH,
        web_jwt_secret=TEST_SECRET,
    )
    app = create_app(cfg, settings)
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def auth_client_no_hash(test_config):
    """Create a TestClient with **empty** ``web_password_hash``.

    Used to verify that login always returns 401 when no password has been
    configured (the "not set up yet" guard).

    Args:
        test_config: Synthetic ``Config`` fixture.

    Returns:
        A ``TestClient`` with ``base_url="https://testserver"`` and no
        password hash configured.
    """
    web_cfg = test_config.web.model_copy(update={"username": TEST_USERNAME})
    cfg = test_config.model_copy(update={"web": web_cfg})
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        web_password_hash="",
        web_jwt_secret=TEST_SECRET,
    )
    app = create_app(cfg, settings)
    return TestClient(app, base_url="https://testserver")


class TestLoginSuccess:
    """Successful login → 204 + session cookie with correct attributes."""

    def test_login_returns_204(self, auth_client: TestClient) -> None:
        """POST /api/auth/login with correct credentials returns 204."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 204

    def test_set_cookie_present_and_httponly(self, auth_client: TestClient) -> None:
        """Set-Cookie header has HttpOnly flag."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        set_cookie = resp.headers.get("set-cookie", "")
        assert "tm_session=" in set_cookie
        assert "HttpOnly" in set_cookie or "httponly" in set_cookie

    def test_set_cookie_samesite_strict(self, auth_client: TestClient) -> None:
        """Set-Cookie header has SameSite=Strict."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        set_cookie = resp.headers.get("set-cookie", "")
        assert "SameSite=Strict" in set_cookie or "SameSite=strict" in set_cookie

    def test_set_cookie_secure(self, auth_client: TestClient) -> None:
        """Set-Cookie header has Secure flag (cookie_secure=True by default)."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        set_cookie = resp.headers.get("set-cookie", "")
        assert "Secure" in set_cookie or "secure" in set_cookie

    def test_set_cookie_path_root(self, auth_client: TestClient) -> None:
        """Set-Cookie header has Path=/."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        set_cookie = resp.headers.get("set-cookie", "")
        assert "Path=/" in set_cookie or "path=/" in set_cookie

    def test_set_cookie_has_max_age(self, auth_client: TestClient) -> None:
        """Set-Cookie header has a Max-Age attribute."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        set_cookie = resp.headers.get("set-cookie", "")
        assert "Max-Age=" in set_cookie or "max-age=" in set_cookie


class TestLoginFailure:
    """Failed login → 401, no cookie, no user enumeration."""

    def test_wrong_password_returns_401(self, auth_client: TestClient) -> None:
        """Wrong password → 401."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": "wrong-password"},
        )
        assert resp.status_code == 401

    def test_wrong_username_returns_401(self, auth_client: TestClient) -> None:
        """Wrong username (even with correct password) → 401."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": TEST_PASSWORD},
        )
        assert resp.status_code == 401

    def test_wrong_username_and_password_returns_401(self, auth_client: TestClient) -> None:
        """Both wrong → 401."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_no_set_cookie_on_failure(self, auth_client: TestClient) -> None:
        """Failed login does NOT set a session cookie."""
        resp = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": "wrong"},
        )
        assert "tm_session=" not in resp.headers.get("set-cookie", "")

    def test_no_user_enumeration_same_body(self, auth_client: TestClient) -> None:
        """Both failure kinds (wrong user, wrong password) return identical 401 bodies."""
        resp_user = auth_client.post(
            "/api/auth/login",
            json={"username": "nonexistent", "password": TEST_PASSWORD},
        )
        resp_pass = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": "wrong"},
        )
        assert resp_user.status_code == 401
        assert resp_pass.status_code == 401
        assert resp_user.json() == resp_pass.json()

    def test_empty_password_hash_always_401(self, auth_client_no_hash: TestClient) -> None:
        """When web_password_hash is empty, even correct credentials → 401."""
        resp = auth_client_no_hash.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 401


class TestMeEndpoint:
    """GET /api/auth/me — requires valid session cookie."""

    def test_me_returns_401_without_cookie(self, auth_client: TestClient) -> None:
        """Unauthenticated → 401."""
        resp = auth_client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_returns_username_with_cookie(self, auth_client: TestClient) -> None:
        """After login, /me returns 200 + {username}."""
        # Login to get the cookie.
        login_resp = auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert login_resp.status_code == 204
        # The TestClient with https base_url replays the Secure cookie.
        resp = auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json() == {"username": TEST_USERNAME}


class TestLogout:
    """POST /api/auth/logout — clears the session cookie."""

    def test_logout_returns_204(self, auth_client: TestClient) -> None:
        """Logout (with valid session) returns 204."""
        auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        resp = auth_client.post("/api/auth/logout")
        assert resp.status_code == 204

    def test_logout_clears_cookie(self, auth_client: TestClient) -> None:
        """Logout clears the tm_session cookie so /me returns 401."""
        auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        auth_client.post("/api/auth/logout")
        # After logout, /me should be 401.
        resp = auth_client.get("/api/auth/me")
        assert resp.status_code == 401


class TestGuardOnVersionRoute:
    """The /api/version route is behind the require_session guard."""

    def test_version_returns_401_without_cookie(self, auth_client: TestClient) -> None:
        """Unauthenticated → 401 on /api/version."""
        resp = auth_client.get("/api/version")
        assert resp.status_code == 401

    def test_version_returns_200_after_login(self, auth_client: TestClient) -> None:
        """After login, /api/version returns 200."""
        auth_client.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        resp = auth_client.get("/api/version")
        assert resp.status_code == 200
