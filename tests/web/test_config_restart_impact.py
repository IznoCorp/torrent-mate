"""Architecture test for RESTART_IMPACT coverage + auth-guard tests.

Covers:
- Every ``Config.model_fields`` key is explicitly classified in
  ``RESTART_IMPACT`` (missing = test failure).
- ``restart_required_for("unknown_future_key")`` is ``True`` (fail-safe).
- Auth guard: config endpoints return 401 without session, 200 with session,
  using the real ``create_app`` factory (mirrors ``tests/web/test_auth.py``).
- X-Requested-With: ``PUT /api/config/files/paths.json5`` without the
  header returns 400.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.web.auth.passwords import hash_password
from personalscraper.web.routes.config import RESTART_IMPACT, restart_required_for

TEST_USERNAME = "testuser"
TEST_PASSWORD = "test-password"
TEST_HASH = hash_password(TEST_PASSWORD)
TEST_SECRET = "restart-impact-test-secret"

#: Absolute path to the config.example template directory (repo root).
_CONFIG_EXAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "config.example"


# ── RESTART_IMPACT architecture test ────────────────────────────────────────


class TestRestartImpactMap:
    """Architecture test: every Config key must be classified in RESTART_IMPACT."""

    def test_all_config_keys_classified(self) -> None:
        """Every ``Config.model_fields`` key is in ``RESTART_IMPACT``.

        A missing key means a new config section was added without updating
        the restart-impact classification — the test fails with a helpful
        message naming the missing key.
        """
        config_keys = set(Config.model_fields.keys())
        classified_keys = set(RESTART_IMPACT.keys())

        missing = config_keys - classified_keys
        assert not missing, f"New config section(s) must be classified in RESTART_IMPACT: {', '.join(sorted(missing))}"

    def test_web_paths_indexer_require_restart(self) -> None:
        """``web``, ``paths``, and ``indexer`` require a restart."""
        assert RESTART_IMPACT["web"] is True
        assert RESTART_IMPACT["paths"] is True
        assert RESTART_IMPACT["indexer"] is True

    def test_unknown_key_failsafe_defaults_true(self) -> None:
        """``restart_required_for`` returns ``True`` for unknown keys (fail-safe)."""
        assert restart_required_for("unknown_future_key") is True

    def test_no_extra_keys_in_restart_impact(self) -> None:
        """Every key in ``RESTART_IMPACT`` matches a ``Config.model_fields`` key.

        An extra key means a config section was removed but its RESTART_IMPACT
        entry was not cleaned up.
        """
        config_keys = set(Config.model_fields.keys())
        classified_keys = set(RESTART_IMPACT.keys())

        extra = classified_keys - config_keys
        assert not extra, f"Stale RESTART_IMPACT entries for removed config sections: {', '.join(sorted(extra))}"


# ── Auth-guard tests (real create_app factory) ──────────────────────────────


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provision a temporary config dir from ``config.example/``.

    Copies ``config.example/`` into ``tmp_path/config/`` and sets
    ``PERSONALSCRAPER_CONFIG`` so ``resolve_config_path`` discovers it.

    Args:
        tmp_path: Pytest temporary directory (unique per test).
        monkeypatch: Pytest environment patcher.

    Returns:
        Absolute path to the temporary config directory.
    """
    dest = tmp_path / "config"
    shutil.copytree(_CONFIG_EXAMPLE_DIR, dest)
    monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(dest))
    return dest


def _login(client: TestClient) -> None:
    """Log in and store the session cookie on *client*.

    Args:
        client: A ``TestClient`` with ``base_url="https://testserver"``.
    """
    resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 204, f"Login failed: {resp.status_code}"


class TestConfigRoutesAuthGuard:
    """Auth-guard and X-Requested-With tests for config endpoints.

    Uses the real ``create_app`` factory (mirrors ``tests/web/test_auth.py``)
    so that the config router registration in ``app.py`` is actually exercised.
    """

    def test_schema_unauthenticated_returns_401(
        self, test_config: Config, tmp_path: Path, config_dir: Path, make_web_client
    ) -> None:
        """``GET /api/config/schema`` without session → 401."""
        web_cfg = test_config.web.model_copy(update={"username": TEST_USERNAME})
        cfg = test_config.model_copy(update={"web": web_cfg})
        cfg.paths.data_dir.mkdir(parents=True, exist_ok=True)
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )
        client = make_web_client(cfg, settings)

        resp = client.get("/api/config/schema")
        assert resp.status_code == 401

    def test_schema_authenticated_returns_200(
        self, test_config: Config, tmp_path: Path, config_dir: Path, make_web_client
    ) -> None:
        """``GET /api/config/schema`` with authenticated client → 200."""
        web_cfg = test_config.web.model_copy(update={"username": TEST_USERNAME})
        cfg = test_config.model_copy(update={"web": web_cfg})
        cfg.paths.data_dir.mkdir(parents=True, exist_ok=True)
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )
        client = make_web_client(cfg, settings, https=True)
        _login(client)

        resp = client.get("/api/config/schema")
        assert resp.status_code == 200
        data = resp.json()
        assert "json_schema" in data
        assert "ownership" in data
        assert "restart_impact" in data

    def test_put_file_without_x_requested_with_returns_400(
        self, test_config: Config, tmp_path: Path, config_dir: Path, make_web_client
    ) -> None:
        """``PUT /api/config/files/paths.json5`` without X-Requested-With → 400.

        The ``require_x_requested_with`` dependency raises 400 (NOT 403) when
        the header is missing, even for an authenticated client.
        """
        web_cfg = test_config.web.model_copy(update={"username": TEST_USERNAME})
        cfg = test_config.model_copy(update={"web": web_cfg})
        cfg.paths.data_dir.mkdir(parents=True, exist_ok=True)
        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )
        client = make_web_client(cfg, settings, https=True)
        _login(client)

        # Only send the JSON body — deliberately omit X-Requested-With.
        resp = client.put(
            "/api/config/files/paths.json5",
            json={"values": {}, "base_sha256": ""},
        )
        assert resp.status_code == 400
        assert "X-Requested-With" in resp.json()["detail"]
