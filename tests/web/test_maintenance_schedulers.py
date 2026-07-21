"""Route tests for ``GET /api/maintenance/schedulers`` (webui-ux Phase 5).

Covers the scheduler overview endpoint: the watcher row (enabled state +
last-successful-run from ``acquire.db`` ``watch_state``) and the static cron
rows (schedule + display name from the registry; last-run from ``pipeline_run``
by ``kind``/``command`` — ``None`` when the job writes no row, the current
reality).

Mirrors ``tests/web/test_maintenance_panels.py`` for auth (``tm_session``
cookie via ``/api/auth/login``, ``https`` TestClient, ``tmp_path``-based
``data_dir``) and config-override idioms.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.web.auth.passwords import hash_password
from personalscraper.web.schedulers.registry import CRON_JOBS
from tests.web._web_harness import build_guarded_app

TEST_USERNAME = "testuser"
TEST_PASSWORD = "test-password"
TEST_HASH = hash_password(TEST_PASSWORD)
TEST_SECRET = "maint-schedulers-test-secret"

# Minimal DDL — just the two tables the route reads.
_WATCH_STATE_DDL = "CREATE TABLE watch_state (key TEXT PRIMARY KEY, value REAL NOT NULL);"
_PIPELINE_RUN_DDL = """
CREATE TABLE pipeline_run (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_uid      TEXT    UNIQUE NOT NULL,
    trigger      TEXT    NOT NULL,
    dry_run      INTEGER NOT NULL DEFAULT 0,
    started_at   REAL    NOT NULL,
    ended_at     REAL,
    outcome      TEXT,
    steps_json   TEXT,
    error        TEXT,
    pid          INTEGER,
    kind         TEXT    NOT NULL DEFAULT 'pipeline',
    command      TEXT    NULL,
    options_json TEXT    NULL,
    output_tail  TEXT    NULL
);
"""


def _login(client: TestClient) -> None:
    """Log in and store the session cookie on *client*."""
    resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 204, f"Login failed: {resp.status_code}"


def _build_app(
    test_config,
    tmp_path: Path,
    *,
    with_auth: bool = True,
    **config_overrides,
) -> FastAPI:
    """Build a minimal FastAPI app with auth + maintenance routers."""
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

    from personalscraper.web.routes.maintenance import router as maintenance_router

    return build_guarded_app(config=cfg, settings=settings, routers=maintenance_router, with_auth=with_auth)


def _authenticated_client(test_config, tmp_path: Path, **config_overrides) -> TestClient:
    """Build an app, log in, and return an authenticated ``TestClient``."""
    app = _build_app(test_config, tmp_path, **config_overrides)
    client = TestClient(app, base_url="https://testserver")
    _login(client)
    return client


class TestSchedulersRoute:
    """``GET /api/maintenance/schedulers`` — watcher + static crons."""

    def test_schedulers_empty_dbs(self, test_config, tmp_path: Path) -> None:
        """200 — no DBs → watcher enabled, no last-runs; every cron present, null.

        With no ``watcher.paused`` sentinel the watcher is enabled; with no
        ``acquire.db``/``library.db`` every ``last_run_at`` is ``None``
        (fail-soft). The static cron rows always render from the registry.
        """
        (tmp_path / ".data").mkdir(parents=True, exist_ok=True)
        nonexistent_acquire = tmp_path / "acquire.db"
        nonexistent_indexer = tmp_path / "library.db"
        assert not nonexistent_acquire.exists()
        assert not nonexistent_indexer.exists()

        client = _authenticated_client(
            test_config,
            tmp_path,
            acquire=test_config.acquire.model_copy(update={"db_path": nonexistent_acquire}),
            indexer=test_config.indexer.model_copy(update={"db_path": nonexistent_indexer}),
        )

        resp = client.get("/api/maintenance/schedulers")
        assert resp.status_code == 200
        data = resp.json()

        rows = data["schedulers"]
        # Watcher first, then one row per registered cron.
        assert len(rows) == 1 + len(CRON_JOBS)

        watcher = rows[0]
        assert watcher["kind"] == "watcher"
        assert watcher["name"] == "personalscraper-watch"
        assert watcher["enabled"] is True
        assert watcher["schedule"] is None
        assert watcher["last_run_at"] is None
        assert watcher["last_outcome"] is None

        crons = rows[1:]
        # Fixed oracle (NOT derived from CRON_JOBS) so a registry drop is caught.
        assert {c["name"] for c in crons} == {
            "personalscraper-follow-detect",
            "personalscraper-grab",
            "personalscraper-index-enrich",
        }
        for cron in crons:
            assert cron["kind"] == "cron"
            assert cron["enabled"] is None
            assert isinstance(cron["schedule"], str) and cron["schedule"]
            assert isinstance(cron["display_name"], str) and cron["display_name"]
            # No pipeline_run rows exist → last-run null (current reality).
            assert cron["last_run_at"] is None
            assert cron["last_outcome"] is None

    def test_schedulers_watcher_paused_and_last_run(self, test_config, tmp_path: Path) -> None:
        """200 — sentinel present → watcher disabled; ``watch_state`` last-run surfaced."""
        data_dir = tmp_path / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "watcher.paused").write_text("")

        # Seed acquire.db watch_state with a known last-successful-run timestamp.
        acquire_path = tmp_path / "acquire.db"
        last_run = time.time() - 3600
        conn = sqlite3.connect(str(acquire_path))
        conn.executescript(_WATCH_STATE_DDL)
        conn.execute("INSERT INTO watch_state (key, value) VALUES (?, ?)", ("last_successful_run_at", last_run))
        conn.commit()
        conn.close()

        client = _authenticated_client(
            test_config,
            tmp_path,
            acquire=test_config.acquire.model_copy(update={"db_path": acquire_path}),
            indexer=test_config.indexer.model_copy(update={"db_path": tmp_path / "library.db"}),
        )

        resp = client.get("/api/maintenance/schedulers")
        assert resp.status_code == 200
        watcher = resp.json()["schedulers"][0]
        assert watcher["kind"] == "watcher"
        assert watcher["enabled"] is False  # sentinel present
        assert watcher["last_run_at"] == last_run
        # ``last_successful_run_at`` is only written by a SUCCESSFUL run, so the
        # outcome pill must read success — never « Jamais exécuté » next to a
        # real timestamp (operator-caught contradiction, e2e loop 1).
        assert watcher["last_outcome"] == "success"

    def test_schedulers_watcher_without_any_run_has_no_outcome(self, test_config, tmp_path: Path) -> None:
        """200 — no watch_state row → last_run_at AND last_outcome both null."""
        data_dir = tmp_path / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)

        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        conn.executescript(_WATCH_STATE_DDL)
        conn.commit()
        conn.close()

        client = _authenticated_client(
            test_config,
            tmp_path,
            acquire=test_config.acquire.model_copy(update={"db_path": acquire_path}),
            indexer=test_config.indexer.model_copy(update={"db_path": tmp_path / "library.db"}),
        )

        watcher = client.get("/api/maintenance/schedulers").json()["schedulers"][0]
        assert watcher["last_run_at"] is None
        assert watcher["last_outcome"] is None

    def test_schedulers_cron_last_run_from_pipeline_run(self, test_config, tmp_path: Path) -> None:
        """200 — a matching ``pipeline_run`` row surfaces a cron's last-run + outcome.

        Even though the crons write no row today, the match rule (``kind`` +
        ``command`` prefix) is exercised so a future row would surface: a
        ``kind='pipeline'`` row with ``command='grab'`` is picked up by the
        ``personalscraper-grab`` cron.
        """
        (tmp_path / ".data").mkdir(parents=True, exist_ok=True)
        indexer_path = tmp_path / "library.db"
        grab_started = time.time() - 1800
        conn = sqlite3.connect(str(indexer_path))
        conn.executescript(_PIPELINE_RUN_DDL)
        conn.execute(
            "INSERT INTO pipeline_run (run_uid, trigger, started_at, ended_at, outcome, kind, command) "
            "VALUES ('r1', 'cli', ?, ?, 'success', 'pipeline', 'grab')",
            (grab_started, grab_started + 60),
        )
        # A second, older grab row must NOT win the ORDER BY started_at DESC.
        conn.execute(
            "INSERT INTO pipeline_run (run_uid, trigger, started_at, ended_at, outcome, kind, command) "
            "VALUES ('r0', 'cli', ?, ?, 'error', 'pipeline', 'grab')",
            (grab_started - 86400, grab_started - 86400 + 60),
        )
        conn.commit()
        conn.close()

        client = _authenticated_client(
            test_config,
            tmp_path,
            acquire=test_config.acquire.model_copy(update={"db_path": tmp_path / "acquire.db"}),
            indexer=test_config.indexer.model_copy(update={"db_path": indexer_path}),
        )

        resp = client.get("/api/maintenance/schedulers")
        assert resp.status_code == 200
        rows = resp.json()["schedulers"]
        grab = next(r for r in rows if r["name"] == "personalscraper-grab")
        assert grab["last_run_at"] == grab_started  # most recent, not the older error
        assert grab["last_outcome"] == "success"
        # Non-matching crons stay null.
        follow = next(r for r in rows if r["name"] == "personalscraper-follow-detect")
        assert follow["last_run_at"] is None

    def test_schedulers_surface_maintenance_kind_acquisition_runs(self, test_config, tmp_path: Path) -> None:
        """200 — a ``kind='maintenance'`` follow-detect run surfaces on its cron (§1).

        Regression: the acquisition CLIs (follow-detect / grab) record a
        ``kind='maintenance'`` pipeline_run row — not ``kind='pipeline'``. The
        cron match rule must be by COMMAND alone, else these real runs stay
        hidden and the schedulers panel is stuck on « Jamais exécuté » despite a
        run having happened. Red on the old ``kind='pipeline'``-filtered query.
        """
        (tmp_path / ".data").mkdir(parents=True, exist_ok=True)
        indexer_path = tmp_path / "library.db"
        started = time.time() - 900
        conn = sqlite3.connect(str(indexer_path))
        conn.executescript(_PIPELINE_RUN_DDL)
        conn.execute(
            "INSERT INTO pipeline_run (run_uid, trigger, started_at, ended_at, outcome, kind, command) "
            "VALUES ('rm', 'cron', ?, ?, 'success', 'maintenance', 'follow-detect')",
            (started, started + 5),
        )
        conn.commit()
        conn.close()

        client = _authenticated_client(
            test_config,
            tmp_path,
            acquire=test_config.acquire.model_copy(update={"db_path": tmp_path / "acquire.db"}),
            indexer=test_config.indexer.model_copy(update={"db_path": indexer_path}),
        )

        rows = client.get("/api/maintenance/schedulers").json()["schedulers"]
        detect = next(r for r in rows if r["name"] == "personalscraper-follow-detect")
        assert detect["last_run_at"] == started, "a kind='maintenance' follow-detect run must surface on its cron"
        assert detect["last_outcome"] == "success"

    def test_schedulers_unauthenticated(self, test_config, tmp_path: Path) -> None:
        """401 — no session cookie."""
        app = _build_app(test_config, tmp_path, with_auth=False)
        client = TestClient(app)
        resp = client.get("/api/maintenance/schedulers")
        assert resp.status_code == 401
