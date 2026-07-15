"""Route tests for the 3 maintenance-dashboard panel GET endpoints.

Covers ``GET /api/maintenance/disks``, ``/locks``, and ``/index-health``
with both authenticated and unauthenticated paths.

Mirrors the structure of ``tests/web/test_pipeline_routes.py`` for
auth (``tm_session`` cookie via ``/api/auth/login``, ``https`` TestClient,
``tmp_path``-based ``data_dir``) and config-override idioms.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.indexer.db import apply_migrations
from personalscraper.web.auth.passwords import hash_password
from personalscraper.web.deps import require_session


def _mount_guarded(app: FastAPI, router: APIRouter) -> None:
    """Mount *router* behind the session-guard perimeter, mirroring app.py (R14).

    Handlers no longer carry a per-route ``Depends(require_session)`` — the
    guard lives on the parent router only (web-ui.md §6), so test apps must
    reproduce the same perimeter to exercise auth.
    """
    guarded_api = APIRouter(dependencies=[Depends(require_session)])
    guarded_api.include_router(router)
    app.include_router(guarded_api)


TEST_USERNAME = "testuser"
TEST_PASSWORD = "test-password"
TEST_HASH = hash_password(TEST_PASSWORD)
TEST_SECRET = "maint-panels-test-secret"

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "personalscraper" / "indexer" / "migrations"

NOW = int(time.time())


# ── Auth helper ────────────────────────────────────────────────────────────────


def _login(
    client: TestClient,
    username: str = TEST_USERNAME,
    password: str = TEST_PASSWORD,
) -> None:
    """Log in and store the session cookie on *client*.

    Args:
        client: A ``TestClient`` with ``base_url="https://testserver"``.
        username: Web username (must match what the app was configured with).
        password: Web password (must match the hash stored in settings).
    """
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 204, f"Login failed: {resp.status_code}"


def _build_app(
    test_config,
    tmp_path: Path,
    *,
    with_auth: bool = True,
    **config_overrides,
) -> tuple[FastAPI, Settings]:
    """Build a minimal FastAPI app with auth and maintenance routers.

    Args:
        test_config: Synthetic ``Config`` fixture.
        tmp_path: Pytest temporary directory.
        with_auth: When ``True`` (default), include the auth router so
            ``/api/auth/login`` works.
        **config_overrides: Extra keys passed to ``test_config.model_copy(update=...)``
            for test-specific overrides (e.g. ``indexer``, ``web``).

    Returns:
        A ``(FastAPI, Settings)`` tuple ready for ``TestClient`` wrapping.
    """
    cfg = test_config.model_copy(
        update={
            "paths": test_config.paths.model_copy(update={"data_dir": tmp_path / ".data"}),
            "web": test_config.web.model_copy(update={"username": TEST_USERNAME}),
            **config_overrides,
        },
    )

    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        web_password_hash=TEST_HASH,
        web_jwt_secret=TEST_SECRET,
    )

    app = FastAPI()
    app.state.config = cfg
    app.state.settings = settings

    if with_auth:
        from personalscraper.web.auth.routes import router as auth_router

        app.include_router(auth_router)

    from personalscraper.web.routes.maintenance import router as maintenance_router

    _mount_guarded(app, maintenance_router)

    return app, settings


def _build_authenticated_client(
    test_config,
    tmp_path: Path,
    **config_overrides,
) -> TestClient:
    """Build a minimal app + log in → return an authenticated ``TestClient``.

    Args:
        test_config: Synthetic ``Config`` fixture.
        tmp_path: Pytest temporary directory.
        **config_overrides: Passed through to :func:`_build_app`.

    Returns:
        An authenticated ``TestClient`` ready for guarded-route assertions.
    """
    app, _settings = _build_app(test_config, tmp_path, **config_overrides)
    client = TestClient(app, base_url="https://testserver")
    _login(client)
    return client


# ── GET /disks ─────────────────────────────────────────────────────────────────


class TestDisksRoute:
    """``GET /api/maintenance/disks`` — mount status and capacity."""

    def test_disks_authenticated(self, test_config, tmp_path: Path) -> None:
        """200 — each configured disk has numeric fields and mounted=True.

        Creates the disk paths on *tmp_path* so ``get_disk_status`` reports
        them as mounted.  ``free_gb`` / ``total_gb`` are real shutil.disk_usage
        values; ``used_pct`` falls in [0, 100].
        """
        # Ensure disk paths exist so they are "mounted".
        for disk_cfg in test_config.disks:
            disk_cfg.path.mkdir(parents=True, exist_ok=True)
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.get("/api/maintenance/disks")
        assert resp.status_code == 200
        data = resp.json()
        assert "disks" in data
        assert isinstance(data["disks"], list)
        assert len(data["disks"]) == len(test_config.disks)

        for entry in data["disks"]:
            assert isinstance(entry["id"], str)
            assert isinstance(entry["label"], str)
            assert entry["mounted"] is True
            assert isinstance(entry["free_gb"], (int, float))
            assert isinstance(entry["total_gb"], (int, float))
            assert entry["total_gb"] > 0
            assert isinstance(entry["used_pct"], (int, float))
            assert 0.0 <= entry["used_pct"] <= 100.0

    def test_disks_unauthenticated(self, test_config, tmp_path: Path) -> None:
        """401 — no session cookie."""
        app, _settings = _build_app(test_config, tmp_path, with_auth=False)
        client = TestClient(app)
        resp = client.get("/api/maintenance/disks")
        assert resp.status_code == 401


# ── GET /locks ─────────────────────────────────────────────────────────────────


class TestLocksRoute:
    """``GET /api/maintenance/locks`` — pipeline lock, sentinels, orphans."""

    @pytest.fixture(autouse=True)
    def _reset_orphan_cache(self) -> None:
        """Clear the module-level tmp-orphan cache so each test sweeps fresh."""
        from personalscraper.web.routes import maintenance as _maint

        _maint._orphan_cache["ts"] = 0.0
        _maint._orphan_cache["data"] = []
        _maint._orphan_cache["computing"] = False

    @staticmethod
    def _wait_for_sweep(client, timeout_s: float = 5.0) -> dict:
        """GET /locks until the background sweep lands (C25), returning the body."""
        deadline = time.time() + timeout_s
        data: dict = {}
        while time.time() < deadline:
            data = client.get("/api/maintenance/locks").json()
            if data["sweep"]["status"] == "ready":
                return data
            time.sleep(0.02)
        raise AssertionError(f"sweep never became ready: {data.get('sweep')}")

    def test_locks_returns_pending_sweep_on_cold_read(self, test_config, tmp_path: Path) -> None:
        """C25 — the cold first read returns locks immediately + a pending sweep."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client(test_config, tmp_path)

        data = client.get("/api/maintenance/locks").json()
        # Locks are present right away; the slow disk sweep is still pending.
        assert data["pipeline_lock"]["held"] is False
        assert data["sweep"]["status"] == "pending"
        assert data["sweep"]["orphans"] == []

    def test_locks_idle(self, test_config, tmp_path: Path) -> None:
        """200 — no lock file → ``held=False``, sentinels absent, no orphans."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

        client = _build_authenticated_client(test_config, tmp_path)

        data = self._wait_for_sweep(client)

        lock = data["pipeline_lock"]
        assert lock["held"] is False
        assert lock["pid"] is None
        assert lock["pid_alive"] is False
        assert lock["stale"] is False
        assert lock["age_s"] is None

        sentinels = data["sentinels"]
        assert sentinels["pause"] is False
        assert sentinels["pause_age_s"] is None
        assert sentinels["watcher_paused"] is False
        assert sentinels["watcher_paused_age_s"] is None

        assert data["sweep"]["status"] == "ready"
        assert data["sweep"]["orphans"] == []

    def test_locks_stale(self, test_config, tmp_path: Path) -> None:
        """Lock file with a dead PID → ``stale=True``, ``pid_alive=False``.

        Spawns a short-lived subprocess, waits for it to exit, then writes
        its (now dead) PID into ``data_dir/pipeline.lock``.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        # Spawn a process that exits immediately, capture its PID.
        proc = subprocess.Popen([os.sys.executable, "-c", "pass"])
        proc.wait()
        dead_pid = proc.pid

        (data_dir / "pipeline.lock").write_text(str(dead_pid))

        client = _build_authenticated_client(test_config, tmp_path)

        resp = client.get("/api/maintenance/locks")
        assert resp.status_code == 200
        data = resp.json()

        lock = data["pipeline_lock"]
        # is_lock_held returns False when the PID is dead (ProcessLookupError
        # on os.kill(pid, 0)) — the lock file exists but is not "held" by a
        # live process.
        assert lock["held"] is False
        assert lock["pid"] == dead_pid
        assert lock["pid_alive"] is False
        assert lock["stale"] is True
        assert isinstance(lock["age_s"], (int, float))

    def test_locks_tmp_orphans(self, test_config, tmp_path: Path) -> None:
        """``_tmp_dispatch_*`` dirs in the staging root land in ``sweep.orphans``.

        Creates 3 temporary dirs and asserts the background sweep reports them
        all (once it lands), demonstrating the cap holds at a small count.
        """
        staging = test_config.paths.staging_dir
        staging.mkdir(parents=True, exist_ok=True)
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

        orphans_created = []
        for i in range(3):
            p = staging / f"_tmp_dispatch_test_{i}"
            p.mkdir()
            orphans_created.append(str(p))

        client = _build_authenticated_client(test_config, tmp_path)

        data = self._wait_for_sweep(client)
        orphans = data["sweep"]["orphans"]

        reported_paths = [e["path"] for e in orphans]
        reported_prefixes = [e["prefix"] for e in orphans]

        assert len(orphans) == 3
        for created_path in orphans_created:
            assert created_path in reported_paths
        for prefix in reported_prefixes:
            assert prefix == "_tmp_dispatch_"

    def test_locks_orphan_sweep_is_cached(self, test_config, tmp_path: Path) -> None:
        """The disk walk runs once per TTL — reads within it hit the cache (C25)."""
        from unittest.mock import patch

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client(test_config, tmp_path)

        with patch(
            "personalscraper.web.routes.maintenance._sweep_tmp_orphans",
            return_value=[],
        ) as sweep:
            # The first (cold) read triggers exactly one background sweep; once
            # it lands, further reads within the TTL serve the cache, not a walk.
            self._wait_for_sweep(client)
            assert client.get("/api/maintenance/locks").status_code == 200
            assert client.get("/api/maintenance/locks").status_code == 200
        assert sweep.call_count == 1

    def test_locks_unauthenticated(self, test_config, tmp_path: Path) -> None:
        """401 — no session cookie."""
        app, _settings = _build_app(test_config, tmp_path, with_auth=False)
        client = TestClient(app)
        resp = client.get("/api/maintenance/locks")
        assert resp.status_code == 401


# ── GET /index-health ──────────────────────────────────────────────────────────


class TestIndexHealthRoute:
    """``GET /api/maintenance/index-health`` — aggregate library.db snapshot."""

    @staticmethod
    def _seed_db(db_path: Path) -> None:
        """Apply all migrations to *db_path* and insert 2 media_items + files.

        Args:
            db_path: Absolute path where the SQLite database will be created.
        """
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        apply_migrations(conn, MIGRATIONS_DIR)

        conn.execute(
            "INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES (?,?,?,1)", ("uuid-1", "disk1", "/tmp/disk1")
        )
        conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1, 'test')")

        # Movie — nfo valid, canonical_provider set.
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "date_created, date_modified, nfo_status, canonical_provider, external_ids_json) "
            "VALUES ('movie', 'Test Movie', 'Test Movie', 'movies', ?, ?, 'valid', 'tmdb', '{}')",
            (NOW, NOW),
        )
        # Show — nfo missing, canonical_provider NULL (for canonical_null assertion).
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "date_created, date_modified, nfo_status, canonical_provider, external_ids_json) "
            "VALUES ('show', 'Test Show', 'Test Show', 'tv_shows', ?, ?, 'missing', NULL, '{}')",
            (NOW, NOW),
        )

        # Releases — one per item (show-level, no episode).
        conn.execute("INSERT INTO media_release(item_id, episode_id) VALUES (1, NULL)")
        conn.execute("INSERT INTO media_release(item_id, episode_id) VALUES (2, NULL)")

        # Files — 1 GiB each.
        conn.execute(
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, "
            "mtime_ns, oshash, scan_generation, last_verified_at) "
            "VALUES (1, 1, 'movie.mkv', 1073741824, ?, 'aaaa1111bbbb2222', 1, ?)",
            (NOW * 1_000_000_000, NOW),
        )
        conn.execute(
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, "
            "mtime_ns, oshash, scan_generation, last_verified_at) "
            "VALUES (2, 1, 'show.mkv', 1073741824, ?, 'cccc3333dddd4444', 1, ?)",
            (NOW * 1_000_000_000, NOW),
        )
        # Soft-deleted file.
        conn.execute(
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, "
            "mtime_ns, oshash, scan_generation, last_verified_at, deleted_at) "
            "VALUES (1, 1, 'deleted.mkv', 524288000, ?, 'eeee5555ffff6666', 1, ?, ?)",
            (NOW * 1_000_000_000, NOW, NOW),
        )

        conn.commit()
        conn.close()

    @pytest.fixture
    def seeded_db_path(self, tmp_path: Path) -> Path:
        """Create a seeded ``library.db`` file at a known path.

        Args:
            tmp_path: Pytest temporary directory.

        Returns:
            Absolute path to the populated database file.
        """
        db_path = tmp_path / "library.db"
        self._seed_db(db_path)
        return db_path

    def test_index_health(self, test_config, tmp_path: Path, seeded_db_path: Path) -> None:
        """200 — seeded DB returns correct item/movie/show/file counts.

        Seeded state:
        - 2 media_items: 1 movie ('valid' nfo), 1 show ('missing' nfo)
        - 2 non-deleted media_files (1 GiB each → 2.0 GiB total)
        - 1 soft-deleted media_file
        - 1 canonical_provider NULL (the show)
        """
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": seeded_db_path}),
        )

        resp = client.get("/api/maintenance/index-health")
        assert resp.status_code == 200
        data = resp.json()

        assert data["items"] == 2
        assert data["movies"] == 1
        assert data["shows"] == 1
        assert data["files"] == 2
        assert data["size_gb"] == pytest.approx(2.0, rel=0.1)

        nfo = data["nfo"]
        assert nfo["valid"] == 1
        assert nfo["invalid"] == 0
        assert nfo["missing"] == 1

        assert data["soft_deleted"] == 1
        assert data["canonical_null"] == 1

        # No scans recorded → all last_scan_* null/false.
        assert data["last_scan_id"] is None
        assert data["last_scan_mode"] is None
        assert data["last_scan_status"] is None
        assert data["last_scan_started_at"] is None
        assert data["last_scan_finished_at"] is None
        assert data["last_scan_stuck"] is False

        # No repair/outbox entries.
        assert data["repair_queue_pending"] == 0
        assert data["repair_queue_oldest_age_s"] is None
        assert data["outbox_pending"] == 0
        assert data["outbox_oldest_age_s"] is None


class TestDestructiveLogRoute:
    """``GET /api/maintenance/destructive-log`` — the §7 forensic trail."""

    def test_destructive_log_returns_recorded_ops(self, test_config, tmp_path: Path) -> None:
        """200 — recorded destructive ops surface newest-first with who/what/where."""
        from personalscraper.indexer.destructive_journal import OP_DELETE, OP_OVERWRITE, record_destruction

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        conn.close()

        record_destruction(db_path, op=OP_OVERWRITE, path="/disk/Ferrari (2023)", actor="dispatch", detail="REPLACE")
        record_destruction(db_path, op=OP_DELETE, path="/disk/.actors", actor="disk-clean", detail="Nettoyage")

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        resp = client.get("/api/maintenance/destructive-log")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) == 2
        assert entries[0]["op"] == "delete"
        assert entries[0]["actor"] == "disk-clean"
        assert entries[1]["op"] == "overwrite"
        assert entries[1]["path"] == "/disk/Ferrari (2023)"

    def test_destructive_log_fail_soft_empty(self, test_config, tmp_path: Path) -> None:
        """200 with an empty list when the DB has no journal table (fail-soft)."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        empty_db = tmp_path / "empty.db"
        conn = sqlite3.connect(str(empty_db))
        conn.execute("CREATE TABLE unrelated (x INTEGER)")
        conn.commit()
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": empty_db}),
        )

        resp = client.get("/api/maintenance/destructive-log")
        assert resp.status_code == 200
        assert resp.json()["entries"] == []

    def test_index_health_empty_db(self, test_config, tmp_path: Path) -> None:
        """200 — non-existent db_path → zeroed response (fail-soft, NOT 500)."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        nonexistent = tmp_path / "nonexistent.db"
        # Assert it really does not exist.
        assert not nonexistent.exists()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": nonexistent}),
        )

        resp = client.get("/api/maintenance/index-health")
        assert resp.status_code == 200
        data = resp.json()

        assert data["items"] == 0
        assert data["movies"] == 0
        assert data["shows"] == 0
        assert data["files"] == 0
        assert data["size_gb"] == 0.0
        assert data["nfo"]["valid"] == 0
        assert data["nfo"]["invalid"] == 0
        assert data["nfo"]["missing"] == 0
        # A genuinely missing DB is an empty library, NOT a degraded one.
        assert data["degraded"] is False
        assert data["error"] is None

    def test_index_health_degraded_on_broken_db(self, test_config, tmp_path: Path) -> None:
        """200 with ``degraded=True`` when the DB exists but a query fails (Finding D).

        A DB file that has ``pipeline_run`` but no ``media_item`` table must NOT
        be reported as a pristine empty library — the first aggregate query
        raises ``OperationalError`` and the response is flagged ``degraded``.
        """
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(db_path))
        # Present but mis-migrated: a table exists, but not media_item.
        conn.execute("CREATE TABLE pipeline_run (id INTEGER PRIMARY KEY, run_uid TEXT)")
        conn.commit()
        conn.close()

        client = _build_authenticated_client(
            test_config,
            tmp_path,
            indexer=test_config.indexer.model_copy(update={"db_path": db_path}),
        )

        resp = client.get("/api/maintenance/index-health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["degraded"] is True
        assert data["error"] is not None
        # Counts are still zeroed, but the degraded flag distinguishes this
        # from a genuinely empty library.
        assert data["items"] == 0

    def test_index_health_unauthenticated(self, test_config, tmp_path: Path) -> None:
        """401 — no session cookie."""
        app, _settings = _build_app(test_config, tmp_path, with_auth=False)
        client = TestClient(app)
        resp = client.get("/api/maintenance/index-health")
        assert resp.status_code == 401
