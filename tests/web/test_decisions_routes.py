"""Route tests for the 5 decision queue endpoints (scrape-arbiter feature).

Covers ``GET /api/decisions`` (list), ``GET /api/decisions/{id}`` (detail),
``POST /api/decisions/{id}/search``, ``POST /api/decisions/{id}/resolve``,
and ``POST /api/decisions/{id}/dismiss`` — with authenticated, unauthenticated,
staging, XRW, lock-conflict, and edge-case paths.

Mirrors the structure of ``tests/web/test_maintenance_actions_run.py`` for
auth (``tm_session`` cookie via ``/api/auth/login``, ``https`` TestClient,
``tmp_path``-based ``data_dir``) and config-override idioms.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.web.deps import require_session

from .test_maintenance_panels import (
    TEST_HASH,
    TEST_SECRET,
    TEST_USERNAME,
    _build_app,
    _login,
    _mount_guarded,
)

NOW = int(time.time())


def _build_authenticated_client_with_decisions(
    test_config,
    tmp_path: Path,
    **config_overrides,
) -> TestClient:
    """Build a minimal app with BOTH maintenance + decisions routers, then log in.

    The shared ``_build_app`` fixture only mounts ``maintenance_router``.
    This helper extends it to also mount ``decisions_router`` under the same
    ``guarded_api`` perimeter.

    Args:
        test_config: Synthetic ``Config`` fixture.
        tmp_path: Pytest temporary directory.
        **config_overrides: Passed through to :func:`_build_app`.

    Returns:
        An authenticated ``TestClient`` ready for decisions-route assertions.
    """
    # Build the config with overrides.
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

    # Auth router (needed for login).
    from personalscraper.web.auth.routes import router as auth_router

    app.include_router(auth_router)

    # Guarded API with both maintenance + decisions routers.
    guarded_api = APIRouter(dependencies=[Depends(require_session)])
    from personalscraper.web.routes.decisions import router as decisions_router
    from personalscraper.web.routes.maintenance import router as maintenance_router

    guarded_api.include_router(maintenance_router)
    guarded_api.include_router(decisions_router)
    app.include_router(guarded_api)

    client = TestClient(app, base_url="https://testserver")
    _login(client)
    return client


# ── DB helpers ─────────────────────────────────────────────────────────────────


def _create_library_db(db_path: Path) -> sqlite3.Connection:
    """Create a minimal ``library.db`` with ``pipeline_run`` and ``scrape_decision`` tables.

    The ``pipeline_run`` DDL reflects migrations 011 + 012 (all columns present).
    The ``scrape_decision`` DDL matches migration 013 exactly.

    Args:
        db_path: Absolute path where the database will be created.

    Returns:
        An open connection (caller must close).
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    # pipeline_run — migrations 011 + 012 (all columns).
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pipeline_run ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_uid TEXT UNIQUE NOT NULL,"
        "  kind TEXT NOT NULL DEFAULT 'pipeline',"
        "  command TEXT,"
        "  trigger TEXT NOT NULL DEFAULT 'web',"
        "  dry_run INTEGER NOT NULL DEFAULT 0,"
        "  options_json TEXT,"
        "  started_at REAL NOT NULL,"
        "  ended_at REAL,"
        "  outcome TEXT,"
        "  steps_json TEXT,"
        "  error TEXT,"
        "  pid INTEGER,"
        "  output_tail TEXT"
        ")"
    )

    # scrape_decision — migration 013 (exact DDL).
    conn.execute(
        "CREATE TABLE IF NOT EXISTS scrape_decision ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  staging_path TEXT UNIQUE NOT NULL,"
        "  media_kind TEXT NOT NULL,"
        "  extracted_title TEXT NOT NULL,"
        "  extracted_year INTEGER,"
        '  "trigger" TEXT NOT NULL,'
        "  candidates_json TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  resolution_json TEXT,"
        "  run_uid TEXT,"
        "  created_at REAL NOT NULL,"
        "  updated_at REAL NOT NULL,"
        "  resolved_at REAL"
        ")"
    )

    conn.commit()
    return conn


def _seed_decision(
    conn: sqlite3.Connection,
    *,
    decision_id: int | None = None,
    staging_path: str = "/tmp/staging/Some Movie (2024)",
    media_kind: str = "movie",
    extracted_title: str = "Some Movie",
    extracted_year: int | None = 2024,
    trigger: str = "mid_band",
    candidates_json: str | None = None,
    status: str = "pending",
    resolution_json: str | None = None,
    created_at: float | None = None,
) -> int:
    """Insert a ``scrape_decision`` row and return its id.

    Args:
        conn: An open connection to a database with the ``scrape_decision`` table.
        decision_id: Optional explicit id (auto-increment when absent).
        staging_path: Absolute staging path.
        media_kind: ``"movie"`` or ``"tvshow"``.
        extracted_title: Title guessed from the folder name.
        extracted_year: Year guessed, or ``None``.
        trigger: Decision trigger.
        candidates_json: JSON array of candidates (default: one dummy candidate).
        status: ``"pending"`` | ``"resolved"`` | ``"dismissed"`` | ``"superseded"``.
        resolution_json: JSON resolution metadata, or ``None``.
        created_at: Epoch seconds (defaults to ``NOW``).

    Returns:
        The id of the inserted row.
    """
    if candidates_json is None:
        candidates_json = json.dumps(
            [
                {
                    "provider": "tmdb",
                    "provider_id": 123,
                    "title": extracted_title,
                    "year": extracted_year,
                    "score": 0.85,
                    "poster_url": None,
                    "overview": "A test movie.",
                }
            ]
        )

    now = created_at if created_at is not None else float(NOW)

    if decision_id is not None:
        conn.execute(
            "INSERT INTO scrape_decision "
            "(id, staging_path, media_kind, extracted_title, extracted_year, "
            '"trigger", candidates_json, status, resolution_json, created_at, updated_at) '
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                decision_id,
                staging_path,
                media_kind,
                extracted_title,
                extracted_year,
                trigger,
                candidates_json,
                status,
                resolution_json,
                now,
                now,
            ),
        )
    else:
        cursor = conn.execute(
            "INSERT INTO scrape_decision "
            "(staging_path, media_kind, extracted_title, extracted_year, "
            '"trigger", candidates_json, status, resolution_json, created_at, updated_at) '
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                staging_path,
                media_kind,
                extracted_title,
                extracted_year,
                trigger,
                candidates_json,
                status,
                resolution_json,
                now,
                now,
            ),
        )
        decision_id = cursor.lastrowid

    conn.commit()
    assert decision_id is not None
    return decision_id


def _seed_running_resolve(
    conn: sqlite3.Connection,
    *,
    pid: int | None = None,
    decision_id: int | None = None,
    run_uid: str = "deadc0de1234",
) -> None:
    """Insert a running scrape-resolve ``pipeline_run`` row.

    Args:
        conn: An open connection to a database with the ``pipeline_run`` table.
        pid: Optional PID to store in the row.  When ``None`` the column is
            left NULL (simulating a pre-pid-migration row or a runner that
            crashed before inserting its pid).
        decision_id: Optional ``decision_id`` embedded in ``options_json`` so
            the per-decision reservation guard (scoped by
            ``json_extract(options_json, '$.decision_id')``) can match it.  When
            ``None`` an empty ``{}`` is stored (a row scoped to no decision — the
            guard will NOT match it for any decision id).
        run_uid: The run identifier for the row (distinct rows need distinct
            uids when a test seeds more than one).
    """
    options_json = "{}" if decision_id is None else json.dumps({"decision_id": decision_id})
    conn.execute(
        "INSERT INTO pipeline_run (run_uid, kind, command, trigger, dry_run, "
        "  options_json, started_at, outcome, pid) "
        "VALUES (?, 'maintenance', 'scrape-resolve', 'web', 0, ?, ?, 'running', ?)",
        (run_uid, options_json, float(NOW), pid),
    )
    conn.commit()


def _query_pipeline_row(db_path: Path, run_uid: str) -> dict | None:
    """Return the ``pipeline_run`` row for *run_uid* as a dict, or ``None``.

    Args:
        db_path: Path to the SQLite database.
        run_uid: The run identifier to look up.

    Returns:
        The row as a dict, or ``None`` when no such row exists.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pipeline_run WHERE run_uid = ?", (run_uid,)).fetchone()
    conn.close()
    return dict(row) if row is not None else None


def _query_decision_row(db_path: Path, decision_id: int) -> dict | None:
    """Return the ``scrape_decision`` row for *decision_id* as a dict, or ``None``."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM scrape_decision WHERE id = ?", (decision_id,)).fetchone()
    conn.close()
    return dict(row) if row is not None else None


# ═══════════════════════════════════════════════════════════════════════════════
# GET / — list
# ═══════════════════════════════════════════════════════════════════════════════


class TestListDecisions:
    """``GET /api/decisions`` — pagination, status filter, pending_count, orphan GC."""

    def test_list_defaults_to_pending(self, test_config, tmp_path: Path) -> None:
        """200 — default filter is ``status=pending``, pending_count is always computed."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        staging1 = tmp_path / "staging" / "Test 1"
        staging2 = tmp_path / "staging" / "Test 2"
        staging1.mkdir(parents=True, exist_ok=True)
        staging2.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, status="pending", staging_path=str(staging1))
        _seed_decision(conn, status="resolved", staging_path=str(staging2))
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.get("/api/decisions/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 1
        assert data["total"] == 1  # Only pending rows (default filter)
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "pending"
        assert data["page"] == 1
        assert data["page_size"] == 50

    def test_list_status_filter(self, test_config, tmp_path: Path) -> None:
        """200 — ``?status=resolved`` returns only resolved rows."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        staging1 = tmp_path / "staging" / "Test 1"
        staging2 = tmp_path / "staging" / "Test 2"
        staging1.mkdir(parents=True, exist_ok=True)
        staging2.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, status="pending", staging_path=str(staging1))
        _seed_decision(conn, status="resolved", staging_path=str(staging2))
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.get("/api/decisions/?status=resolved")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 1  # Always computed
        assert data["total"] == 1  # Only resolved
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "resolved"

    def test_list_pagination(self, test_config, tmp_path: Path) -> None:
        """200 — pagination with page and page_size params."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        for i in range(5):
            staging = tmp_path / "staging" / f"Test {i}"
            staging.mkdir(parents=True, exist_ok=True)
            _seed_decision(conn, staging_path=str(staging), created_at=float(NOW - i))
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        # Page 1, size 2.
        resp = client.get("/api/decisions/?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

        # Page 3, size 2 — should have 1 item.
        resp = client.get("/api/decisions/?page=3&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    def test_list_page_size_over_cap_rejected(self, test_config, tmp_path: Path) -> None:
        """422 — page_size > 200 is rejected by the OpenAPI constraint (F42).

        The param is ``Query(le=200)`` so an out-of-range value is a typed
        422 the frontend contract can catch, not a silently-clamped 200.
        """
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.get("/api/decisions/?page_size=999")
        assert resp.status_code == 422
        # A valid max is accepted.
        ok = client.get("/api/decisions/?page_size=200")
        assert ok.status_code == 200
        assert ok.json()["page_size"] == 200

    def test_list_invalid_status_rejected(self, test_config, tmp_path: Path) -> None:
        """422 — an unknown status filter is rejected by the Literal constraint (F42)."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )
        resp = client.get("/api/decisions/?status=Pending")  # wrong case
        assert resp.status_code == 422

    def test_list_pending_count_independent_of_filter(self, test_config, tmp_path: Path) -> None:
        """200 — pending_count includes all pending rows regardless of status filter."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        for name in ("Pending 1", "Pending 2", "Resolved"):
            staging = tmp_path / "staging" / name
            staging.mkdir(parents=True, exist_ok=True)
        _seed_decision(conn, status="pending", staging_path=str(tmp_path / "staging" / "Pending 1"))
        _seed_decision(conn, status="pending", staging_path=str(tmp_path / "staging" / "Pending 2"))
        _seed_decision(conn, status="resolved", staging_path=str(tmp_path / "staging" / "Resolved"))
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.get("/api/decisions/?status=resolved")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 2
        assert data["total"] == 1  # Only resolved
        assert len(data["items"]) == 1

    def test_list_marks_superseded_orphans(self, test_config, tmp_path: Path) -> None:
        """200 — pending rows whose staging path does not exist are marked superseded."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        # Use a path that definitely does not exist.
        _seed_decision(conn, staging_path="/tmp/nonexistent/deadbeef/Some Movie (2024)", status="pending")
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        # First request: GC runs, marks as superseded.
        resp = client.get("/api/decisions/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 0
        assert data["total"] == 0  # No pending rows left

        # Verify the row is now superseded.
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        row = conn2.execute("SELECT status FROM scrape_decision WHERE id = 1").fetchone()
        conn2.close()
        assert row is not None
        assert row["status"] == "superseded"

    def test_list_no_db_returns_empty(self, test_config, tmp_path: Path) -> None:
        """200 — no DB file → empty response, no 500."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "nonexistent.db"  # Not created

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.get("/api/decisions/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["pending_count"] == 0
        assert data["total"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# GET /{id} — detail
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetDecision:
    """``GET /api/decisions/{id}`` — 200, 404, 410."""

    def test_detail_returns_full_row(self, test_config, tmp_path: Path) -> None:
        """200 — detail includes candidates, resolution_json=None when pending."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.get("/api/decisions/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["media_kind"] == "movie"
        assert data["status"] == "pending"
        assert isinstance(data["candidates"], list)
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["provider"] == "tmdb"
        assert data["resolution_json"] is None

    def test_detail_404_unknown_id(self, test_config, tmp_path: Path) -> None:
        """404 — decision id does not exist."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.get("/api/decisions/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_detail_410_superseded(self, test_config, tmp_path: Path) -> None:
        """410 — decision has status 'superseded'."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, status="superseded")
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.get("/api/decisions/1")
        assert resp.status_code == 410
        assert "superseded" in resp.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# POST /{id}/search
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchDecision:
    """``POST /api/decisions/{id}/search`` — 200 (mocked clients), 502, 404, 410."""

    def test_search_movie_returns_candidates(self, test_config, tmp_path: Path) -> None:
        """200 — movie search returns fresh candidates from TMDB."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, media_kind="movie")
        conn.close()

        from personalscraper.scraper.decision_candidate import DecisionCandidate

        dummy = [DecisionCandidate(provider="tmdb", provider_id=550, title="Fight Club", year=1999, score=0.95)]

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with patch(
            "personalscraper.scraper.confidence.match_movie_detailed",
            return_value=(None, dummy),
        ):
            resp = client.post(
                "/api/decisions/1/search",
                json={"title": "Fight Club", "year": 1999},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "candidates" in data
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["provider"] == "tmdb"
        assert data["candidates"][0]["title"] == "Fight Club"

    def test_search_tvshow_returns_candidates(self, test_config, tmp_path: Path) -> None:
        """200 — tvshow search returns fresh candidates from TVDB/TMDB."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, media_kind="tvshow", extracted_title="Breaking Bad")
        conn.close()

        from personalscraper.scraper.decision_candidate import DecisionCandidate

        dummy = [DecisionCandidate(provider="tvdb", provider_id=81189, title="Breaking Bad", year=2008, score=0.98)]

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with patch(
            "personalscraper.scraper.confidence.match_tvshow_detailed",
            return_value=(None, dummy),
        ):
            resp = client.post(
                "/api/decisions/1/search",
                json={"title": "Breaking Bad", "year": 2008},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["provider"] == "tvdb"

    def test_search_404_unknown_id(self, test_config, tmp_path: Path) -> None:
        """404 — decision id does not exist."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.post(
            "/api/decisions/999/search",
            json={"title": "Test"},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 404

    def test_search_410_superseded(self, test_config, tmp_path: Path) -> None:
        """410 — decision has status 'superseded'."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, status="superseded")
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.post(
            "/api/decisions/1/search",
            json={"title": "Test"},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 410

    def test_search_provider_failure_returns_502(self, test_config, tmp_path: Path) -> None:
        """502 — provider client build failure returns 502."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, media_kind="movie")
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with patch(
            "personalscraper.cli_helpers._build_app_context",
            side_effect=RuntimeError("No API key"),
        ):
            resp = client.post(
                "/api/decisions/1/search",
                json={"title": "Test"},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 502
        assert "unavailable" in resp.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# POST /{id}/resolve
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveDecision:
    """``POST /api/decisions/{id}/resolve`` — 202, 409 lock, 409 concurrent, 403 staging, 404, 410."""

    def test_resolve_returns_202_and_reserves_row(self, test_config, tmp_path: Path) -> None:
        """202 — spawns runner, reserves pipeline_run row, returns run_uid."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with patch("personalscraper.web.routes.decisions._spawn_decision_runner") as mock_spawn:
            resp = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "run_uid" in data
        run_uid = data["run_uid"]
        assert len(run_uid) == 32
        assert all(c in "0123456789abcdef" for c in run_uid)

        # Verify the row was reserved.
        row = _query_pipeline_row(db_path, run_uid)
        assert row is not None
        assert row["outcome"] == "running"
        assert row["kind"] == "maintenance"
        assert row["command"] == "scrape-resolve"

        # Verify spawn args.
        mock_spawn.assert_called_once()
        call_args = mock_spawn.call_args
        assert call_args[0][0] == run_uid
        assert call_args[0][1] == 1  # decision_id
        assert call_args[0][2] == "tmdb"
        assert call_args[0][3] == 550

    def test_resolve_pipeline_lock_held_returns_409(self, test_config, tmp_path: Path) -> None:
        """409 — pipeline.lock is held by a live process."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "pipeline.lock").write_text(str(os.getpid()))

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.post(
            "/api/decisions/1/resolve",
            json={"provider": "tmdb", "provider_id": 550},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Pipeline lock held"

    def test_resolve_concurrent_running_returns_409(self, test_config, tmp_path: Path) -> None:
        """409 — a scrape-resolve for THIS decision with a live pid is already running."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        # A live resolve scoped to decision 1 → a second resolve of decision 1
        # must 409 (per-decision guard, webui-ux phase 4).
        _seed_running_resolve(conn, pid=os.getpid(), decision_id=1)  # Live PID
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.post(
            "/api/decisions/1/resolve",
            json={"provider": "tmdb", "provider_id": 550},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 409
        assert "already resolving" in resp.json()["detail"]

    def test_resolve_different_decision_running_allows_202(self, test_config, tmp_path: Path) -> None:
        """202 — a live resolve of a DIFFERENT decision does NOT block this one.

        Per-decision scoping (webui-ux phase 4): the guard filters running rows
        by ``decision_id``, so a resolve of decision 2 leaves decision 1 free to
        resolve concurrently (both accepted).
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        _seed_decision(conn, decision_id=2, staging_path="/tmp/staging/Other Movie (2023)")
        # A live resolve scoped to decision 2 — must NOT block decision 1.
        _seed_running_resolve(conn, pid=os.getpid(), decision_id=2, run_uid="beef00000002")
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with patch("personalscraper.web.routes.decisions._spawn_decision_runner"):
            resp = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 202

    def test_resolve_concurrent_dead_pid_allows_202(self, test_config, tmp_path: Path) -> None:
        """202 — running resolve row with dead pid is stale → ignored."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        # A dead-pid resolve scoped to decision 1 is stale → the per-decision
        # guard ignores it and the resolve of decision 1 proceeds (202).
        _seed_running_resolve(conn, pid=99999, decision_id=1)  # Dead PID
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with patch("personalscraper.web.routes.decisions._spawn_decision_runner"):
            resp = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 202

    def test_resolve_404_unknown_id(self, test_config, tmp_path: Path) -> None:
        """404 — decision id does not exist."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.post(
            "/api/decisions/999/resolve",
            json={"provider": "tmdb", "provider_id": 550},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 404

    def test_resolve_410_superseded(self, test_config, tmp_path: Path) -> None:
        """410 — decision has status 'superseded'."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, status="superseded")
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.post(
            "/api/decisions/1/resolve",
            json={"provider": "tmdb", "provider_id": 550},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 410

    def test_resolve_spawn_failure_returns_500(self, test_config, tmp_path: Path) -> None:
        """500 — subprocess.Popen raises OSError → finalize error + 500."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with patch("personalscraper.web.routes.decisions.subprocess.Popen", side_effect=OSError("spawn failed")):
            resp = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 500
        assert "spawn" in resp.json()["detail"].lower()

        # Verify the reserved row was finalized 'error'.
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute("SELECT * FROM pipeline_run").fetchall()
        conn2.close()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["outcome"] == "error"


class TestResolveLockReProbe:
    """R11 — pipeline lock re-probe after reservation before spawn."""

    def test_lock_appearing_after_reservation_returns_409_and_finalizes(self, test_config, tmp_path: Path) -> None:
        """409 — lock grabbed between early probe and spawn → finalize 'error'."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with (
            patch(
                "personalscraper.web.routes.decisions.is_lock_held",
                side_effect=[False, True],
            ),
            patch("personalscraper.web.routes.decisions._spawn_decision_runner") as mock_spawn,
        ):
            resp = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert resp.status_code == 409
        assert resp.json()["detail"] == "Pipeline lock held"
        mock_spawn.assert_not_called()

        # The reserved row must be finalized 'error'.
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        rows = conn2.execute("SELECT * FROM pipeline_run").fetchall()
        conn2.close()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["outcome"] == "error"
        assert row["error"] == "Pipeline lock held"
        assert row["ended_at"] is not None

    def test_finalize_raising_on_lock_reprobe_still_returns_409(self, test_config, tmp_path: Path) -> None:
        """SF3 — a raising finalize on the lock-re-probe path must still 409.

        If ``PipelineRunWriter.finalize`` raises (contended DB), the intended 409
        must still fire — the finalize is fail-soft so a DB error cannot swallow
        the HTTP response nor turn a 409 into an untyped 500.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with (
            patch(
                "personalscraper.web.routes.decisions.is_lock_held",
                side_effect=[False, True],
            ),
            patch(
                "personalscraper.web.routes.decisions.PipelineRunWriter.finalize",
                side_effect=sqlite3.OperationalError("database is locked"),
            ),
            patch("personalscraper.web.routes.decisions._spawn_decision_runner") as mock_spawn,
        ):
            resp = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )

        # The intended 409 fires even though finalize raised (fail-soft).
        assert resp.status_code == 409
        assert resp.json()["detail"] == "Pipeline lock held"
        mock_spawn.assert_not_called()

    def test_finalize_raising_on_spawn_failure_still_returns_500(self, test_config, tmp_path: Path) -> None:
        """SF3 — a raising finalize on the spawn-failure path must still 500.

        The spawn OSError already maps to a 500; a subsequent raising finalize
        (fail-soft) must not convert that into a different/untyped error.
        """
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with (
            patch("personalscraper.web.routes.decisions.subprocess.Popen", side_effect=OSError("spawn failed")),
            patch(
                "personalscraper.web.routes.decisions.PipelineRunWriter.finalize",
                side_effect=sqlite3.OperationalError("database is locked"),
            ),
        ):
            resp = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )

        # The intended 500 fires even though finalize raised (fail-soft).
        assert resp.status_code == 500
        assert "spawn" in resp.json()["detail"].lower()


class TestResolveSecondConcurrent:
    """Finding C — second concurrent resolve gets 409."""

    def test_second_concurrent_resolve_returns_409(self, test_config, tmp_path: Path) -> None:
        """409 — first 202, second sees the reserved row → 409."""
        data_dir = test_config.paths.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        with patch("personalscraper.web.routes.decisions._spawn_decision_runner"):
            first = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )
            assert first.status_code == 202

            second = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )

        assert second.status_code == 409
        assert "already resolving" in second.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /{id}/dismiss
# ═══════════════════════════════════════════════════════════════════════════════


class TestDismissDecision:
    """``POST /api/decisions/{id}/dismiss`` — 200, 404, 410, 403 staging."""

    def test_dismiss_returns_200_and_refreshed_status(self, test_config, tmp_path: Path) -> None:
        """200 — dismiss marks the row 'dismissed' and returns the refreshed detail."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, status="pending")
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.post(
            "/api/decisions/1/dismiss",
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dismissed"
        assert data["id"] == 1

        # Verify persisted.
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        row = conn2.execute("SELECT status FROM scrape_decision WHERE id = 1").fetchone()
        conn2.close()
        assert row is not None
        assert row["status"] == "dismissed"

    def test_dismiss_404_unknown_id(self, test_config, tmp_path: Path) -> None:
        """404 — decision id does not exist."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.post(
            "/api/decisions/999/dismiss",
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 404

    def test_dismiss_410_superseded(self, test_config, tmp_path: Path) -> None:
        """410 — decision has status 'superseded'."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, status="superseded")
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        resp = client.post(
            "/api/decisions/1/dismiss",
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 410


# ═══════════════════════════════════════════════════════════════════════════════
# Auth / staging / XRW tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuth:
    """401 — unauthenticated requests to guarded endpoints."""

    @staticmethod
    def _build_guarded_app_without_auth(test_config, tmp_path: Path) -> TestClient:
        """Build an app with the decisions router mounted under auth guard, no login.

        The guarded_api requires a session cookie → 401 on every endpoint.
        """
        from personalscraper.config import Settings as _Settings

        cfg = test_config.model_copy(
            update={
                "paths": test_config.paths.model_copy(update={"data_dir": tmp_path / ".data"}),
                "web": test_config.web.model_copy(update={"username": TEST_USERNAME}),
            },
        )
        settings = _Settings(  # type: ignore[call-arg]
            _env_file=None,
            web_password_hash=TEST_HASH,
            web_jwt_secret=TEST_SECRET,
        )
        app = FastAPI()
        app.state.config = cfg
        app.state.settings = settings

        from personalscraper.web.routes.decisions import router as decisions_router

        _mount_guarded(app, decisions_router)

        return TestClient(app)

    def test_list_unauthenticated_returns_401(self, test_config, tmp_path: Path) -> None:
        """401 — GET / without session cookie."""
        client = self._build_guarded_app_without_auth(test_config, tmp_path)
        resp = client.get("/api/decisions/")
        assert resp.status_code == 401

    def test_detail_unauthenticated_returns_401(self, test_config, tmp_path: Path) -> None:
        """401 — GET /{id} without session cookie."""
        client = self._build_guarded_app_without_auth(test_config, tmp_path)
        resp = client.get("/api/decisions/1")
        assert resp.status_code == 401

    def test_search_unauthenticated_returns_401(self, test_config, tmp_path: Path) -> None:
        """401 — POST /{id}/search without session cookie."""
        client = self._build_guarded_app_without_auth(test_config, tmp_path)
        resp = client.post(
            "/api/decisions/1/search",
            json={"title": "Test"},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 401

    def test_resolve_unauthenticated_returns_401(self, test_config, tmp_path: Path) -> None:
        """401 — POST /{id}/resolve without session cookie."""
        client = self._build_guarded_app_without_auth(test_config, tmp_path)
        resp = client.post(
            "/api/decisions/1/resolve",
            json={"provider": "tmdb", "provider_id": 550},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 401

    def test_dismiss_unauthenticated_returns_401(self, test_config, tmp_path: Path) -> None:
        """401 — POST /{id}/dismiss without session cookie."""
        client = self._build_guarded_app_without_auth(test_config, tmp_path)
        resp = client.post(
            "/api/decisions/1/dismiss",
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 401


class TestXRW:
    """400 — missing ``X-Requested-With`` header on mutating endpoints."""

    def test_search_missing_xrw_returns_400(self, test_config, tmp_path: Path) -> None:
        """400 — POST /{id}/search without X-Requested-With."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client_with_decisions(test_config, tmp_path)

        resp = client.post("/api/decisions/1/search", json={"title": "Test"})
        assert resp.status_code == 400
        assert "X-Requested-With" in resp.json()["detail"]

    def test_resolve_missing_xrw_returns_400(self, test_config, tmp_path: Path) -> None:
        """400 — POST /{id}/resolve without X-Requested-With."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client_with_decisions(test_config, tmp_path)

        resp = client.post(
            "/api/decisions/1/resolve",
            json={"provider": "tmdb", "provider_id": 550},
        )
        assert resp.status_code == 400

    def test_dismiss_missing_xrw_returns_400(self, test_config, tmp_path: Path) -> None:
        """400 — POST /{id}/dismiss without X-Requested-With."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client_with_decisions(test_config, tmp_path)

        resp = client.post("/api/decisions/1/dismiss")
        assert resp.status_code == 400


class TestStagingReadOnly:
    """403 — ``PERSONALSCRAPER_WEB_ROLE=staging`` on write endpoints."""

    def test_resolve_returns_403_when_staging(self, test_config, tmp_path: Path, monkeypatch) -> None:
        """403 — POST /{id}/resolve on staging instance."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.post(
            "/api/decisions/1/resolve",
            json={"provider": "tmdb", "provider_id": 550},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "read-only"

    def test_dismiss_returns_403_when_staging(self, test_config, tmp_path: Path, monkeypatch) -> None:
        """403 — POST /{id}/dismiss on staging instance."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.post(
            "/api/decisions/1/dismiss",
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "read-only"

    def test_search_not_guarded_by_staging(self, test_config, tmp_path: Path, monkeypatch) -> None:
        """200 — POST /{id}/search is read-only → NOT staging-guarded."""
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, media_kind="movie")
        conn.close()

        from personalscraper.scraper.decision_candidate import DecisionCandidate

        dummy = [DecisionCandidate(provider="tmdb", provider_id=1, title="T", year=None, score=1.0)]

        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        with patch(
            "personalscraper.scraper.confidence.match_movie_detailed",
            return_value=(None, dummy),
        ):
            resp = client.post(
                "/api/decisions/1/search",
                json={"title": "Test"},
                headers={"X-Requested-With": "TorrentMate"},
            )

        # Search is read-only — no require_not_staging Depends.
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Edge case: mount verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestDecisionsRouterMount:
    """Verify the decisions router is correctly mounted under the auth perimeter."""

    def test_decisions_router_present(self, test_config, tmp_path: Path) -> None:
        """The decisions router is mounted via _mount_guarded — auth protects all routes."""
        from personalscraper.web.routes.decisions import router as decisions_router

        app, _settings = _build_app(test_config, tmp_path, with_auth=True)
        _mount_guarded(app, decisions_router)
        client = TestClient(app)

        # Without auth, the guarded_api's require_session fires 401.
        resp = client.get("/api/decisions/")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Coherence-study batch B regression tests (2026-07-10)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDecisionStateMachineGuards:
    """F28/F34/F46 — routes reject non-pending resolve/dismiss with a synchronous 409."""

    def _client(self, test_config, tmp_path, seed_status: str):
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, status=seed_status)
        conn.close()
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        return _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

    def test_resolve_already_resolved_returns_409(self, test_config, tmp_path: Path) -> None:
        """A resolve POST on an already-resolved decision → 409 (not a 202 + async error)."""
        client = self._client(test_config, tmp_path, "resolved")
        with patch("personalscraper.web.routes.decisions._spawn_decision_runner") as mock_spawn:
            resp = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )
        assert resp.status_code == 409
        assert "not 'pending'" in resp.json()["detail"]
        mock_spawn.assert_not_called()

    def test_dismiss_already_dismissed_returns_409(self, test_config, tmp_path: Path) -> None:
        """A dismiss POST on an already-dismissed decision → 409."""
        client = self._client(test_config, tmp_path, "dismissed")
        resp = client.post("/api/decisions/1/dismiss", headers={"X-Requested-With": "TorrentMate"})
        assert resp.status_code == 409

    def test_dismiss_resolved_returns_409_preserves_resolution(self, test_config, tmp_path: Path) -> None:
        """Dismissing a resolved decision is refused (409) — the resolution is preserved (F28/F33)."""
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(
            conn,
            decision_id=1,
            status="resolved",
            resolution_json='{"provider":"tmdb","provider_id":9,"via":"pick"}',
        )
        conn.close()
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )
        resp = client.post("/api/decisions/1/dismiss", headers={"X-Requested-With": "TorrentMate"})
        assert resp.status_code == 409
        row = _query_decision_row(db_path, 1)
        assert row["status"] == "resolved"
        assert row["resolution_json"] is not None


class TestResolveViaThreading:
    """F09 — the resolve provenance (via) is threaded into the runner spawn."""

    def test_resolve_passes_via_to_runner(self, test_config, tmp_path: Path) -> None:
        """The via field of ResolveRequest is passed to _spawn_decision_runner."""
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )
        with patch("personalscraper.web.routes.decisions._spawn_decision_runner") as mock_spawn:
            resp = client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550, "via": "search_override"},
                headers={"X-Requested-With": "TorrentMate"},
            )
        assert resp.status_code == 202
        # _spawn_decision_runner(run_uid, decision_id, provider, provider_id, via)
        assert mock_spawn.call_args[0][4] == "search_override"

    def test_resolve_via_defaults_to_pick(self, test_config, tmp_path: Path) -> None:
        """An absent via defaults to 'pick'."""
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1)
        conn.close()
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )
        with patch("personalscraper.web.routes.decisions._spawn_decision_runner") as mock_spawn:
            client.post(
                "/api/decisions/1/resolve",
                json={"provider": "tmdb", "provider_id": 550},
                headers={"X-Requested-With": "TorrentMate"},
            )
        assert mock_spawn.call_args[0][4] == "pick"


class TestListStagingNoGC:
    """F04 — GET /api/decisions does not GC (write) on the read-only staging instance."""

    def test_list_skips_gc_on_staging(self, test_config, tmp_path: Path, monkeypatch) -> None:
        """On staging the GET leaves a missing-path pending row untouched (no write)."""
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        # A pending row whose staging path does NOT exist — GC would supersede it.
        _seed_decision(conn, decision_id=1, status="pending", staging_path="/gone/path")
        conn.close()
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )

        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.get("/api/decisions/?status=pending")
        assert resp.status_code == 200
        # On staging the row must remain pending (no write side-effect).
        row = _query_decision_row(db_path, 1)
        assert row["status"] == "pending"

    def test_list_runs_gc_on_prod(self, test_config, tmp_path: Path, monkeypatch) -> None:
        """On prod the GET GCs a missing-path pending row to superseded."""
        db_path = tmp_path / "library.db"
        conn = _create_library_db(db_path)
        _seed_decision(conn, decision_id=1, status="pending", staging_path="/gone/path")
        conn.close()
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        client = _build_authenticated_client_with_decisions(
            test_config, tmp_path, indexer=test_config.indexer.model_copy(update={"db_path": db_path})
        )
        monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
        resp = client.get("/api/decisions/?status=pending")
        assert resp.status_code == 200
        # On prod the GC supersedes the missing-path row.
        row = _query_decision_row(db_path, 1)
        assert row["status"] == "superseded"
