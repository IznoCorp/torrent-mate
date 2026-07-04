"""Tests for the version route (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.5.

.. note::

    As of phase 2.2 the ``/api/version`` endpoint is behind the auth guard
    (see §4.4).  These tests do not authenticate, so they expect 401.
    Full content tests will be added in 2.4's auth-aware integration suite.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestVersionRoute:
    """Version endpoint is guarded (require_session) — 401 without auth."""

    def test_returns_401_when_unauthenticated(self, web_app: TestClient) -> None:
        """GET /api/version returns 401 without a valid session cookie."""
        response = web_app.get("/api/version")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_version_content_requires_auth(self, web_app: TestClient) -> None:
        """The version endpoint rejects unauthenticated requests (guard functional)."""
        response = web_app.get("/api/version")
        assert response.status_code == 401

    def test_build_commit_endpoint_gated(self, web_app: TestClient) -> None:
        """BUILD_COMMIT reading is unreachable without authentication."""
        response = web_app.get("/api/version")
        assert response.status_code == 401
