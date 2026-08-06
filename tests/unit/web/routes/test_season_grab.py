"""Unit tests for the season grab endpoint (season-grab feature, phase 5).

Covers POST /api/acquisition/follows/{id}/seasons/{N}/grab:
- Create season wanted (201), duplicate returns existing (idempotent)
- Staging allowed (A18), 404 on unknown follow, 400 on movie follow / season < 1
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
from personalscraper.web.routes.acquisition_triggers import PrimeResult
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
        "INSERT INTO followed_series (media_ref_json, title, active, added_at, kind) VALUES (?, ?, ?, ?, ?)",
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
        self,
        client: TestClient,
        tmp_path: Path,
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
        self,
        client: TestClient,
        tmp_path: Path,
    ) -> None:
        """Second grab on the same LIVE season → 200, reused=True, no new row."""
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
        assert data1["reused"] is False

        # Second grab — HTTP 200 (nothing created), same id, reused flag set
        resp2 = client.post(
            f"/api/acquisition/follows/{fid}/seasons/1/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp2.status_code == 200, resp2.text
        data2 = resp2.json()
        assert data2["season_wanted_id"] == wid
        assert data2["absorbed_count"] == 1
        assert data2["reused"] is True

        # Mutation-check: still exactly ONE season row in the DB.
        conn = sqlite3.connect(str(acquire_path))
        count = conn.execute(
            "SELECT COUNT(*) FROM wanted WHERE kind = 'season' AND followed_id = ? AND season = 1",
            (fid,),
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_terminal_season_row_does_not_block_a_fresh_grab(
        self,
        client: TestClient,
        tmp_path: Path,
    ) -> None:
        """Review F5: a ``fallback_episodes`` season row is history, not a dedup hit.

        The status-agnostic dedup « reused » the terminal row: 201 + success
        toast, nothing enqueued, forever — with this endpoint being the ONLY
        manual escape hatch after an R6 fallback. A terminal row must yield a
        FRESH season row (201) that absorbs the live episodes.
        """
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show")
        old_season_id = _seed_wanted(conn, fid, "season", 2, None, status="fallback_episodes")
        ep1 = _seed_wanted(conn, fid, "episode", 2, 1, status="pending")
        ep2 = _seed_wanted(conn, fid, "episode", 2, 2, status="searching")
        conn.commit()
        conn.close()

        resp = client.post(
            f"/api/acquisition/follows/{fid}/seasons/2/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["reused"] is False
        assert data["season_wanted_id"] != old_season_id
        assert data["absorbed_count"] == 2

        # Mutation-check on the DB, not just the response.
        conn = sqlite3.connect(str(acquire_path))
        conn.row_factory = sqlite3.Row
        new_row = conn.execute("SELECT status FROM wanted WHERE id = ?", (data["season_wanted_id"],)).fetchone()
        assert new_row is not None and new_row["status"] == "pending"
        old_row = conn.execute("SELECT status, absorbed_by FROM wanted WHERE id = ?", (old_season_id,)).fetchone()
        assert old_row["status"] == "fallback_episodes"  # untouched
        assert old_row["absorbed_by"] is None
        episodes = conn.execute("SELECT id, status, absorbed_by FROM wanted WHERE id IN (?, ?)", (ep1, ep2)).fetchall()
        conn.close()
        assert {(r["status"], r["absorbed_by"]) for r in episodes} == {
            ("absorbed", data["season_wanted_id"]),
        }

    def test_live_season_row_is_reused_with_200(
        self,
        client: TestClient,
        tmp_path: Path,
    ) -> None:
        """A LIVE (open) season row → 200 + reused=True + same id, no new row."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show")
        live_id = _seed_wanted(conn, fid, "season", 3, None, status="grabbed")
        conn.commit()
        conn.close()

        resp = client.post(
            f"/api/acquisition/follows/{fid}/seasons/3/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["reused"] is True
        assert data["season_wanted_id"] == live_id

        conn = sqlite3.connect(str(acquire_path))
        count = conn.execute(
            "SELECT COUNT(*) FROM wanted WHERE kind = 'season' AND followed_id = ? AND season = 3",
            (fid,),
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_grab_season_allowed_on_staging(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A18 : le rôle staging peut déclencher un grab de saison — la route d'écriture est ouverte."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")

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
        assert resp.status_code == 201, resp.text

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
        self,
        client: TestClient,
        tmp_path: Path,
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
        self,
        client: TestClient,
        tmp_path: Path,
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
        self,
        client: TestClient,
        tmp_path: Path,
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
        self,
        client: TestClient,
        tmp_path: Path,
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


# ---------------------------------------------------------------------------
# acq-escalade D3 — the operator's action must START, not wait for cron
# ---------------------------------------------------------------------------


class TestSeasonGrabTriggersARun:
    """A manual season grab must start the pass, not wait up to 12 h for cron (D3).

    ``create_follow`` has always primed the chain; ``grab_season`` did not, so the
    operator's click produced a queued row and no observable run — the UI said
    « en cours d'acquisition » about work nothing had scheduled (product-intent §2).
    Crons are ``search 10 3,15`` / ``grab 20 3,15``: a row created at 12:36 waited
    until 15:10.
    """

    def test_fresh_season_grab_enqueues_a_prime_run(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Creating the season row also enqueues the scoped run, and says so."""
        calls: list[int] = []

        def _fake_enqueue(db_path: object, followed_id: int) -> PrimeResult:
            calls.append(followed_id)
            return PrimeResult(outcome="spawned", run_uid="run-abc")

        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            _fake_enqueue,
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

        assert resp.status_code == 201, resp.text
        assert calls == [fid], "the operator action must start the pass"
        assert resp.json()["run_started"] is True

    def test_reused_live_row_does_not_double_enqueue(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An existing LIVE season row is reused (200) and must not re-spawn a run.

        Re-spawning would be the duplicate-of-the-same-action §6 forbids.
        """
        calls: list[int] = []
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: (calls.append(followed_id), PrimeResult(outcome="spawned", run_uid="run-abc"))[
                1
            ],
        )

        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show")
        conn.commit()
        conn.close()

        client.post(
            f"/api/acquisition/follows/{fid}/seasons/1/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        calls.clear()

        resp = client.post(
            f"/api/acquisition/follows/{fid}/seasons/1/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["reused"] is True
        assert calls == [], "the reused path must not queue a second identical run"
        assert resp.json()["run_started"] is False


class TestSeasonGrabConstitutionSix:
    """§6 — a legitimate operator action never answers « occupé »."""

    def test_never_returns_409_when_a_run_is_already_in_flight(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An already-running prime yields a normal response, never a 409.

        The only refusal §6 permits is idempotence — which ``enqueue_prime_run``
        already implements internally by not duplicating an in-flight prime.
        """
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: PrimeResult(outcome="already_running", run_uid="run-live"),
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

        assert resp.status_code != 409, "§6: a legitimate action is never refused as « occupé »"
        assert resp.status_code == 201, resp.text
        assert resp.json()["run_started"] is True

    def test_failed_enqueue_is_reported_not_hidden(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A dead enqueue is visible in the payload — no success toast on a dead run (§5).

        The season row still exists (the next cron will pick it up), but the
        response must not claim a run started when none did.
        """
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: PrimeResult(outcome="failed", run_uid=None),
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

        assert resp.status_code == 201, resp.text
        assert resp.json()["run_started"] is False
        assert resp.json()["season_wanted_id"] > 0, "the row is enqueued even when the spawn fails"


# ---------------------------------------------------------------------------
# §5 — the manual trigger must SHOW the run, not just claim it started
# ---------------------------------------------------------------------------


class TestSeasonGrabExposesTheRunUid:
    """« Le déclenchement manuel montre le run » (§5) needs the run's identity.

    A boolean « a run started » cannot be followed to its numbered result. The
    response must carry the ``run_uid`` so the UI can poll it to completion and
    report « X détectés, Y disponibles, Z récupérés » — or the real error.
    """

    def test_fresh_grab_returns_the_spawned_run_uid(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The response carries the uid of the run this call spawned."""
        from personalscraper.web.routes.acquisition_triggers import PrimeResult

        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: PrimeResult(outcome="spawned", run_uid="deadbeef"),
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

        assert resp.status_code == 201, resp.text
        assert resp.json()["run_uid"] == "deadbeef"
        assert resp.json()["run_started"] is True

    def test_already_running_returns_the_live_run_uid(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An in-flight prime hands back ITS uid — the operator follows that run.

        §6: the action is not refused, it joins the run already doing the work.
        Returning no uid here would leave the UI unable to show anything.
        """
        from personalscraper.web.routes.acquisition_triggers import PrimeResult

        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: PrimeResult(outcome="already_running", run_uid="live123"),
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

        assert resp.json()["run_uid"] == "live123"
        assert resp.json()["run_started"] is True

    def test_failed_enqueue_returns_no_run_uid(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A dead spawn carries no uid — there is no run to show (§5)."""
        from personalscraper.web.routes.acquisition_triggers import PrimeResult

        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_seasons.enqueue_prime_run",
            lambda db_path, followed_id: PrimeResult(outcome="failed", run_uid=None),
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

        assert resp.json()["run_uid"] is None
        assert resp.json()["run_started"] is False
