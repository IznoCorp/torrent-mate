""":func:`test_reading_follows_never_calls_a_tracker` — NE-DOIT-PAS-8 executable.

Rendering acquisition surfaces must not touch trackers or providers.

NE-DOIT-PAS-8: getting banned from a tracker deprives the operator of the
tool. Availability is read from persisted state; a read path that searches
live would turn every page refresh into tracker traffic.

Instrumentation: the tracker boundary is patched at three layers — the
``TrackerRegistry`` class methods (``search_all`` / ``search_candidates``),
the per-tracker ``TorrentSearchable.search`` protocol, and the HTTP transport
(``requests.Session.send``). All three raise ``AssertionError`` when called,
so a single accidental tracker call fails the test loudly.

Drives ``GET /api/acquisition/followed?active=all`` and
``GET /api/acquisition/followed/{id}/completeness`` through the TestClient
over a seeded store (cached catalog + mixed wanted rows). The movie card path
is also covered (a ``kind='movie'`` follow with a movie wanted row).

Plan drift: the plan places this test under ``tests/integration/``. It lives
in ``tests/unit/web/`` instead because the integration conftest carries heavy
fixtures (staging tree, fake disks, rsync) that are not needed for a pure
TestClient read test. The test uses the same ``client`` fixture pattern as
``test_acquisition_read.py``.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.app import create_app
from personalscraper.web.auth.tokens import create_session_token

# ---------------------------------------------------------------------------
# DDL (full acquire.db schema through migration 008 + indexer pipeline_run)
# ---------------------------------------------------------------------------

_ACQUIRE_DDL = """
PRAGMA user_version = 8;

CREATE TABLE IF NOT EXISTS followed_series (
    id                   INTEGER PRIMARY KEY,
    media_ref_json       TEXT    NOT NULL,
    title                TEXT    NOT NULL,
    active               INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    quality_profile_json TEXT,
    cadence_json         TEXT,
    added_at             INTEGER NOT NULL,
    poster_url           TEXT,
    overview             TEXT,
    year                 INTEGER,
    season_count         INTEGER,
    kind                 TEXT    NOT NULL DEFAULT 'show' CHECK (kind IN ('movie', 'show'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_followed_media_ref
    ON followed_series (media_ref_json);

CREATE TABLE IF NOT EXISTS wanted (
    id              INTEGER PRIMARY KEY,
    followed_id     INTEGER REFERENCES followed_series(id) ON DELETE SET NULL,
    media_ref_json  TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('movie', 'episode')),
    season          INTEGER,
    episode         INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'searching', 'available',
                                      'grabbed', 'done', 'abandoned')),
    criteria_json   TEXT,
    enqueued_at     INTEGER NOT NULL,
    last_search_at  INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    grabbed_hash    TEXT,
    last_search_outcome TEXT,
    last_search_found   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_wanted_pending
    ON wanted (status) WHERE status = 'pending';

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

CREATE TABLE IF NOT EXISTS cross_seed_history (
    source_hash TEXT NOT NULL,
    tracker     TEXT NOT NULL,
    searched_at REAL NOT NULL,
    PRIMARY KEY (source_hash, tracker)
);

CREATE TABLE IF NOT EXISTS cross_seed_quota (
    date  TEXT    NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date)
);

CREATE TABLE IF NOT EXISTS watch_state (
    key   TEXT PRIMARY KEY,
    value REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS aired_episode (
    followed_id INTEGER NOT NULL REFERENCES followed_series(id) ON DELETE CASCADE,
    season      INTEGER NOT NULL,
    episode     INTEGER NOT NULL,
    title       TEXT,
    air_date    TEXT    NOT NULL,
    updated_at  INTEGER NOT NULL,
    PRIMARY KEY (followed_id, season, episode)
);

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version(version) VALUES (1);
INSERT OR IGNORE INTO schema_version(version) VALUES (2);
INSERT OR IGNORE INTO schema_version(version) VALUES (3);
INSERT OR IGNORE INTO schema_version(version) VALUES (4);
INSERT OR IGNORE INTO schema_version(version) VALUES (5);
INSERT OR IGNORE INTO schema_version(version) VALUES (6);
INSERT OR IGNORE INTO schema_version(version) VALUES (7);
INSERT OR IGNORE INTO schema_version(version) VALUES (8);
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
    """Create a temp acquire.db with the full post-migration-008 schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.executescript(_ACQUIRE_DDL)
    conn.commit()
    conn.close()


def _seed_followed(
    conn: sqlite3.Connection,
    idx: int,
    title: str,
    *,
    active: bool = True,
    kind: str = "show",
    tvdb_id: int | None = None,
    tmdb_id: int | None = None,
) -> int:
    """Insert a followed_series row and return its id."""
    now = int(time.time())
    tid = tvdb_id if tvdb_id is not None else 360000 + idx
    mid = tmdb_id if tmdb_id is not None else 1000 + idx
    cur = conn.execute(
        "INSERT INTO followed_series (media_ref_json, title, active, added_at, kind) VALUES (?, ?, ?, ?, ?)",
        (json.dumps({"tvdb_id": tid, "tmdb_id": mid}), title, 1 if active else 0, now, kind),
    )
    return cur.lastrowid


def _seed_aired_episodes(
    conn: sqlite3.Connection,
    followed_id: int,
    season: int,
    count: int,
) -> None:
    """Insert aired_episode rows for one season (episodes 1..count)."""
    now = int(time.time())
    for ep in range(1, count + 1):
        conn.execute(
            "INSERT INTO aired_episode (followed_id, season, episode, title, air_date, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (followed_id, season, ep, f"Episode {ep}", f"2026-01-{ep:02d}", now),
        )


def _seed_wanted(
    conn: sqlite3.Connection,
    followed_id: int,
    *,
    status: str = "pending",
    kind: str = "episode",
    season: int | None = None,
    episode: int | None = None,
    last_search_outcome: str | None = None,
    last_search_found: int | None = None,
) -> int:
    """Insert a wanted row and return its id."""
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, "
        "status, enqueued_at, attempts, last_search_outcome, last_search_found) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
        (
            followed_id,
            '{"tvdb_id": 360001}',
            kind,
            season,
            episode,
            status,
            now,
            last_search_outcome,
            last_search_found,
        ),
    )
    return cur.lastrowid


def _make_auth_cookie(username: str = "izno", secret: str = "testsecret") -> dict[str, str]:
    """Create a ``tm_session`` cookie dict for a TestClient request."""
    token = create_session_token(username, secret, 24)
    return {"tm_session": token}


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(test_config: Any, tmp_path: Path) -> TestClient:
    """Build a TestClient with temp acquire.db + library.db.

    The synthetic Config is pointed at temp DB paths so route handlers open
    real on-disk files.
    """
    config = test_config

    acquire_path = tmp_path / "acquire.db"
    config.acquire.db_path = acquire_path
    _create_acquire_db(acquire_path)

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
# The guard — patches the tracker boundary so ANY call fails loudly
# ---------------------------------------------------------------------------


def _install_tracker_guards(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Patch every tracker/provider boundary to raise on call.

    Three layers (belt and braces):
    1. ``TrackerRegistry.search_all`` + ``search_candidates`` — the two
       entry points the acquisition orchestrator calls.
    2. Per-tracker ``search()`` — individual ``TorrentSearchable`` protocol.
    3. ``requests.Session.send`` — the HTTP transport beneath all providers.

    Returns:
        The list of dotted paths patched (for diagnostics).
    """
    paths: list[str] = []

    def _fail(name: str) -> None:
        def _guard(*args: object, **kwargs: object) -> object:
            raise AssertionError(f"Tracker/provider boundary called during acquisition read: {name}")

        return _guard

    # Layer 1: TrackerRegistry class methods.
    for method in ("search_all", "search_candidates"):
        path = f"personalscraper.api.tracker._registry.TrackerRegistry.{method}"
        monkeypatch.setattr(path, _fail(method))
        paths.append(path)

    # Layer 2: any TorrentSearchable.search implementation that could be
    # called directly (belt — individual tracker search bypassing the
    # registry would still be caught by layer 3).
    for tracker_mod in (
        "personalscraper.api.tracker.c411.C411Client.search",
        "personalscraper.api.tracker.tr4ker.Tr4kerClient.search",
    ):
        try:
            monkeypatch.setattr(tracker_mod, _fail(tracker_mod))
            paths.append(tracker_mod)
        except AttributeError:
            pass  # Tracker not importable (missing config / missing dependency)

    # Layer 3: HTTP transport — braces: any raw HTTP call from a provider.
    monkeypatch.setattr(
        "requests.Session.send",
        _fail("requests.Session.send"),
    )
    paths.append("requests.Session.send")

    return paths


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_reading_follows_never_calls_a_tracker(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rendering acquisition surfaces must not touch trackers or providers.

    NE-DOIT-PAS-8: getting banned from a tracker deprives the operator of the
    tool. Availability is read from persisted state; a read path that searches
    live would turn every page refresh into tracker traffic.

    Seeds a show follow (catalog + wanted rows) AND a movie follow, installs
    the three-layer tracker guard, then drives ``GET /followed?active=all``
    and ``GET /followed/{id}/completeness`` through the TestClient. Both must
    return 200 without ever hitting a tracker.
    """
    # ── Seed ────────────────────────────────────────────────────────────
    acquire_path = tmp_path / "acquire.db"
    conn = sqlite3.connect(str(acquire_path))
    apply_pragmas(conn)

    # A TV show follow with a cached catalog + mixed wanted rows.
    show_id = _seed_followed(conn, 1, "Test Show", kind="show", tvdb_id=360001)
    _seed_aired_episodes(conn, show_id, season=1, count=10)
    # Owned episode (no wanted row — the library owns it → en_mediatheque).
    # Un-owned episode with a takeable candidate (available).
    _seed_wanted(conn, show_id, status="available", episode=1, last_search_outcome="found", last_search_found=3)
    # Un-owned episode in the pipeline (grabbed).
    _seed_wanted(conn, show_id, status="grabbed", episode=2, last_search_outcome="found", last_search_found=1)
    # Un-owned episode searched with nothing takeable (pending — no verdict yet).
    _seed_wanted(conn, show_id, status="pending", episode=3)

    # A movie follow (covers the movie card path).
    movie_id = _seed_followed(conn, 2, "Test Movie", kind="movie", tmdb_id=438631)
    _seed_aired_episodes(conn, movie_id, season=1, count=1)
    _seed_wanted(conn, movie_id, status="available", kind="movie", last_search_outcome="found", last_search_found=1)

    conn.commit()
    conn.close()

    # ── Install tracker guards ───────────────────────────────────────────
    guarded = _install_tracker_guards(monkeypatch)

    # ── Drive GET /followed?active=all ───────────────────────────────────
    resp = client.get(
        "/api/acquisition/followed?active=all",
        cookies=_make_auth_cookie(),
    )
    assert resp.status_code == 200, (
        f"GET /followed?active=all failed ({resp.status_code}): {resp.text}\nTracker guards installed: {guarded}"
    )
    data = resp.json()
    items: list[dict[str, Any]] = data["items"]
    assert len(items) == 2, f"Expected 2 items (show + movie), got {len(items)}"

    # The show card.
    show_item = next(it for it in items if it["id"] == show_id)
    assert show_item["title"] == "Test Show"
    assert show_item["kind"] == "show"
    # With a cached catalog, the counts are known.
    assert show_item["aired_count"] == 10
    assert isinstance(show_item["owned_count"], int)
    assert isinstance(show_item["to_grab_count"], int)
    assert isinstance(show_item["acquiring_count"], int)
    assert isinstance(show_item["pending_count"], int)

    # The movie card.
    movie_item = next(it for it in items if it["id"] == movie_id)
    assert movie_item["title"] == "Test Movie"
    assert movie_item["kind"] == "movie"
    facts = movie_item.get("movie_facts")
    assert facts is not None, "Movie card must carry movie_facts"
    # MovieFacts carries owned + wanted row facts, not 'kind'.
    assert isinstance(facts["owned"], bool)
    assert "wanted_status" in facts

    # ── Drive GET /followed/{id}/completeness ────────────────────────────
    resp = client.get(
        f"/api/acquisition/followed/{show_id}/completeness",
        cookies=_make_auth_cookie(),
    )
    assert resp.status_code == 200, (
        f"GET /followed/{show_id}/completeness failed ({resp.status_code}): {resp.text}\n"
        f"Tracker guards installed: {guarded}"
    )
    comp = resp.json()
    # The completeness response carries seasons.
    assert "seasons" in comp, f"Completeness response must have 'seasons': {list(comp.keys())}"

    # ── Assertion: if we got here, no tracker was called ─────────────────
    # Each guard raises AssertionError on call, so reaching this point
    # proves zero tracker/provider calls across both read endpoints.
    # The explicit assertion below is for documentation — the guards already
    # enforce the invariant.
    assert True, "No tracker call was made — all guards held"
