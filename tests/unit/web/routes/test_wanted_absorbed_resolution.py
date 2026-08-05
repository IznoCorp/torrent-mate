"""GET /api/acquisition/wanted — the queue FOLLOWS the absorption pointer (#411).

``absorbed`` is not a state of the episode: it is a pointer to the ``wanted`` row
that carries its acquisition (season-grab R5). Serving the pointer verbatim made
four American Dad episodes read « En cours d'acquisition » on 2026-08-05 while both
season packs had been grabbed and the files were already in the library — the
literal prohibition of §13 (« un état qui *pointe* vers autre chose doit suivre le
pointeur, jamais le rapporter tel quel »).

The rule itself lives in
:func:`personalscraper.web.acquisition.states.substitute_absorbed_facts`; these tests
pin that the ROUTE applies it, and that a pointer it cannot follow keeps ``absorbed``
rather than being downgraded into a different lie.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.auth.tokens import create_session_token
from tests.web._web_harness import web_client

# ---------------------------------------------------------------------------
# DDL — base schema (migration 001); the store applies the rest on open.
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_and_migrate(db_path: Path) -> None:
    """Create the base acquire schema, then migrate it to the current one."""
    from personalscraper.acquire.store import ConcreteAcquireStore

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.executescript(_ACQUIRE_DDL)
    conn.commit()
    conn.close()

    store = ConcreteAcquireStore(db_path)
    store._ensure_open()
    store.close()


def _seed_followed(conn: sqlite3.Connection, title: str = "American Dad!", tvdb_id: int = 73141) -> int:
    """Insert one followed series and return its id."""
    cur = conn.execute(
        "INSERT INTO followed_series (media_ref_json, title, active, added_at, kind) VALUES (?, ?, 1, ?, 'show')",
        (json.dumps({"tvdb_id": tvdb_id}), title, int(time.time())),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _seed_wanted(
    conn: sqlite3.Connection,
    followed_id: int,
    *,
    kind: str,
    status: str,
    season: int | None = None,
    episode: int | None = None,
    absorbed_by: int | None = None,
    enqueued_at: int | None = None,
    tvdb_id: int = 73141,
) -> int:
    """Insert one wanted row (post-migration schema) and return its id."""
    cur = conn.execute(
        "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, status, "
        "enqueued_at, absorbed_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            followed_id,
            json.dumps({"tvdb_id": tvdb_id}),
            kind,
            season,
            episode,
            status,
            enqueued_at if enqueued_at is not None else int(time.time()),
            absorbed_by,
        ),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _auth_cookie(secret: str = "testsecret") -> dict[str, str]:
    """Return a ``tm_session`` cookie dict."""
    return {"tm_session": create_session_token("izno", secret, 24)}


def _statuses_by_id(payload: dict) -> dict[int, str]:
    """Map wanted id → the status the route SERVED."""
    return {int(item["id"]): item["status"] for item in payload["items"]}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_real_prime_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize the create-follow priming spawn (never fork in a unit test)."""
    monkeypatch.setattr(
        "personalscraper.web.routes.acquisition_triggers._spawn_prime_runner",
        lambda run_uid, followed_id: os.getpid(),
    )


@pytest.fixture
def acquire_db(test_config, tmp_path: Path) -> Path:
    """Return the path of a migrated, empty acquire.db wired into the config."""
    path = tmp_path / "acquire.db"
    test_config.acquire.db_path = path
    _create_and_migrate(path)
    test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def client(test_config, acquire_db: Path) -> TestClient:
    """Return a TestClient wired onto the migrated acquire.db."""
    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    return web_client(test_config, settings)


# ---------------------------------------------------------------------------
# The reported defect
# ---------------------------------------------------------------------------


def test_absorbed_episode_reads_its_finished_season(client: TestClient, acquire_db: Path) -> None:
    """The 2026-08-05 report: 4 American Dad episodes absorbed by DONE seasons.

    Before the fix the queue served ``absorbed`` for these rows, which the UI
    renders « En cours d'acquisition » — while both packs had been grabbed and
    the four files were already in the library. They must read their season.
    """
    with sqlite3.connect(str(acquire_db)) as conn:
        conn.row_factory = sqlite3.Row
        fid = _seed_followed(conn)
        s15 = _seed_wanted(conn, fid, kind="season", season=15, status="done")
        s17 = _seed_wanted(conn, fid, kind="season", season=17, status="done")
        e21 = _seed_wanted(conn, fid, kind="episode", season=15, episode=21, status="absorbed", absorbed_by=s15)
        e22 = _seed_wanted(conn, fid, kind="episode", season=15, episode=22, status="absorbed", absorbed_by=s15)
        e23 = _seed_wanted(conn, fid, kind="episode", season=17, episode=23, status="absorbed", absorbed_by=s17)
        e24 = _seed_wanted(conn, fid, kind="episode", season=17, episode=24, status="absorbed", absorbed_by=s17)
        conn.commit()

    resp = client.get("/api/acquisition/wanted?page_size=50", cookies=_auth_cookie())
    assert resp.status_code == 200
    served = _statuses_by_id(resp.json())

    assert served[e21] == "done"
    assert served[e22] == "done"
    assert served[e23] == "done"
    assert served[e24] == "done"
    # The season rows themselves are untouched — they already told the truth.
    assert served[s15] == "done"
    assert served[s17] == "done"


@pytest.mark.parametrize("season_status", ["pending", "searching", "grabbed"])
def test_absorbed_episode_follows_a_live_season_too(client: TestClient, acquire_db: Path, season_status: str) -> None:
    """Following the pointer is not « terminal only »: a live season is followed too.

    A fix that only special-cased ``done`` would still lie the day a reswitch
    requeues the season to ``pending`` — the exact 2026-08-04 incident shape.
    """
    with sqlite3.connect(str(acquire_db)) as conn:
        fid = _seed_followed(conn)
        season = _seed_wanted(conn, fid, kind="season", season=15, status=season_status)
        ep = _seed_wanted(conn, fid, kind="episode", season=15, episode=21, status="absorbed", absorbed_by=season)
        conn.commit()

    resp = client.get("/api/acquisition/wanted?page_size=50", cookies=_auth_cookie())
    assert resp.status_code == 200
    assert _statuses_by_id(resp.json())[ep] == season_status


# ---------------------------------------------------------------------------
# The pointer that cannot be followed (D3 — ignorance is not downgraded)
# ---------------------------------------------------------------------------


def test_null_pointer_keeps_absorbed(client: TestClient, acquire_db: Path) -> None:
    """``absorbed_by IS NULL`` → the row keeps ``absorbed``.

    We do not know which season carries it; inventing ``done`` would trade one
    lie for another.
    """
    with sqlite3.connect(str(acquire_db)) as conn:
        fid = _seed_followed(conn)
        ep = _seed_wanted(conn, fid, kind="episode", season=15, episode=21, status="absorbed", absorbed_by=None)
        conn.commit()

    resp = client.get("/api/acquisition/wanted?page_size=50", cookies=_auth_cookie())
    assert resp.status_code == 200
    assert _statuses_by_id(resp.json())[ep] == "absorbed"


def test_dangling_pointer_keeps_absorbed(client: TestClient, acquire_db: Path) -> None:
    """``absorbed_by`` pointing at a row that does not exist → keeps ``absorbed``.

    The column carries no FK (the table is advisory), so a dangling pointer is a
    real possibility, and it is ignorance — not a licence to invent a state.
    """
    with sqlite3.connect(str(acquire_db)) as conn:
        fid = _seed_followed(conn)
        ep = _seed_wanted(conn, fid, kind="episode", season=15, episode=21, status="absorbed", absorbed_by=9999)
        conn.commit()

    resp = client.get("/api/acquisition/wanted?page_size=50", cookies=_auth_cookie())
    assert resp.status_code == 200
    assert _statuses_by_id(resp.json())[ep] == "absorbed"


# ---------------------------------------------------------------------------
# Resolution must not depend on pagination
# ---------------------------------------------------------------------------


def test_season_row_on_another_page_is_still_followed(client: TestClient, acquire_db: Path) -> None:
    """The carrying season row may fall outside the requested page.

    Rows are ordered by ``enqueued_at DESC``; the season here is the OLDEST row,
    so a page of 2 cannot contain it. Resolving from the page alone would silently
    reintroduce the bug for any queue longer than one page.
    """
    with sqlite3.connect(str(acquire_db)) as conn:
        fid = _seed_followed(conn)
        base = int(time.time())
        season = _seed_wanted(conn, fid, kind="season", season=15, status="done", enqueued_at=base - 500)
        ep = _seed_wanted(
            conn,
            fid,
            kind="episode",
            season=15,
            episode=21,
            status="absorbed",
            absorbed_by=season,
            enqueued_at=base,
        )
        _seed_wanted(conn, fid, kind="episode", season=15, episode=22, status="pending", enqueued_at=base - 100)
        conn.commit()

    resp = client.get("/api/acquisition/wanted?page=1&page_size=2", cookies=_auth_cookie())
    assert resp.status_code == 200
    payload = resp.json()
    served = _statuses_by_id(payload)
    assert season not in served, "fixture is wrong: the season row must be off-page"
    assert served[ep] == "done"


# ---------------------------------------------------------------------------
# Non-regression: rows that are not absorbed are untouched
# ---------------------------------------------------------------------------


def test_non_absorbed_rows_pass_through_unchanged(client: TestClient, acquire_db: Path) -> None:
    """Ordinary rows keep their own status — the resolution is scoped to absorption."""
    with sqlite3.connect(str(acquire_db)) as conn:
        fid = _seed_followed(conn)
        pending = _seed_wanted(conn, fid, kind="episode", season=22, episode=5, status="pending")
        grabbed = _seed_wanted(conn, fid, kind="episode", season=22, episode=6, status="grabbed")
        done = _seed_wanted(conn, fid, kind="episode", season=22, episode=7, status="done")
        abandoned = _seed_wanted(conn, fid, kind="episode", season=22, episode=8, status="abandoned")
        conn.commit()

    resp = client.get("/api/acquisition/wanted?page_size=50", cookies=_auth_cookie())
    assert resp.status_code == 200
    served = _statuses_by_id(resp.json())
    assert served[pending] == "pending"
    assert served[grabbed] == "grabbed"
    assert served[done] == "done"
    assert served[abandoned] == "abandoned"
