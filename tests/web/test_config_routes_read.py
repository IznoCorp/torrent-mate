"""Route tests for the 4 config editor read endpoints (config-editor feature).

Covers ``GET /api/config/schema``, ``/files``, ``/files/{name}``, and
``/status`` using a temporary copy of ``config.example/``.  All endpoints
are tested against the router directly (a local ``FastAPI`` app) — router
registration in ``app.py`` is sub-phase 2.4.

Mirrors the structure of ``tests/web/test_maintenance_panels.py`` for
tmp-path-based config dir provisioning and minimal app building.  No real
``config/`` directory is required (CI-safe).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from urllib.parse import quote

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
    return TestClient(app)


# ── GET /schema ─────────────────────────────────────────────────────────────


class TestSchemaEndpoint:
    """``GET /api/config/schema`` — JSON Schema, ownership, restart impact."""

    def test_returns_200(self, client: TestClient) -> None:
        """200 — the endpoint responds successfully."""
        resp = client.get("/api/config/schema")
        assert resp.status_code == 200

    def test_json_schema_has_properties(self, client: TestClient) -> None:
        """The ``json_schema`` field includes JSON Schema ``properties``."""
        resp = client.get("/api/config/schema")
        data = resp.json()
        assert "json_schema" in data
        assert "properties" in data["json_schema"]
        # At least the top-level keys should be present as properties.
        props: dict[str, object] = data["json_schema"]["properties"]
        assert "paths" in props
        assert "web" in props
        assert "indexer" in props

    def test_ownership_maps_keys_to_files(self, client: TestClient) -> None:
        """Every top-level key maps to the filename that owns it."""
        resp = client.get("/api/config/schema")
        data = resp.json()
        ownership: dict[str, str] = data["ownership"]
        # Master-owned key.
        assert ownership.get("config_version") == "config.json5"
        # Overlay-owned keys.
        assert ownership.get("paths") == "paths.json5"
        assert ownership.get("web") == "web.json5"
        assert ownership.get("indexer") == "indexer.json5"
        assert ownership.get("disks") == "disks.json5"
        # `sort` is exposed via scraper.json5 (0.43.1 follow-up); `process_clean`
        # is intentionally NOT owned by any overlay (its verify_seed_pure flag is
        # reserved and not enforced — see ProcessCleanConfig), so it is invisible
        # to the editor by design.
        assert ownership.get("sort") == "scraper.json5"
        assert "process_clean" not in ownership
        # All values should be valid filenames (basenames, no path separators).
        for key, filename in ownership.items():
            assert "/" not in filename, f"Ownership value for {key!r} is a path, not a filename: {filename!r}"
            assert filename.endswith(".json5"), f"Ownership value for {key!r} is not a .json5 file: {filename!r}"

    def test_restart_impact_covers_web_paths_indexer_as_true(self, client: TestClient) -> None:
        """Keys that require a restart are marked ``True``."""
        resp = client.get("/api/config/schema")
        data = resp.json()
        impact: dict[str, bool] = data["restart_impact"]
        assert impact.get("web") is True
        assert impact.get("paths") is True
        assert impact.get("indexer") is True
        # Spot-check a few false keys.
        assert impact.get("disks") is False
        assert impact.get("scraper") is False


# ── GET /files ──────────────────────────────────────────────────────────────


class TestFilesEndpoint:
    """``GET /api/config/files`` — file metadata listing."""

    def test_returns_200(self, client: TestClient) -> None:
        """200 — the endpoint responds successfully."""
        resp = client.get("/api/config/files")
        assert resp.status_code == 200

    def test_one_entry_per_overlay_plus_master(self, client: TestClient) -> None:
        """Each declared overlay, plus master and optional local, has an entry."""
        resp = client.get("/api/config/files")
        data = resp.json()
        files: list[dict[str, object]] = data["files"]
        # Master + 18 overlays (from config.example) = 19 minimum.
        assert len(files) >= 19
        names = {f["name"] for f in files}
        assert "config.json5" in names
        assert "paths.json5" in names
        assert "web.json5" in names

    def test_sha256_matches_recompute(self, client: TestClient, config_dir: Path) -> None:
        """The reported SHA-256 matches an independent ``hashlib`` recompute."""
        resp = client.get("/api/config/files")
        data = resp.json()
        for f in data["files"]:
            file_path = config_dir / f["name"]
            expected = hashlib.sha256(file_path.read_bytes()).hexdigest()
            assert f["sha256"] == expected, f"SHA-256 mismatch for {f['name']}"

    def test_field_types_and_shapes(self, client: TestClient) -> None:
        """Each ``FileInfo`` entry has the expected field types and shapes."""
        resp = client.get("/api/config/files")
        data = resp.json()
        for f in data["files"]:
            assert isinstance(f["name"], str)
            assert isinstance(f["owned_keys"], list)
            assert all(isinstance(k, str) for k in f["owned_keys"])
            assert isinstance(f["sha256"], str)
            assert len(f["sha256"]) == 64  # hex-encoded SHA-256
            assert isinstance(f["mtime"], (int, float))
            assert isinstance(f["size"], int)
            assert f["size"] > 0
            assert isinstance(f["shadowed_keys"], list)


# ── GET /files/{name} ───────────────────────────────────────────────────────


class TestFileEndpoint:
    """``GET /api/config/files/{name}`` — single file content."""

    def test_returns_200_for_real_overlay(self, client: TestClient) -> None:
        """200 — a declared overlay returns its parsed values."""
        resp = client.get("/api/config/files/paths.json5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "paths.json5"
        assert "paths" in data["values"]
        assert isinstance(data["values"]["paths"], dict)
        assert len(data["sha256"]) == 64

    def test_returns_200_for_master(self, client: TestClient) -> None:
        """200 — the master config.json5 returns its parsed values."""
        resp = client.get("/api/config/files/config.json5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "config.json5"
        assert "overlays" in data["values"]
        assert "config_version" in data["values"]

    def test_returns_404_for_unknown_name(self, client: TestClient) -> None:
        """404 — a filename not in overlays, master, or local is rejected."""
        resp = client.get("/api/config/files/nonexistent.json5")
        assert resp.status_code == 404

    def test_values_contain_expected_keys(self, client: TestClient) -> None:
        """The ``values`` dict for paths.json5 contains the paths sub-object."""
        resp = client.get("/api/config/files/paths.json5")
        data = resp.json()
        values: dict[str, object] = data["values"]["paths"]
        assert "staging_dir" in values
        assert "data_dir" in values

    @pytest.mark.parametrize(
        "traversal_name",
        [
            "../x.json5",
            "/etc/passwd",
            ".backups/paths.json5.x.json5",
        ],
    )
    def test_404_path_traversal_rejected(self, client: TestClient, traversal_name: str) -> None:
        """Path traversal attempts via GET /files/{name} are rejected with 404."""
        # URL-encode to preserve path separators in the name segment.

        resp = client.get(f"/api/config/files/{quote(traversal_name, safe='')}")
        assert resp.status_code == 404

    def test_422_corrupt_json5_parse_error(self, client: TestClient, config_dir: Path) -> None:
        """GET a file with invalid JSON5 syntax → 422 with parse error detail."""
        # Corrupt an overlay file on disk.
        overlay_path = config_dir / "web.json5"
        original = overlay_path.read_text(encoding="utf-8")
        try:
            overlay_path.write_text("{ invalid json5 !!! }", encoding="utf-8")
            resp = client.get("/api/config/files/web.json5")
            assert resp.status_code == 422
            detail = resp.json()["detail"]
            assert "JSON5 parse error" in detail
        finally:
            overlay_path.write_text(original, encoding="utf-8")


# ── GET /status ─────────────────────────────────────────────────────────────


class TestStatusEndpoint:
    """``GET /api/config/status`` — role, read-only, stale detection."""

    def test_returns_200(self, client: TestClient) -> None:
        """200 — the endpoint responds successfully."""
        resp = client.get("/api/config/status")
        assert resp.status_code == 200

    def test_role_defaults_to_prod(self, client: TestClient) -> None:
        """Default role is ``"prod"`` with ``read_only=False``."""
        resp = client.get("/api/config/status")
        data = resp.json()
        assert data["role"] == "prod"
        assert data["read_only"] is False

    def test_staging_role_read_only(self, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When ``PERSONALSCRAPER_WEB_ROLE=staging``, ``read_only`` is ``True``."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/config/status")
        data = resp.json()
        assert data["role"] == "staging"
        assert data["read_only"] is True

    def test_no_stale_files_initially(self, client: TestClient) -> None:
        """Fresh boot — no stale files, no restart required."""
        resp = client.get("/api/config/status")
        data = resp.json()
        assert data["stale_files"] == []
        assert data["restart_required"] is False

    def test_stale_files_after_modification(self, client: TestClient, config_dir: Path) -> None:
        """Modifying an overlay file after boot snapshot is captured → stale."""
        # First call triggers the lazy boot snapshot.
        resp1 = client.get("/api/config/status")
        assert resp1.status_code == 200
        assert resp1.json()["stale_files"] == []

        # Modify an overlay file on disk.
        web_path = config_dir / "web.json5"
        original = web_path.read_text()
        try:
            web_path.write_text(original + "\n// test modification\n")

            # Second call should detect the change.
            resp2 = client.get("/api/config/status")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert "web.json5" in data2["stale_files"]
            assert data2["restart_required"] is True
        finally:
            # Restore the file to keep the tmp dir clean for other tests.
            web_path.write_text(original)

    def test_stale_files_empty_when_unchanged(self, client: TestClient) -> None:
        """Multiple calls without modifications → no stale files."""
        resp1 = client.get("/api/config/status")
        assert resp1.json()["stale_files"] == []

        resp2 = client.get("/api/config/status")
        assert resp2.json()["stale_files"] == []

    def test_500_when_master_config_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Status returns 500 when config.json5 is missing, not a bare traceback."""
        dest = _copy_config_example(tmp_path)
        monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(dest))
        # Delete the master config.json5.
        (dest / "config.json5").unlink()

        app = _build_app()
        client = TestClient(app)

        resp = client.get("/api/config/status")
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "config dir unreadable" in detail.lower()

    def test_restart_configured_false_by_default(self, client: TestClient) -> None:
        """When ``PERSONALSCRAPER_PM2_NAME`` is not set, ``restart_configured`` is ``False``."""
        resp = client.get("/api/config/status")
        assert resp.status_code == 200
        assert resp.json()["restart_configured"] is False

    def test_restart_configured_true_when_set(self, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When ``PERSONALSCRAPER_PM2_NAME`` is set, ``restart_configured`` is ``True``."""
        monkeypatch.setenv("PERSONALSCRAPER_PM2_NAME", "torrentmate-web")
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/config/status")
        assert resp.status_code == 200
        assert resp.json()["restart_configured"] is True

    def test_deleted_overlay_flags_stale(self, config_dir: Path) -> None:
        """A snapshot-listed overlay file deleted from disk is flagged stale."""
        import hashlib

        web_path = config_dir / "web.json5"
        web_sha = hashlib.sha256(web_path.read_bytes()).hexdigest()

        # Pre-seed boot hashes with web.json5 present at boot.
        app = _build_app()
        app.state.config_boot_hashes = {"web.json5": web_sha}
        client = TestClient(app)

        original = web_path.read_bytes()
        try:
            web_path.unlink()

            # GET /status → web.json5 missing from disk → stale.
            resp = client.get("/api/config/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "web.json5" in data["stale_files"]
        finally:
            web_path.write_bytes(original)
