"""Tests for the version route (tm-shell feature).

See docs/features/tm-shell/DESIGN.md §4.5.

The ``/api/version`` endpoint is behind the auth guard (§4.4): one test covers
the unauthenticated 401, the rest authenticate and assert the response BODY,
including both branches of the ``BUILD_COMMIT`` file read.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import personalscraper
from personalscraper.config import Settings
from personalscraper.web.app import create_app
from personalscraper.web.auth.passwords import hash_password
from personalscraper.web.routes import version as version_module
from personalscraper.web.routes.version import _read_build_commit

# ── Test constants ──────────────────────────────────────────────────────────
TEST_USERNAME = "testuser"
TEST_PASSWORD = "test-password"
TEST_HASH = hash_password(TEST_PASSWORD)
TEST_SECRET = "version-integration-test-secret"


@pytest.fixture
def version_client(test_config) -> TestClient:
    """Create a TestClient able to authenticate, for body assertions on /api/version.

    Injects a known scrypt hash + JWT secret and uses ``https`` base_url so the
    ``Secure`` session cookie is replayed after login.

    Args:
        test_config: Synthetic ``Config`` fixture.

    Returns:
        A ``TestClient`` with ``base_url="https://testserver"``.
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


def _login(client: TestClient) -> None:
    """Log in with the known test credentials (sets the session cookie).

    Args:
        client: The version test client.
    """
    resp = client.post("/api/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert resp.status_code == 204


class TestVersionRouteGuard:
    """The endpoint is guarded — 401 without a valid session."""

    def test_returns_401_when_unauthenticated(self, web_app: TestClient) -> None:
        """GET /api/version returns 401 without a valid session cookie."""
        response = web_app.get("/api/version")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"


class TestVersionRouteBody:
    """Authenticated response body of /api/version."""

    def test_returns_version_and_build_commit(self, version_client: TestClient) -> None:
        """After login the body carries the package version and the build commit."""
        _login(version_client)
        response = version_client.get("/api/version")
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "version": personalscraper.__version__,
            "build_commit": _read_build_commit(),
        }
        assert body["version"] == personalscraper.__version__


class TestReadBuildCommit:
    """Both branches of the ``BUILD_COMMIT`` file read (§4.5)."""

    def test_reads_build_commit_file(self, tmp_path: Path, monkeypatch) -> None:
        """When ``static/BUILD_COMMIT`` exists, its stripped contents are returned.

        ``_read_build_commit`` derives the path from the module ``__file__``
        (``<root>/routes/version.py`` → ``<root>/static/BUILD_COMMIT``); pointing
        the module file into a temp tree exercises the real read path.
        """
        (tmp_path / "static").mkdir()
        (tmp_path / "static" / "BUILD_COMMIT").write_text("abc1234\n")
        monkeypatch.setattr(version_module, "__file__", str(tmp_path / "routes" / "version.py"))

        assert _read_build_commit() == "abc1234"

    def test_defaults_to_dev_when_file_absent(self, tmp_path: Path, monkeypatch) -> None:
        """When ``static/BUILD_COMMIT`` is missing, the default ``"dev"`` is returned."""
        monkeypatch.setattr(version_module, "__file__", str(tmp_path / "routes" / "version.py"))

        assert _read_build_commit() == "dev"


class TestBuildCommitCachedAtBoot:
    """R27 — the served build_commit identifies the RUNNING process's build."""

    def test_endpoint_serves_boot_value_not_disk(self, version_client: TestClient, monkeypatch) -> None:
        """A post-boot change to BUILD_COMMIT on disk must NOT change the response.

        A stale (pre-deploy) process re-reading the freshly stamped file per
        request would masquerade as the new build — deploy.sh's post-check
        relies on the boot-time cache to detect a failed pm2 restart.
        """
        _login(version_client)
        first = version_client.get("/api/version").json()["build_commit"]

        # Simulate a new deploy stamping a fresh BUILD_COMMIT while this
        # (old) process keeps running.
        monkeypatch.setattr(version_module, "_read_build_commit", lambda: "post-deploy-sha")

        second = version_client.get("/api/version").json()["build_commit"]
        assert second == first
        assert second != "post-deploy-sha"
