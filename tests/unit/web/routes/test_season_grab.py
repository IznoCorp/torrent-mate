"""Unit tests for the season grab endpoint (season-grab feature, phase 5).

Covers POST /api/acquisition/follows/{id}/seasons/{N}/grab:
- Create season wanted (201), duplicate returns existing (idempotent)
- 403 on staging, 404 on unknown follow, 400 on movie follow / season < 1
- Episode absorption (R5) — live episode wanteds are linked to the season row
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.auth.tokens import create_session_token
from tests.web._web_harness import web_client

# ---------------------------------------------------------------------------
# DDL — EXACT match for migration 001_init.sql (base schema).
# The store's `_ensure_open` runs migrations 002–013 atop this.
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
    """Create a temp acquire.db and apply the base schema (pre-migration)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.executescript(_ACQUIRE_DDL)
    conn.commit()
    conn.close()


def _migrate_acquire_db(db_path: Path) -> None:
    """Open the store to trigger migrations (base schema → full schema)."""
    from personalscraper.acquire.store import ConcreteAcquireStore

    store = ConcreteAcquireStore(db_path)
    store._ensure_open()
    store.close()


def _seed_followed(
    conn: sqlite3.Connection,
    idx: int,
    title: str,
    active: bool = True,
    tvdb_id: int | None = None,
    kind: str = "show",
) -> int:
    """Insert a followed_series row and return its id.

    Requires the DB to be migrated (kind column exists after migration 006).
    """
    import time

    now = int(time.time())
    tid = tvdb_id if tvdb_id is not None else 360000 + idx
    cur = conn.execute(
        "INSERT INTO followed_series (media_ref_json, title, active, added_at, kind) "
        "VALUES (?, ?, ?, ?, ?)",
        (json.dumps({"tvdb_id": tid, "tmdb_id": 1000 + idx}), title, 1 if active else 0, now, kind),
    )
    return cur.lastrowid


def _seed_wanted(
    conn: sqlite3.Connection,
    followed_id: int,
    kind: str,
    season: int | None,
    episode: int | None,
    status: str = "pending",
    tvdb_id: int | None = None,
    enqueued_at: int | None = None,
) -> int:
    """Insert a wanted row and return its id.

    Requires the DB to be migrated (season kind / available status after 008/013).
    """
    import time

    now = enqueued_at if enqueued_at is not None else int(time.time())
    tid = tvdb_id if tvdb_id is not None else 360000 + followed_id
    cur = conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, status, enqueued_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            followed_id,
            json.dumps({"tvdb_id": tid, "tmdb_id": 1000 + followed_id}),
            kind,
            season,
            episode,
            status,
            now,
        ),
    )
    return cur.lastrowid


def _make_auth_cookie(username: str = "izno", secret: str = "testsecret") -> dict[str, str]:
    """Create a ``tm_session`` cookie dict for a TestClient request."""
    token = create_session_token(username, secret, 24)
    return {"tm_session": token}


def _xrw_headers() -> dict[str, str]:
    """Return headers with the required ``X-Requested-With`` value."""
    return {"X-Requested-With": "TorrentMate"}


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_real_prime_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize the create-follow priming spawn."""
    monkeypatch.setattr(
        "personalscraper.web.routes.acquisition_triggers._spawn_prime_runner",
        lambda run_uid, followed_id: os.getpid(),
    )


@pytest.fixture
def client(test_config, tmp_path: Path) -> TestClient:
    """Build a TestClient with temp acquire.db + library.db.

    The acquire.db is created with the base schema, then migrated via the
    store so later migrations 002–013 apply (adding kind, season CHECK, etc.).
    """
    config = test_config

    acquire_path = tmp_path / "acquire.db"
    config.acquire.db_path = acquire_path
    _create_acquire_db(acquire_path)
    # Trigger migrations so the DB has all columns/CHECKs (season kind, etc.)
    _migrate_acquire_db(acquire_path)

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
    return web_client(config, settings)


def _auth_cookies() -> dict[str, str]:
    """Return auth cookies for the TestClient."""
    return _make_auth_cookie()


# ---------------------------------------------------------------------------
# Test cases — POST /api/acquisition/follows/{id}/seasons/{N}/grab
# ---------------------------------------------------------------------------


class TestSeasonGrab:
    """POST /api/acquisition/follows/{id}/seasons/{N}/grab — season grab (R4/R5)."""

    def test_creates_season_wanted_and_absorbs_episodes(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        """First grab on a season → 201, season wanted created, episodes absorbed."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show")
        # Seed 3 live episode wanteds in season 1
        _seed_wanted(conn, fid, "episode", 1, 1, status="pending")
        _seed_wanted(conn, fid, "episode", 1, 2, status="searching")
        _seed_wanted(conn, fid, "episode", 1, 3, status="available")
        conn.commit()
        conn.close()

        resp = client.post(
            f"/api/acquisition/follows/{fid}/seasons/1/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["season"] == 1
        assert data["season_wanted_id"] > 0
        assert data["absorbed_count"] == 3

    def test_duplicate_returns_existing(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        """Second grab on the same season → returns existing row with absorbed count."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show")
        _seed_wanted(conn, fid, "episode", 1, 1, status="pending")
        conn.commit()
        conn.close()

        # First grab
        resp1 = client.post(
            f"/api/acquisition/follows/{fid}/seasons/1/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp1.status_code == 201, resp1.text
        data1 = resp1.json()
        wid = data1["season_wanted_id"]
        assert data1["absorbed_count"] == 1

        # Second grab — same season_wanted_id, same absorbed count
        resp2 = client.post(
            f"/api/acquisition/follows/{fid}/seasons/1/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp2.status_code == 201, resp2.text
        data2 = resp2.json()
        assert data2["season_wanted_id"] == wid
        assert data2["absorbed_count"] == 1

    def test_403_on_staging(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Staging role → 403 Forbidden (require_not_staging)."""
        monkeypatch.setattr(
            "personalscraper.web.deps.is_staging_role",
            lambda: True,
        )

        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show")
        conn.commit()
        conn.close()

        resp = client.post(
            f"/api/acquisition/follows/{fid}/seasons/1/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403, resp.text
        assert "read-only" in resp.text

    def test_404_on_unknown_follow(self, client: TestClient) -> None:
        """Unknown followed_id → 404."""
        resp = client.post(
            "/api/acquisition/follows/9999/seasons/1/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 404, resp.text
        assert "not found" in resp.text.lower()

    def test_400_on_movie_follow(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        """Movie follow (kind='movie') → 400."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Movie", kind="movie")
        conn.commit()
        conn.close()

        resp = client.post(
            f"/api/acquisition/follows/{fid}/seasons/1/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 400, resp.text
        assert "TV shows" in resp.text

    def test_400_on_invalid_season(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        """Season < 1 → 400."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show")
        conn.commit()
        conn.close()

        resp = client.post(
            f"/api/acquisition/follows/{fid}/seasons/0/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 400, resp.text
        assert "Season must be >= 1" in resp.text

    def test_400_missing_xrw_header(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        """Missing X-Requested-With header → 400 (require_x_requested_with)."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show")
        conn.commit()
        conn.close()

        resp = client.post(
            f"/api/acquisition/follows/{fid}/seasons/1/grab",
            cookies=_auth_cookies(),
        )
        assert resp.status_code == 400, resp.text
        assert "X-Requested-With" in resp.text

    def test_no_episodes_absorbed_when_none_exist(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        """Season grab on a season with no live episodes → 201, absorbed_count=0."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show")
        conn.commit()
        conn.close()

        resp = client.post(
            f"/api/acquisition/follows/{fid}/seasons/2/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["season"] == 2
        assert data["season_wanted_id"] > 0
        assert data["absorbed_count"] == 0
