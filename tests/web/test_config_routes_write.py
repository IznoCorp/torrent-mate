"""Route tests for the 5 config editor write endpoints (config-editor feature).

Covers ``POST /api/config/validate``, ``PUT /api/config/files/{name}``,
``GET /api/config/secrets``, ``PUT /api/config/secrets``, and
``POST /api/config/restart-web`` using a temporary copy of ``config.example/``.

Mirrors the structure of ``tests/web/test_config_routes_read.py`` for
tmp-path-based config dir provisioning and minimal app building.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import quote

import json5
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personalscraper.web.routes.config import router as config_router

#: Absolute path to the config.example template directory (repo root).
_CONFIG_EXAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "config.example"


def _build_app() -> FastAPI:
    """Build a minimal FastAPI app with only the config router mounted.

    Returns:
        A ``FastAPI`` instance with ``/api/config/*`` routes available.
    """
    app = FastAPI()
    app.include_router(config_router)
    return app


def _copy_config_example(dest_dir: Path) -> Path:
    """Copy ``config.example/`` into *dest_dir*, preserving the layout.

    Args:
        dest_dir: Directory under which the copy will be created as
            ``<dest_dir>/config/``.

    Returns:
        The absolute path to the newly created config directory.
    """
    dest = dest_dir / "config"
    shutil.copytree(_CONFIG_EXAMPLE_DIR, dest)
    return dest


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provision a temporary config dir and point ``PERSONALSCRAPER_CONFIG`` at it.

    Copies ``config.example/`` into ``tmp_path/config/`` and sets the env var
    so :func:`resolve_config_path` discovers it at request time.

    Args:
        tmp_path: Pytest temporary directory (unique per test).
        monkeypatch: Pytest environment patcher.

    Returns:
        Absolute path to the temporary config directory.
    """
    dest = _copy_config_example(tmp_path)
    monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(dest))
    return dest


@pytest.fixture
def client(config_dir: Path) -> TestClient:
    """Build a ``TestClient`` wrapping a minimal app with the config router.

    Args:
        config_dir: Temporary config directory (ensures the env var is set
            before the app is built).

    Returns:
        A ``TestClient`` ready for request assertions.
    """
    app = _build_app()
    client = TestClient(app)
    # On every request, the TestClient needs the X-Requested-With header
    # for mutating endpoints; we don't set it globally — each test adds it.
    return client


@pytest.fixture
def staging_client(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build a ``TestClient`` in staging (read-only) mode.

    Args:
        config_dir: Temporary config directory.
        monkeypatch: Pytest environment patcher.

    Returns:
        A ``TestClient`` with ``PERSONALSCRAPER_WEB_ROLE=staging``.
    """
    monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
    app = _build_app()
    return TestClient(app)


@pytest.fixture
def secrets_tmp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provision a tmp dir with ``.env.example`` and ``.env`` for secrets tests.

    Also creates a minimal config dir with ``config.json5`` so the config
    router can resolve the project root (``config_dir.parent``).

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest environment patcher.

    Returns:
        Absolute path to the project root (contains ``.env.example``,
        ``.env``, and ``config/``).
    """
    # Create a minimal config dir so config_dir resolves.
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json5").write_text('{\n  config_version: "0.0.0",\n  overlays: [],\n}\n', encoding="utf-8")
    monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(config_dir))

    root = tmp_path
    # Create .env.example with known keys.
    (root / ".env.example").write_text(
        "# ── API Keys ─────────────────\n"
        "TMDB_API_KEY=\n"
        "# Television DB key\n"
        "TVDB_API_KEY=somevalue\n"
        "# ── Web UI ──────────────────\n"
        "WEB_JWT_SECRET=\n",
        encoding="utf-8",
    )
    # Create .env with some keys set.
    (root / ".env").write_text(
        "TMDB_API_KEY=abc123\nTVDB_API_KEY=\n# comment line\nWEB_JWT_SECRET=\n",
        encoding="utf-8",
    )
    return root


# ── Helpers ─────────────────────────────────────────────────────────────────


def _xrw() -> dict[str, str]:
    """Return headers dict with the required ``X-Requested-With`` header.

    Returns:
        Dict with ``{"X-Requested-With": "TorrentMate"}``.
    """
    return {"X-Requested-With": "TorrentMate"}


# ── POST /validate ──────────────────────────────────────────────────────────


class TestValidateEndpoint:
    """``POST /api/config/validate`` — config validation without disk write."""

    def test_200_valid_payload_returns_warnings(self, client: TestClient, config_dir: Path) -> None:
        """A valid payload (current file values, unchanged) returns 200 with a warnings list."""
        current = json5.loads((config_dir / "paths.json5").read_text(encoding="utf-8"))
        resp = client.post(
            "/api/config/validate",
            json={"file_name": "paths.json5", "values": current},
            headers=_xrw(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data
        assert isinstance(data["warnings"], list)

    def test_422_invalid_values_with_loc_paths(self, client: TestClient) -> None:
        """Invalid values (wrong type) return 422 with structured loc paths."""
        # paths.json5 owns the "paths" key which expects a dict, not a list.
        resp = client.post(
            "/api/config/validate",
            json={"file_name": "paths.json5", "values": {"paths": [1, 2, 3]}},
            headers=_xrw(),
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, list)
        assert len(detail) >= 1
        first = detail[0]
        assert "loc" in first
        assert "msg" in first
        assert "type" in first
        assert isinstance(first["loc"], list)

    def test_404_unknown_file_name(self, client: TestClient) -> None:
        """A file_name not in overlays or local.json5 returns 404."""
        resp = client.post(
            "/api/config/validate",
            json={"file_name": "nonexistent.json5", "values": {}},
            headers=_xrw(),
        )
        assert resp.status_code == 404

    def test_200_valid_payload_for_known_overlay_with_owned_key(self, client: TestClient, config_dir: Path) -> None:
        """A read-modify-write payload with a key owned by the file passes validation."""
        current = json5.loads((config_dir / "paths.json5").read_text(encoding="utf-8"))
        modified = dict(current)
        modified["paths"] = {**current["paths"], "staging_dir": "/tmp/test", "data_dir": "/tmp/data"}
        resp = client.post(
            "/api/config/validate",
            json={"file_name": "paths.json5", "values": modified},
            headers=_xrw(),
        )
        assert resp.status_code == 200

    def test_422_conflict_key_owned_by_another_overlay(self, client: TestClient, config_dir: Path) -> None:
        """Validating a candidate that introduces a key owned by another overlay → 422."""
        resp = client.post(
            "/api/config/validate",
            json={
                "file_name": "scraper.json5",
                # "paths" is owned by paths.json5, not scraper.json5.
                "values": {"paths": {"staging_dir": "/tmp/conflict_test", "data_dir": "/tmp/data"}},
            },
            headers=_xrw(),
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, str)
        assert "conflict" in detail.lower() or "paths" in detail.lower()
        # Config-dir path must be stripped from the detail (SF-19).
        assert str(config_dir) not in detail

    def test_409_known_name_missing_dependency_overlay(self, client: TestClient, config_dir: Path) -> None:
        """Validate with a known name but another declared overlay missing → 409."""
        # Remove paths.json5 from disk.  web.json5 is still a valid name,
        # but paths.json5 (declared in the overlays array) is now missing.
        (config_dir / "paths.json5").unlink()
        resp = client.post(
            "/api/config/validate",
            json={"file_name": "web.json5", "values": {"web": {"port": 8080}}},
            headers=_xrw(),
        )
        assert resp.status_code == 409


# ── PUT /files/{name} ───────────────────────────────────────────────────────


class TestPutFileEndpoint:
    """``PUT /api/config/files/{name}`` — atomic file write with backup."""

    def test_403_staging_role(self, staging_client: TestClient) -> None:
        """Staging mode returns 403 on put file."""
        resp = staging_client.put(
            "/api/config/files/paths.json5",
            json={"values": {}, "base_sha256": "0000"},
            headers=_xrw(),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "read-only"

    def test_404_unknown_name(self, client: TestClient) -> None:
        """A non-writable filename (e.g. config.json5) returns 404."""
        resp = client.put(
            "/api/config/files/config.json5",
            json={"values": {}, "base_sha256": ""},
            headers=_xrw(),
        )
        assert resp.status_code == 404

    def test_412_stale_hash(self, client: TestClient, config_dir: Path) -> None:
        """A base_sha256 mismatch returns 412."""
        resp = client.put(
            "/api/config/files/paths.json5",
            json={"values": {}, "base_sha256": "0000000000000000000000000000000000000000000000000000000000000000"},
            headers=_xrw(),
        )
        assert resp.status_code == 412

    def test_200_happy_path_with_backup_and_rewrite(self, client: TestClient, config_dir: Path) -> None:
        """Full happy path: file rewritten, backup created, sha256 changes."""
        file_path = config_dir / "paths.json5"
        original_bytes = file_path.read_bytes()
        original_sha256 = hashlib.sha256(original_bytes).hexdigest()

        current = json5.loads(original_bytes.decode("utf-8"))
        new_values = dict(current)
        new_values["paths"] = {**current["paths"], "staging_dir": "/tmp/test", "data_dir": "/tmp/data"}
        resp = client.put(
            "/api/config/files/paths.json5",
            json={"values": new_values, "base_sha256": original_sha256},
            headers=_xrw(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data
        assert "restart_required" in data

        # File was rewritten.
        new_bytes = file_path.read_bytes()
        assert new_bytes != original_bytes

        # Header comment is present.
        text = new_bytes.decode("utf-8")
        assert text.startswith("// Written by TorrentMate config editor")

        # Values round-trip through json5.load.
        stripped = text.split("\n", 1)[1]  # remove header line
        parsed = json5.loads(stripped)
        assert parsed == new_values

        # Backup file was created.
        backup_dir = config_dir / ".backups"
        backups = list(backup_dir.glob("paths.json5.*.json5"))
        assert len(backups) == 1
        assert backups[0].read_bytes() == original_bytes

    def test_422_invalid_values_no_backup_created(self, client: TestClient, config_dir: Path) -> None:
        """Invalid values return 422 and leave the file untouched, no backup."""
        file_path = config_dir / "paths.json5"
        original_bytes = file_path.read_bytes()
        current_sha256 = hashlib.sha256(original_bytes).hexdigest()

        resp = client.put(
            "/api/config/files/paths.json5",
            json={
                "values": {"paths": [1, 2, 3]},  # wrong type
                "base_sha256": current_sha256,
            },
            headers=_xrw(),
        )
        assert resp.status_code == 422

        # File bytes are identical — untouched.
        assert file_path.read_bytes() == original_bytes

        # No backup was created.
        backup_dir = config_dir / ".backups"
        assert not backup_dir.exists() or len(list(backup_dir.glob("paths.json5.*.json5"))) == 0

    def test_backup_prune_keeps_10(self, client: TestClient, config_dir: Path) -> None:
        """Backup pruning keeps at most 10 backups per file name."""
        file_path = config_dir / "paths.json5"

        # Write 12 times — each write creates a backup.
        for i in range(12):
            file_bytes = file_path.read_bytes()
            text = file_bytes.decode("utf-8")
            # Strip the generated header comment line on rewritten files.
            current = json5.loads(text.split("\n", 1)[1] if text.startswith("//") else text)
            new_values = dict(current)
            new_values["paths"] = {**current["paths"], "staging_dir": f"/tmp/test_{i}"}
            current_sha256 = hashlib.sha256(file_bytes).hexdigest()
            resp = client.put(
                "/api/config/files/paths.json5",
                json={"values": new_values, "base_sha256": current_sha256},
                headers=_xrw(),
            )
            assert resp.status_code == 200

        backup_dir = config_dir / ".backups"
        backups = sorted(backup_dir.glob("paths.json5.*.json5"))
        assert len(backups) == 10

        # First backup (earliest) should be pruned.
        # All remaining backups should be valid files.
        for b in backups:
            assert b.stat().st_size > 0

    def test_restart_required_true_for_web_edit(self, client: TestClient, config_dir: Path) -> None:
        """Editing web.json5 sets restart_required=True."""
        file_path = config_dir / "web.json5"
        current_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()

        # Read current values to construct a valid payload.
        original = json5.loads(file_path.read_text(encoding="utf-8"))
        web_values = original.get("web", {})
        # Modify a safe field.
        updated_web = dict(web_values)
        # Use a minimal dict that's valid for web.json5.
        resp = client.put(
            "/api/config/files/web.json5",
            json={"values": {"web": updated_web}, "base_sha256": current_sha256},
            headers=_xrw(),
        )
        assert resp.status_code == 200
        assert resp.json()["restart_required"] is True

    def test_restart_required_false_for_scraper_edit(self, client: TestClient, config_dir: Path) -> None:
        """Editing scraper.json5 sets restart_required=False."""
        file_path = config_dir / "scraper.json5"
        current_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()

        original = json5.loads(file_path.read_text(encoding="utf-8"))
        scraper_values = original.get("scraper", {})
        updated_scraper = dict(scraper_values)

        resp = client.put(
            "/api/config/files/scraper.json5",
            json={
                "values": {"scraper": updated_scraper},
                "base_sha256": current_sha256,
            },
            headers=_xrw(),
        )
        assert resp.status_code == 200
        assert resp.json()["restart_required"] is False

    def test_422_conflict_key_owned_by_another_overlay(self, client: TestClient, config_dir: Path) -> None:
        """PUT with a candidate introducing a key owned by another overlay → 422."""
        file_path = config_dir / "scraper.json5"
        current_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()

        resp = client.put(
            "/api/config/files/scraper.json5",
            json={
                # "paths" is owned by paths.json5, not scraper.json5.
                "values": {"paths": {"staging_dir": "/tmp/conflict_put", "data_dir": "/tmp/data"}},
                "base_sha256": current_sha256,
            },
            headers=_xrw(),
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert isinstance(detail, str)
        assert "conflict" in detail.lower() or "paths" in detail.lower()
        # Config-dir path must be stripped from the detail (SF-19).
        assert str(config_dir) not in detail

    def test_new_local_json5_created_with_empty_base(self, client: TestClient, config_dir: Path) -> None:
        """PUT with base_sha256="" creates local.json5 when it doesn't exist."""
        local_path = config_dir / "local.json5"
        assert not local_path.exists()

        # The local.json5 file should contain only keys that are valid config
        # fields. We use an empty dict (no keys owned by local.json5).
        resp = client.put(
            "/api/config/files/local.json5",
            json={"values": {}, "base_sha256": ""},
            headers=_xrw(),
        )
        assert resp.status_code == 200

        # File was created.
        assert local_path.is_file()
        text = local_path.read_text(encoding="utf-8")
        assert text.startswith("// Written by TorrentMate config editor")

        # Cleanup.
        local_path.unlink()

    def test_concurrent_put_with_same_sha_one_succeeds_one_412(
        self, client: TestClient, config_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two concurrent PUTs with the same valid sha: exactly one 200 + one 412.

        Patches ``validate_candidate`` with a 0.3 s sleep so the second thread
        reaches the lock while the first is still validating.  With the
        sha check inside ``_write_lock``, thread B's in-lock recheck sees the
        on-disk sha has changed → 412.  The file content matches the 200 writer.
        """
        import personalscraper.conf.loader as loader_mod
        from personalscraper.web.routes import config as config_mod

        file_path = config_dir / "paths.json5"
        original_bytes = file_path.read_bytes()
        original_sha256 = hashlib.sha256(original_bytes).hexdigest()

        current = json5.loads(original_bytes.decode("utf-8"))

        # Slow wrapper: stalls 0.3 s then delegates to the real validate_candidate.
        _real_validate = loader_mod.validate_candidate

        def _slow_validate(*args, **kwargs):
            time.sleep(0.3)
            return _real_validate(*args, **kwargs)

        monkeypatch.setattr(loader_mod, "validate_candidate", _slow_validate)
        # Also patch the reference imported by the routes module.
        monkeypatch.setattr(config_mod, "validate_candidate", _slow_validate)

        def _put(values_suffix: str) -> tuple[int, dict]:
            new_values = dict(current)
            new_values["paths"] = {**current["paths"], "staging_dir": f"/tmp/concurrent_{values_suffix}"}
            resp = client.put(
                "/api/config/files/paths.json5",
                json={"values": new_values, "base_sha256": original_sha256},
                headers=_xrw(),
            )
            return resp.status_code, new_values

        # Launch two concurrent PUTs.
        statuses: list[int] = []
        values_list: list[dict] = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_put, "A"), pool.submit(_put, "B")]
            for fut in as_completed(futures):
                code, vals = fut.result()
                statuses.append(code)
                values_list.append((code, vals))

        # Exactly one 200 and one 412.
        assert sorted(statuses) == [200, 412], f"Expected [200, 412], got {sorted(statuses)}"

        # File content matches the 200 writer's payload.
        winner_values = next(v for c, v in values_list if c == 200)
        file_text = file_path.read_text(encoding="utf-8")
        stripped = file_text.split("\n", 1)[1]  # remove header
        parsed = json5.loads(stripped)
        assert parsed == winner_values

    @pytest.mark.parametrize(
        "traversal_name",
        [
            "../x.json5",
            "/etc/passwd",
            ".backups/paths.json5.x.json5",
        ],
    )
    def test_404_path_traversal_rejected(self, client: TestClient, traversal_name: str) -> None:
        """Path traversal attempts via PUT /files/{name} are rejected with 404."""
        resp = client.put(
            f"/api/config/files/{quote(traversal_name, safe='')}",
            json={"values": {}, "base_sha256": ""},
            headers=_xrw(),
        )
        assert resp.status_code == 404


# ── GET /secrets ────────────────────────────────────────────────────────────


class TestSecretsGetEndpoint:
    """``GET /api/config/secrets`` — catalog with is_set flags, no values."""

    def test_200_returns_catalog_keys(self, secrets_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The response includes all keys from .env.example with is_set flags."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/config/secrets")
        assert resp.status_code == 200
        data = resp.json()
        secrets = data["secrets"]
        keys = {s["key"] for s in secrets}
        assert "TMDB_API_KEY" in keys
        assert "TVDB_API_KEY" in keys
        assert "WEB_JWT_SECRET" in keys

    def test_is_set_flags_correct(self, secrets_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """is_set is True for keys with non-empty values in .env, False otherwise."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/config/secrets")
        assert resp.status_code == 200
        secrets = {s["key"]: s for s in resp.json()["secrets"]}
        # TMDB_API_KEY=abc123 in .env → is_set=True.
        assert secrets["TMDB_API_KEY"]["is_set"] is True
        # TVDB_API_KEY= (empty) in .env → is_set=False.
        assert secrets["TVDB_API_KEY"]["is_set"] is False
        # WEB_JWT_SECRET= (empty) → is_set=False.
        assert secrets["WEB_JWT_SECRET"]["is_set"] is False

    def test_no_values_in_response_body(self, secrets_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The response body must never contain actual secret values."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/config/secrets")
        assert resp.status_code == 200
        body = resp.text
        # None of the .env values should appear in the response.
        assert "abc123" not in body

    def test_descriptions_from_catalog(self, secrets_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Descriptions are parsed from .env.example comment blocks."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/config/secrets")
        secrets = {s["key"]: s for s in resp.json()["secrets"]}
        # TVDB_API_KEY has a comment "Television DB key" above it.
        assert "Television DB key" in secrets["TVDB_API_KEY"]["description"]

    def test_200_empty_when_no_env_example(self, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns empty list when .env.example is absent."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/config/secrets")
        assert resp.status_code == 200
        assert resp.json()["secrets"] == []


# ── PUT /secrets ────────────────────────────────────────────────────────────


class TestSecretsPutEndpoint:
    """``PUT /api/config/secrets`` — atomic upsert with key allowlisting."""

    def test_403_staging_role(self, staging_client: TestClient) -> None:
        """Staging mode returns 403."""
        resp = staging_client.put(
            "/api/config/secrets",
            json={"TMDB_API_KEY": "secret"},
            headers=_xrw(),
        )
        assert resp.status_code == 403

    def test_200_writes_env_file(self, secrets_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid keys are written to .env via atomic upsert."""
        app = _build_app()
        client = TestClient(app)

        resp = client.put(
            "/api/config/secrets",
            json={"TMDB_API_KEY": "new_secret_value", "TVDB_API_KEY": "tvdb_secret"},
            headers=_xrw(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["restart_required"] is True

        # Verify .env was updated.
        env_content = (secrets_tmp_dir / ".env").read_text(encoding="utf-8")
        assert "TMDB_API_KEY=new_secret_value" in env_content
        assert "TVDB_API_KEY=tvdb_secret" in env_content

    def test_422_unknown_key_no_value_echo(self, secrets_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown keys → 422, value never echoed in error response."""
        app = _build_app()
        client = TestClient(app)

        resp = client.put(
            "/api/config/secrets",
            json={"UNKNOWN_KEY": "my_secret_value", "TMDB_API_KEY": "ok"},
            headers=_xrw(),
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        # Unknown key is listed.
        assert "UNKNOWN_KEY" in detail["unknown_keys"]
        # Value must NOT appear.
        body_text = resp.text
        assert "my_secret_value" not in body_text

    def test_restart_required_true(self, secrets_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The response always has restart_required=True."""
        app = _build_app()
        client = TestClient(app)

        resp = client.put(
            "/api/config/secrets",
            json={"TMDB_API_KEY": "val"},
            headers=_xrw(),
        )
        assert resp.status_code == 200
        assert resp.json()["restart_required"] is True

    def test_caplog_contains_no_secret_value(
        self,
        secrets_tmp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Log output must never contain secret values."""
        import logging

        caplog.set_level(logging.INFO)

        app = _build_app()
        client = TestClient(app)

        secret_value = "super_secret_abc_123"
        resp = client.put(
            "/api/config/secrets",
            json={"TMDB_API_KEY": secret_value},
            headers=_xrw(),
        )
        assert resp.status_code == 200

        # Collect all log output and verify no secret value.
        log_text = caplog.text
        assert secret_value not in log_text

    def test_422_newline_injection_rejected(self, secrets_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        r"""Values containing \n are rejected with 422; .env untouched, key not injected."""
        app = _build_app()
        client = TestClient(app)

        original_env = (secrets_tmp_dir / ".env").read_text(encoding="utf-8")

        resp = client.put(
            "/api/config/secrets",
            json={"TMDB_API_KEY": "safe\nWEB_PASSWORD_HASH=evil"},
            headers=_xrw(),
        )
        assert resp.status_code == 422

        # .env must be untouched — the injected key must NOT appear.
        env_after = (secrets_tmp_dir / ".env").read_text(encoding="utf-8")
        assert env_after == original_env
        assert "WEB_PASSWORD_HASH" not in env_after

    def test_422_empty_dict_no_keys_provided(self, secrets_tmp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """PUT {} → 422 'no keys provided'."""
        app = _build_app()
        client = TestClient(app)

        resp = client.put(
            "/api/config/secrets",
            json={},
            headers=_xrw(),
        )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "no keys provided"


# ── POST /restart-web ───────────────────────────────────────────────────────


class TestRestartEndpoint:
    """``POST /api/config/restart-web`` — PM2 restart scheduling."""

    def test_403_staging_role(self, staging_client: TestClient) -> None:
        """Staging mode returns 403."""
        resp = staging_client.post(
            "/api/config/restart-web",
            headers=_xrw(),
        )
        assert resp.status_code == 403

    def test_404_no_pm2_name(self, client: TestClient) -> None:
        """When PERSONALSCRAPER_PM2_NAME is unset, returns 404."""
        resp = client.post(
            "/api/config/restart-web",
            headers=_xrw(),
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "restart not configured"

    def test_202_pm2_restart_called(self, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When PERSONALSCRAPER_PM2_NAME is set, Popen is called with pm2 restart."""
        monkeypatch.setenv("PERSONALSCRAPER_PM2_NAME", "torrentmate-web")
        mock_popen = MagicMock()
        monkeypatch.setattr("personalscraper.web.routes.config.subprocess.Popen", mock_popen)
        # Also mock DEVNULL for attribute access.
        monkeypatch.setattr(
            "personalscraper.web.routes.config.subprocess.DEVNULL",
            subprocess.DEVNULL,
            raising=False,
        )

        app = _build_app()
        client = TestClient(app)

        resp = client.post(
            "/api/config/restart-web",
            headers=_xrw(),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "scheduled"

        # Popen was called.
        assert mock_popen.called
        call_args = mock_popen.call_args
        # First positional arg should be the command list.
        cmd = call_args[0][0]
        assert "pm2 restart" in " ".join(cmd)
        assert "torrentmate-web" in " ".join(cmd)
        assert "sleep 0.5" in " ".join(cmd)
        # Detached process.
        assert call_args[1].get("start_new_session") is True
