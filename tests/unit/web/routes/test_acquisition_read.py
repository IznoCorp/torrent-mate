"""Unit tests for the acquisition read routes (acq-watch Phase 1).

Covers all 4 GET endpoints, auth (401), staging-allowed (200), fail-soft
(DB absent → empty), and pagination/status filtering.

Uses the FastAPI TestClient with a synthetic Config + temp SQLite DBs
(acquire.db + library.db) seeded per test.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from personalscraper.api.torrent._base import TorrentItem
from personalscraper.config import Settings
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.app import create_app
from personalscraper.web.auth.tokens import create_session_token

# ---------------------------------------------------------------------------
# DDL snippets (matching real schemas from acquire/migrations/ + indexer/)
# ---------------------------------------------------------------------------

_ACQUIRE_DDL = """
CREATE TABLE IF NOT EXISTS followed_series (
    id                   INTEGER PRIMARY KEY,
    media_ref_json       TEXT    NOT NULL,
    title                TEXT    NOT NULL,
    active               INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    quality_profile_json TEXT,
    cadence_json         TEXT,
    added_at             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wanted (
    id              INTEGER PRIMARY KEY,
    followed_id     INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json  TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('movie', 'episode')),
    season          INTEGER,
    episode         INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'searching', 'grabbed', 'done', 'abandoned')),
    criteria_json   TEXT,
    enqueued_at     INTEGER NOT NULL,
    last_search_at  INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    grabbed_hash    TEXT
);

CREATE TABLE IF NOT EXISTS seed_obligation (
    id               INTEGER PRIMARY KEY,
    info_hash        TEXT    NOT NULL,
    source_tracker   TEXT    NOT NULL,
    dispatched_path  TEXT,
    min_seed_time_s  INTEGER NOT NULL,
    min_ratio        REAL    NOT NULL,
    added_at         INTEGER NOT NULL,
    satisfied_at     INTEGER,
    breached_at      INTEGER,
    released_at      INTEGER,
    CHECK (min_seed_time_s >= 0 AND min_ratio >= 0)
);

CREATE TABLE IF NOT EXISTS ratio_state (
    tracker_name            TEXT    PRIMARY KEY,
    observed_ratio          REAL    NOT NULL DEFAULT 0.0,
    accumulated_seed_time_s INTEGER NOT NULL DEFAULT 0,
    hnr_count               INTEGER NOT NULL DEFAULT 0,
    updated_at              INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS watch_state (
    key   TEXT PRIMARY KEY,
    value REAL NOT NULL
);
"""

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

CREATE INDEX idx_pipeline_run_started ON pipeline_run(started_at);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_acquire_db(db_path: Path) -> None:
    """Create a temp acquire.db and apply the full schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.executescript(_ACQUIRE_DDL)
    conn.commit()
    conn.close()


def _seed_followed(conn: sqlite3.Connection, idx: int, title: str, active: bool = True) -> int:
    """Insert a followed_series row and return its id."""
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO followed_series (media_ref_json, title, active, added_at) VALUES (?, ?, ?, ?)",
        (f'{{"tvdb_id": {360000 + idx}, "tmdb_id": {1000 + idx}}}', title, 1 if active else 0, now),
    )
    return cur.lastrowid


def _seed_wanted(
    conn: sqlite3.Connection,
    followed_id: int,
    status: str = "pending",
    kind: str = "episode",
    season: int = 1,
    episode: int = 1,
) -> int:
    """Insert a wanted row and return its id."""
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, "
        "status, enqueued_at, attempts) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
        (followed_id, '{"tvdb_id": 360001}', kind, season, episode, status, now),
    )
    return cur.lastrowid


def _seed_obligation(
    conn: sqlite3.Connection,
    info_hash: str,
    tracker: str,
    satisfied_at: int | None = None,
    breached_at: int | None = None,
) -> None:
    """Insert a seed_obligation row."""
    now = int(time.time())
    conn.execute(
        "INSERT INTO seed_obligation (info_hash, source_tracker, min_seed_time_s, "
        "min_ratio, added_at, satisfied_at, breached_at) "
        "VALUES (?, ?, 86400, 1.5, ?, ?, ?)",
        (info_hash, tracker, now, satisfied_at, breached_at),
    )


def _seed_ratio(conn: sqlite3.Connection, tracker: str, ratio: float, seed_s: int) -> None:
    """Insert or replace a ratio_state row."""
    now = int(time.time())
    conn.execute(
        "INSERT OR REPLACE INTO ratio_state (tracker_name, observed_ratio, "
        "accumulated_seed_time_s, hnr_count, updated_at) VALUES (?, ?, ?, 0, ?)",
        (tracker, ratio, seed_s, now),
    )


def _seed_pipeline_run(
    conn: sqlite3.Connection,
    run_uid: str,
    trigger: str,
    outcome: str | None = None,
    offset_s: int = 0,
) -> None:
    """Insert a pipeline_run row with a timestamp offset from now."""
    started_at = time.time() - offset_s
    ended_at = None if outcome is None else started_at + 60
    conn.execute(
        "INSERT INTO pipeline_run (run_uid, trigger, started_at, ended_at, outcome) VALUES (?, ?, ?, ?, ?)",
        (run_uid, trigger, started_at, ended_at, outcome),
    )


def _make_auth_cookie(username: str = "izno", secret: str = "testsecret") -> dict[str, str]:
    """Create a ``tm_session`` cookie dict for a TestClient request."""
    token = create_session_token(username, secret, 24)
    return {"tm_session": token}


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(test_config: Any, tmp_path: Path) -> TestClient:
    """Build a TestClient with temp acquire.db + library.db seeded minimally.

    The synthetic Config is pointed at temp DB paths so route handlers open
    real on-disk files.  The ``data_dir`` sentinel check for watcher.paused
    uses the test_config's ``paths.data_dir``.
    """
    config = test_config

    # Point acquire.db at a temp file (overriding the resolved default).
    acquire_path = tmp_path / "acquire.db"
    config.acquire.db_path = acquire_path
    _create_acquire_db(acquire_path)

    # Point library.db at a temp file.
    indexer_path = tmp_path / "library.db"
    config.indexer.db_path = indexer_path
    conn = sqlite3.connect(str(indexer_path))
    apply_pragmas(conn)
    conn.executescript(_PIPELINE_RUN_DDL)
    conn.commit()
    conn.close()

    data_dir = config.paths.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    app = create_app(config, settings)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestFollowedEndpoint:
    """GET /api/acquisition/followed — list followed series."""

    def test_active_default(self, client: TestClient, tmp_path: Path) -> None:
        """Default (active only) returns active items and excludes inactive ones."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        _seed_followed(conn, 1, "Active Show A", active=True)
        _seed_followed(conn, 2, "Active Show B", active=True)
        fid3 = _seed_followed(conn, 3, "Inactive Show", active=False)
        # Add a pending wanted item for show A.
        _seed_wanted(conn, 1, status="pending", episode=1)
        _seed_wanted(conn, 1, status="searching", episode=2)
        # Add a done wanted item for show A (should NOT count as pending).
        _seed_wanted(conn, 1, status="done", episode=3)
        conn.commit()
        conn.close()

        resp = client.get("/api/acquisition/followed", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        items = data["items"]
        assert len(items) == 2, f"Expected 2 active items, got {len(items)}"

        # Assert shape on first item.
        item_a = next(it for it in items if it["id"] == 1)
        assert item_a["title"] == "Active Show A"
        assert item_a["active"] is True
        assert item_a["media_ref"]["tvdb_id"] == 360001
        assert item_a["media_ref"]["tmdb_id"] == 1001
        assert item_a["wanted_pending"] == 2  # pending + searching
        assert item_a["added_at"] > 0
        # C14: status is derived server-side (active + pending → "pending").
        assert item_a["status"] == "pending"

        # Inactive item must NOT be present.
        ids = {it["id"] for it in items}
        assert fid3 not in ids

    def test_active_all(self, client: TestClient, tmp_path: Path) -> None:
        """``?active=all`` returns all items regardless of active flag."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        _seed_followed(conn, 1, "Active Show", active=True)
        _seed_followed(conn, 2, "Inactive Show", active=False)
        conn.commit()
        conn.close()

        resp = client.get("/api/acquisition/followed?active=all", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["items"]) == 2, f"Expected 2 items, got {len(data['items'])}"

    def test_active_inactive(self, client: TestClient, tmp_path: Path) -> None:
        """``?active=inactive`` returns only inactive items."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        _seed_followed(conn, 1, "Active Show", active=True)
        _seed_followed(conn, 2, "Inactive Show", active=False)
        conn.commit()
        conn.close()

        resp = client.get("/api/acquisition/followed?active=inactive", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["active"] is False

    def test_unauthorized(self, client: TestClient) -> None:
        """No ``tm_session`` cookie → 401."""
        resp = client.get("/api/acquisition/followed")
        assert resp.status_code == 401, resp.text

    def test_staging_allowed(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Staging role → 200 (reads are staging-safe)."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.get("/api/acquisition/followed", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text

    def test_fail_soft_db_absent(self, client: TestClient, tmp_path: Path) -> None:
        """Routes return empty lists when acquire.db is missing, not 500."""
        # Delete the DB.
        acquire_path = tmp_path / "acquire.db"
        acquire_path.unlink()
        resp = client.get("/api/acquisition/followed", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"items": []}


class TestWantedEndpoint:
    """GET /api/acquisition/wanted — paginated wanted queue."""

    def test_pagination_page1(self, client: TestClient, tmp_path: Path) -> None:
        """page=1, page_size=50 returns first page with correct total."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Show", active=True)
        for i in range(55):
            _seed_wanted(conn, fid, status="pending", episode=i + 1)
        conn.commit()
        conn.close()

        resp = client.get(
            "/api/acquisition/wanted?page=1&page_size=50",
            cookies=_make_auth_cookie(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["items"]) == 50
        assert data["total"] == 55
        assert data["page"] == 1
        assert data["page_size"] == 50

    def test_pagination_page2(self, client: TestClient, tmp_path: Path) -> None:
        """page=2 returns the remaining items."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Show", active=True)
        for i in range(55):
            _seed_wanted(conn, fid, status="pending", episode=i + 1)
        conn.commit()
        conn.close()

        resp = client.get(
            "/api/acquisition/wanted?page=2&page_size=50",
            cookies=_make_auth_cookie(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["items"]) == 5

    def test_status_filter(self, client: TestClient, tmp_path: Path) -> None:
        """``?status=pending`` returns only pending items."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Show", active=True)
        _seed_wanted(conn, fid, status="pending", episode=1)
        _seed_wanted(conn, fid, status="pending", episode=2)
        _seed_wanted(conn, fid, status="done", episode=3)
        _seed_wanted(conn, fid, status="abandoned", episode=4)
        conn.commit()
        conn.close()

        resp = client.get(
            "/api/acquisition/wanted?status=pending",
            cookies=_make_auth_cookie(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 2
        assert all(it["status"] == "pending" for it in data["items"])

    def test_fail_soft_db_absent(self, client: TestClient, tmp_path: Path) -> None:
        """Returns empty paginated shape when DB is missing."""
        acquire_path = tmp_path / "acquire.db"
        acquire_path.unlink()
        resp = client.get("/api/acquisition/wanted", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data == {"items": [], "total": 0, "page": 1, "page_size": 50}


class TestObligationsEndpoint:
    """GET /api/acquisition/obligations — seed obligations + ratio join."""

    def test_default_all(self, client: TestClient, tmp_path: Path) -> None:
        """Returns all obligations with LEFT JOIN ratio_state."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        _seed_obligation(conn, "a1b2c3", "lacale")
        _seed_obligation(conn, "d4e5f6", "c411")
        _seed_ratio(conn, "lacale", 2.5, 200000)
        conn.commit()
        conn.close()

        resp = client.get("/api/acquisition/obligations", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        items = data["items"]
        assert len(items) == 2

        # lacale has ratio_state → observed_ratio populated.
        lacale = next(it for it in items if it["source_tracker"] == "lacale")
        assert lacale["observed_ratio"] == 2.5
        assert lacale["accumulated_seed_time_s"] == 200000

        # c411 has NO ratio_state → fields are null.
        c411 = next(it for it in items if it["source_tracker"] == "c411")
        assert c411["observed_ratio"] is None
        assert c411["accumulated_seed_time_s"] is None

    def test_status_pending(self, client: TestClient, tmp_path: Path) -> None:
        """``?status=pending`` returns only unsatisfied + unbreached obligations."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        _seed_obligation(conn, "a1b2c3", "lacale")  # pending
        _seed_obligation(conn, "d4e5f6", "c411", satisfied_at=1000)  # satisfied
        _seed_obligation(conn, "g7h8i9", "c411", breached_at=2000)  # breached
        conn.commit()
        conn.close()

        resp = client.get(
            "/api/acquisition/obligations?status=pending",
            cookies=_make_auth_cookie(),
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["info_hash"] == "a1b2c3"


class TestStatusEndpoint:
    """GET /api/acquisition/status — watcher status + recent runs."""

    def test_full_status(self, client: TestClient, tmp_path: Path) -> None:
        """Returns last_successful_run_at, watcher_enabled, and recent runs."""
        # Seed watch_state in acquire.db.
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        conn.execute(
            "INSERT INTO watch_state (key, value) VALUES (?, ?)",
            ("last_successful_run_at", 1712345678.0),
        )
        conn.commit()
        conn.close()

        # Seed watcher-triggered pipeline_run rows in library.db.
        indexer_path = tmp_path / "library.db"
        conn = sqlite3.connect(str(indexer_path))
        apply_pragmas(conn)
        _seed_pipeline_run(conn, "run-001", "completion", outcome="success", offset_s=3600)
        _seed_pipeline_run(conn, "run-002", "safety_net", outcome="error", offset_s=1800)
        _seed_pipeline_run(conn, "run-003", "manual", offset_s=600)
        # A "web"-triggered run must NOT appear.
        _seed_pipeline_run(conn, "run-004", "web", outcome="success", offset_s=100)
        conn.commit()
        conn.close()

        resp = client.get("/api/acquisition/status", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["last_successful_run_at"] == 1712345678.0
        assert data["watcher_enabled"] is True  # no watcher.paused sentinel

        runs = data["recent_runs"]
        assert len(runs) == 3, f"Expected 3 watcher runs, got {len(runs)}"

        # Most recent first.
        assert runs[0]["run_uid"] == "run-003"  # offset 600s
        assert runs[0]["outcome"] is None
        assert runs[1]["run_uid"] == "run-002"  # offset 1800s
        assert runs[1]["outcome"] == "error"
        assert runs[2]["run_uid"] == "run-001"  # offset 3600s

        # Assert shape.
        for r in runs:
            assert isinstance(r["run_uid"], str)
            assert isinstance(r["started_at"], float)

    def test_watcher_disabled_sentinel(self, client: TestClient, test_config: Any) -> None:
        """``watcher.paused`` sentinel → watcher_enabled=False."""
        data_dir = test_config.paths.data_dir
        (data_dir / "watcher.paused").write_text("")
        resp = client.get("/api/acquisition/status", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        assert resp.json()["watcher_enabled"] is False
        # Clean up so other tests are not affected.
        (data_dir / "watcher.paused").unlink()

    def test_no_watch_state(self, client: TestClient) -> None:
        """Empty watch_state → last_successful_run_at is null."""
        resp = client.get("/api/acquisition/status", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        assert resp.json()["last_successful_run_at"] is None

    def test_fail_soft_db_absent(self, client: TestClient, tmp_path: Path) -> None:
        """Status degrades gracefully when acquire.db is missing."""
        acquire_path = tmp_path / "acquire.db"
        acquire_path.unlink()
        resp = client.get("/api/acquisition/status", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["last_successful_run_at"] is None
        assert isinstance(data["watcher_enabled"], bool)
        assert data["recent_runs"] == []


class TestSearchEndpoint:
    """GET /api/acquisition/search — live add-by-search (OBJ3)."""

    @staticmethod
    def _patch_providers(monkeypatch: pytest.MonkeyPatch) -> None:
        """Patch the provider-clients builder so no real registry is built."""
        import personalscraper.web.routes.acquisition as acq_routes

        monkeypatch.setattr(acq_routes, "_build_provider_clients", lambda _request: (object(), object()))

    def test_search_both_kinds_sorted(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both matchers run; results are kind-tagged and best-score-first."""
        import personalscraper.scraper.confidence as confidence
        from personalscraper.scraper.decision_candidate import DecisionCandidate

        self._patch_providers(monkeypatch)
        movie = DecisionCandidate(
            provider="tmdb",
            provider_id=438631,
            title="Dune",
            year=2021,
            score=0.95,
            poster_url="https://img/dune.jpg",
            overview="Sur Arrakis.",
        )
        tv = DecisionCandidate(
            provider="tvdb",
            provider_id=1,
            title="Dune: Prophecy",
            year=2024,
            score=0.42,
            poster_url=None,
            overview=None,
        )
        monkeypatch.setattr(confidence, "match_movie_detailed", lambda _c, _t, _y: (None, [movie]))
        monkeypatch.setattr(
            confidence,
            "match_tvshow_detailed",
            lambda _tv, _tm, _t, _y: (None, [tv]),
        )

        resp = client.get("/api/acquisition/search?q=dune", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert len(results) == 2
        # Sorted best-score-first: movie (0.95) before tv (0.42).
        assert results[0]["kind"] == "movie"
        assert results[0]["title"] == "Dune"
        assert results[0]["poster_url"] == "https://img/dune.jpg"
        assert results[1]["kind"] == "tv"

    def test_search_kind_filter_movie_only(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """kind=movie only runs the movie matcher (tv matcher must not fire)."""
        import personalscraper.scraper.confidence as confidence
        from personalscraper.scraper.decision_candidate import DecisionCandidate

        self._patch_providers(monkeypatch)
        movie = DecisionCandidate(provider="tmdb", provider_id=1, title="Dune", year=2021, score=0.9)

        def _tv_must_not_run(*_a: object, **_k: object) -> object:
            raise AssertionError("tv matcher must not run for kind=movie")

        monkeypatch.setattr(confidence, "match_movie_detailed", lambda _c, _t, _y: (None, [movie]))
        monkeypatch.setattr(confidence, "match_tvshow_detailed", _tv_must_not_run)

        resp = client.get("/api/acquisition/search?q=dune&kind=movie", cookies=_make_auth_cookie())
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["kind"] == "movie"

    def test_search_requires_auth(self, client: TestClient) -> None:
        """Unauthenticated search is rejected (401)."""
        resp = client.get("/api/acquisition/search?q=dune")
        assert resp.status_code == 401

    def test_search_rejects_empty_query(self, client: TestClient) -> None:
        """An empty q is a 422 (min_length=1)."""
        resp = client.get("/api/acquisition/search?q=", cookies=_make_auth_cookie())
        assert resp.status_code == 422


def _seed_grabbed_wanted(conn: sqlite3.Connection, followed_id: int, info_hash: str, kind: str = "movie") -> int:
    """Insert a wanted row already in status='grabbed' with a torrent hash."""
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, status, enqueued_at, "
        "last_search_at, attempts, grabbed_hash) VALUES (?, ?, ?, 'grabbed', ?, ?, 1, ?)",
        (followed_id, '{"tmdb_id": 1184918}', kind, now, now, info_hash),
    )
    return cur.lastrowid


class TestDownloadsEndpoint:
    """GET /api/acquisition/downloads — live torrent progress (A4)."""

    def test_grabbed_row_joins_to_client_progress(self, client: TestClient, tmp_path: Path) -> None:
        """A grabbed wanted row surfaces its live progress from the torrent client."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 7, "Le Robot sauvage")
        _seed_grabbed_wanted(conn, fid, "ABCDEF0123456789")
        conn.commit()
        conn.close()

        fake_client = MagicMock()
        fake_client.get_by_hashes.return_value = [
            TorrentItem(hash="abcdef0123456789", name="Robot.mkv", size_bytes=999, progress=0.33, state="downloading"),
        ]
        with patch(
            "personalscraper.web.torrent_session.build_active_torrent_client",
            return_value=fake_client,
        ):
            resp = client.get("/api/acquisition/downloads", cookies=_make_auth_cookie())

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["client_available"] is True
        assert len(data["downloads"]) == 1
        d = data["downloads"][0]
        assert d["title"] == "Le Robot sauvage"
        assert d["progress"] == 0.33
        assert d["state"] == "downloading"

    def test_client_outage_is_fail_soft(self, client: TestClient, tmp_path: Path) -> None:
        """A torrent-client failure → 200 with client_available=False (never a 500)."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 7, "Le Robot sauvage")
        _seed_grabbed_wanted(conn, fid, "ABCDEF0123456789")
        conn.commit()
        conn.close()

        with patch(
            "personalscraper.web.torrent_session.build_active_torrent_client",
            side_effect=OSError("connection refused"),
        ):
            resp = client.get("/api/acquisition/downloads", cookies=_make_auth_cookie())

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["client_available"] is False
        assert data["downloads"][0]["state"] == "missing"

    def test_downloads_requires_auth(self, client: TestClient) -> None:
        """Unauthenticated downloads request is rejected (401)."""
        resp = client.get("/api/acquisition/downloads")
        assert resp.status_code == 401


class TestParseRunCountsFallback:
    """Pipeline runs without a semantic ``counts`` dict get a derived summary.

    Live incident (2026-07-15): skip-only watcher runs showed a BLANK result
    cell because only the acquisition CLIs write ``counts``; the pipeline
    steps record native success/skip/error fields that were never surfaced.
    """

    def test_counts_dict_still_wins(self) -> None:
        """A recorded counts mapping is returned verbatim (CLI runs)."""
        from personalscraper.web.routes.acquisition import _parse_run_counts

        steps = json.dumps([{"name": "detect", "counts": {"detected": 3, "enqueued": 2}}])
        assert _parse_run_counts(steps) == {"detected": 3, "enqueued": 2}

    def test_pipeline_steps_derive_summary(self) -> None:
        """Native per-step fields → processed (max) / skipped (ingest) / errors (sum)."""
        from personalscraper.web.routes.acquisition import _parse_run_counts

        steps = json.dumps(
            [
                {"name": "ingest", "success_count": 2, "skip_count": 5, "error_count": 0},
                {"name": "sort", "success_count": 2, "skip_count": 0, "error_count": 1},
                {"name": "scrape", "success_count": 4, "skip_count": 1, "error_count": 0},
            ]
        )
        assert _parse_run_counts(steps) == {"processed": 4, "skipped": 5, "errors": 1}

    def test_skip_only_run_reads_skipped_not_blank(self) -> None:
        """The empty-run shape: 0 processed, N skipped — never None."""
        from personalscraper.web.routes.acquisition import _parse_run_counts

        steps = json.dumps(
            [
                {"name": "ingest", "success_count": 0, "skip_count": 3, "error_count": 0},
                {"name": "sort", "success_count": 0, "skip_count": 0, "error_count": 0},
            ]
        )
        assert _parse_run_counts(steps) == {"processed": 0, "skipped": 3, "errors": 0}

    def test_steps_without_any_fields_stay_none(self) -> None:
        """Steps carrying neither counts nor native fields → None (unchanged)."""
        from personalscraper.web.routes.acquisition import _parse_run_counts

        steps = json.dumps([{"name": "boot"}])
        assert _parse_run_counts(steps) is None


class TestStatusDeferred:
    """GET /status carries the watcher's transient-deferral set (§1)."""

    def test_deferred_listed_with_reason(self, client: TestClient, test_config: Any) -> None:
        """A completed torrent below min_ratio surfaces name + reason."""
        from types import SimpleNamespace

        fake_torrent = SimpleNamespace(
            hash="aaaa0000",
            name="Some.Show.S01E01.1080p",
            size_bytes=1_000,
            ratio=0.2,
            content_path=None,
            tags=[],
        )
        fake_client = MagicMock()
        fake_client.get_completed.return_value = [fake_torrent]

        with (
            patch(
                "personalscraper.web.torrent_session.build_active_torrent_client",
                return_value=fake_client,
            ),
            patch(
                "personalscraper.web.routes.acquisition.__name__",
                "noop",
                create=True,
            ),
        ):
            # min_ratio must be > 0 for the ratio guard; patch the config field.
            client.app.state.config.ingest.min_ratio = 1.0
            resp = client.get("/api/acquisition/status", cookies=_make_auth_cookie())

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["deferred"] == [{"name": "Some.Show.S01E01.1080p", "reason": "ratio_below_threshold"}]

    def test_client_outage_fails_soft_empty(self, client: TestClient) -> None:
        """A torrent-client error yields deferred=[] — never a 500."""
        with patch(
            "personalscraper.web.torrent_session.build_active_torrent_client",
            side_effect=RuntimeError("client down"),
        ):
            resp = client.get("/api/acquisition/status", cookies=_make_auth_cookie())

        assert resp.status_code == 200, resp.text
        assert resp.json()["deferred"] == []
