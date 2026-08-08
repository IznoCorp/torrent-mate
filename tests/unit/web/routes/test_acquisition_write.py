"""Unit tests for acquisition write routes (acq-watch Phase 2).

Covers POST/PATCH/DELETE /api/acquisition/followed, including:
- Create (201), reactivate (201), dedup conflict (409)
- Staging allowed (A18), XRW guard (400)
- PATCH cadence / active toggle
- DELETE soft-unfollow (204)
- 404 for unknown IDs, 422 for missing provider IDs

Uses the FastAPI TestClient with a synthetic Config + temp acquire.db,
mirroring the Phase 1 read test structure.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.acquisition.runner import prime_options_json
from personalscraper.web.auth.tokens import create_session_token
from tests.web._web_harness import web_client

# ---------------------------------------------------------------------------
# DDL (matching real schemas for acquire.db)
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
    """Create a temp acquire.db and apply the full schema."""
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
    active: bool = True,
    tvdb_id: int | None = None,
) -> int:
    """Insert a followed_series row and return its id."""
    import time

    now = int(time.time())
    tid = tvdb_id if tvdb_id is not None else 360000 + idx
    cur = conn.execute(
        "INSERT INTO followed_series (media_ref_json, title, active, added_at) VALUES (?, ?, ?, ?)",
        (json.dumps({"tvdb_id": tid, "tmdb_id": 1000 + idx}), title, 1 if active else 0, now),
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
    """Neutralize the create-follow priming spawn (acq-states phase 6).

    ``POST /followed`` now enqueues an amorce run. Its spawn hook detaches
    ``python -m personalscraper.web.acquisition.runner``, which loads the
    OPERATOR's config — not the synthetic test one — and chains detect →
    search → grab against the production DBs and the trackers. No test may
    trigger that.
    """
    monkeypatch.setattr(
        "personalscraper.web.routes.acquisition_triggers._spawn_prime_runner",
        lambda run_uid, followed_id: os.getpid(),
    )


@pytest.fixture
def client(test_config: Any, tmp_path: Path) -> TestClient:
    """Build a TestClient with temp acquire.db + library.db.

    The synthetic Config is pointed at temp DB paths so the store's
    ``build_acquire_store`` opens real on-disk files.
    """
    config = test_config

    # Point acquire.db at a temp file.
    acquire_path = tmp_path / "acquire.db"
    config.acquire.db_path = acquire_path
    _create_acquire_db(acquire_path)

    # Point library.db at a temp file (needed by app boot).
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


def _assert_row_active(acquire_path: Path, row_id: int, expected_active: bool) -> None:
    """Assert the active flag of a followed_series row in the DB.

    Args:
        acquire_path: Path to the temp acquire.db.
        row_id: The row id to check.
        expected_active: Expected active value.
    """
    conn = sqlite3.connect(str(acquire_path))
    apply_pragmas(conn)
    row = conn.execute("SELECT active FROM followed_series WHERE id = ?", (row_id,)).fetchone()
    conn.close()
    assert row is not None, f"Row {row_id} not found in DB"
    assert bool(row[0]) == expected_active, f"Expected active={expected_active}, got active={bool(row[0])}"


def _assert_cadence_json(acquire_path: Path, row_id: int, expected: str | None) -> None:
    """Assert the cadence_json column of a followed_series row.

    Args:
        acquire_path: Path to the temp acquire.db.
        row_id: The row id to check.
        expected: Expected cadence_json string, or None to assert NULL.
    """
    conn = sqlite3.connect(str(acquire_path))
    apply_pragmas(conn)
    row = conn.execute("SELECT cadence_json FROM followed_series WHERE id = ?", (row_id,)).fetchone()
    conn.close()
    assert row is not None, f"Row {row_id} not found in DB"
    if expected is None:
        assert row[0] is None, f"Expected NULL cadence_json, got {row[0]!r}"
    else:
        assert row[0] == expected, f"Expected cadence_json={expected!r}, got {row[0]!r}"


# ---------------------------------------------------------------------------
# Test cases — POST /api/acquisition/followed
# ---------------------------------------------------------------------------


class TestCreateFollow:
    """POST /api/acquisition/followed — create or reactivate."""

    def test_create_new_returns_201(self, client: TestClient, tmp_path: Path) -> None:
        """Sending a new tvdb_id creates a follow and returns 201."""
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 123, "title": "Test Show"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["title"] == "Test Show"
        assert data["media_ref"]["tvdb_id"] == 123
        assert data["active"] is True
        assert data["id"] > 0
        assert data["wanted_pending"] == 0

        # Assert row exists in DB.
        acquire_path = tmp_path / "acquire.db"
        _assert_row_active(acquire_path, data["id"], True)

    def test_create_captures_card_metadata(self, client: TestClient, tmp_path: Path) -> None:
        """poster_url/overview/year from the search candidate are stored + echoed (OBJ3)."""
        resp = client.post(
            "/api/acquisition/followed",
            json={
                "tvdb_id": 777,
                "title": "Rich Show",
                "poster_url": "https://img.example/poster.jpg",
                "overview": "A great series.",
                "year": 2021,
            },
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["poster_url"] == "https://img.example/poster.jpg"
        assert data["overview"] == "A great series."
        assert data["year"] == 2021

        # Persisted on the followed_series row.
        conn = sqlite3.connect(str(tmp_path / "acquire.db"))
        row = conn.execute(
            "SELECT poster_url, overview, year FROM followed_series WHERE id = ?", (data["id"],)
        ).fetchone()
        conn.close()
        assert row == ("https://img.example/poster.jpg", "A great series.", 2021)

    def test_create_no_title_returns_201(self, client: TestClient, tmp_path: Path) -> None:
        """Sending a tvdb_id without title is accepted (title defaults to empty)."""
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 456},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["title"] == ""
        assert data["media_ref"]["tvdb_id"] == 456
        assert data["active"] is True

    def test_create_with_tmdb_id(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Following a show via tmdb_id resolves and stores its tvdb_id.

        The provider is mocked (deterministic, no network): a show followed by
        tmdb_id gets its TVDB id backfilled so episode detection works.
        """
        from contextlib import contextmanager
        from unittest.mock import MagicMock

        tmdb = MagicMock()
        tmdb.get_tvdb_id.return_value = 424242

        @contextmanager
        def _fake_scoped(_request: Any):  # noqa: ANN401 — test double
            yield tmdb, MagicMock()

        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition.scoped_provider_clients",
            _fake_scoped,
        )
        resp = client.post(
            "/api/acquisition/followed",
            json={"tmdb_id": 999, "title": "TMDB Only"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["media_ref"]["tmdb_id"] == 999
        assert data["media_ref"]["tvdb_id"] == 424242
        assert data["tvdb_unresolved"] is False

    def test_duplicate_active_returns_409(self, client: TestClient, tmp_path: Path) -> None:
        """Following the same active series again returns 409."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        _seed_followed(conn, 1, "Already Active", active=True, tvdb_id=123)
        conn.commit()
        conn.close()

        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 123, "title": "Already Active"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 409, resp.text

    def test_reactivate_inactive_returns_201(self, client: TestClient, tmp_path: Path) -> None:
        """Following an inactive series reactivates it and returns 201."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Was Inactive", active=False, tvdb_id=123)
        conn.commit()
        conn.close()

        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 123, "title": "Was Inactive"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["id"] == fid, f"Expected id={fid}, got {data['id']}"
        assert data["active"] is True

        # Assert DB was updated, not duplicated.
        _assert_row_active(acquire_path, fid, True)
        # Only one row should exist.
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        count = conn.execute("SELECT COUNT(*) FROM followed_series").fetchone()[0]
        conn.close()
        assert count == 1, f"Expected 1 row, got {count}"

    def test_reactivate_refreshes_kind_to_movie(self, client: TestClient, tmp_path: Path) -> None:
        """Re-following an inactive 'show' as a 'movie' must land kind='movie' (§5).

        Regression (prod): the reactivate branch flipped only ``active`` and kept
        the stale kind, so a film that had once been followed as a series stayed
        series-shaped — no movie wanted row, no film lifecycle. The upsert path
        must refresh the kind on reactivation.
        """
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        # Seeded via the helper → kind defaults to 'show'; then deactivated.
        fid = _seed_followed(conn, 1, "Le Robot sauvage", active=False, tvdb_id=999)
        conn.commit()
        conn.close()

        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 999, "title": "Le Robot sauvage", "kind": "movie"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["id"] == fid
        assert data["active"] is True
        assert data["kind"] == "movie", "reactivation must refresh the kind, not keep the stale 'show'"

        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        row = conn.execute("SELECT kind, active FROM followed_series WHERE id = ?", (fid,)).fetchone()
        conn.close()
        assert row == ("movie", 1)

    def test_no_provider_id_returns_422(self, client: TestClient) -> None:
        """Sending no provider IDs returns 422 (Pydantic validation error)."""
        resp = client.post(
            "/api/acquisition/followed",
            json={"title": "No ID"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 422, resp.text

    def test_missing_xrw_header_returns_400(self, client: TestClient) -> None:
        """Omitting the X-Requested-With header returns 400."""
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 123, "title": "Test"},
            cookies=_make_auth_cookie(),
            # No XRW header.
        )
        assert resp.status_code == 400, resp.text

    def test_staging_role_is_allowed_to_create(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A18 : le rôle staging peut créer un suivi — la route d'écriture est ouverte."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 123, "title": "Test"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Test cases — PATCH /api/acquisition/followed/{id}
# ---------------------------------------------------------------------------


class TestUpdateFollow:
    """PATCH /api/acquisition/followed/{id} — update cadence or active."""

    def test_update_cadence_returns_200(self, client: TestClient, tmp_path: Path) -> None:
        """Patching cadence writes cadence_json to the DB."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show", active=True)
        conn.commit()
        conn.close()

        resp = client.patch(
            f"/api/acquisition/followed/{fid}",
            json={"cadence": {"interval_minutes": 120}},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["cadence"] == {"interval_minutes": 120}
        assert data["active"] is True

        _assert_cadence_json(acquire_path, fid, json.dumps({"interval_minutes": 120}))

    def test_update_active_false_returns_200(self, client: TestClient, tmp_path: Path) -> None:
        """Patching active=false soft-deactivates the row."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show", active=True)
        conn.commit()
        conn.close()

        resp = client.patch(
            f"/api/acquisition/followed/{fid}",
            json={"active": False},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["active"] is False

        _assert_row_active(acquire_path, fid, False)

    def test_update_both_active_and_cadence(self, client: TestClient, tmp_path: Path) -> None:
        """Patching both fields updates both simultaneously."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show", active=True)
        conn.commit()
        conn.close()

        resp = client.patch(
            f"/api/acquisition/followed/{fid}",
            json={"active": False, "cadence": {"interval_minutes": 60}},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["active"] is False
        assert data["cadence"] == {"interval_minutes": 60}

        _assert_row_active(acquire_path, fid, False)
        _assert_cadence_json(acquire_path, fid, json.dumps({"interval_minutes": 60}))

    def test_patch_unknown_id_returns_404(self, client: TestClient) -> None:
        """Patching a non-existent id returns 404."""
        resp = client.patch(
            "/api/acquisition/followed/99999",
            json={"active": False},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 404, resp.text

    def test_patch_quality_profile_is_not_accepted(self, client: TestClient, tmp_path: Path) -> None:
        """Sending quality_profile in a PATCH body is ignored (not a field)."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show", active=True)
        conn.commit()
        conn.close()

        # Send quality_profile — Pydantic should ignore it since it's not a field.
        resp = client.patch(
            f"/api/acquisition/followed/{fid}",
            json={"active": True, "quality_profile": {"min_quality": "1080p"}},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # The quality_profile field is NOT updated (ignored by Pydantic).
        # It surfaces whatever was there before (None in our seed).
        assert data["quality_profile"] is None

    def test_patch_missing_xrw_header_returns_400(self, client: TestClient) -> None:
        """Omitting the X-Requested-With header on PATCH returns 400."""
        resp = client.patch(
            "/api/acquisition/followed/1",
            json={"active": False},
            cookies=_make_auth_cookie(),
        )
        assert resp.status_code == 400, resp.text

    def test_staging_role_is_allowed_to_patch(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A18 : le rôle staging peut modifier un suivi (PATCH) — la route d'écriture est ouverte."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test", active=True)
        conn.commit()
        conn.close()

        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.patch(
            f"/api/acquisition/followed/{fid}",
            json={"active": False},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Test cases — DELETE /api/acquisition/followed/{id}
# ---------------------------------------------------------------------------


class TestDeleteFollow:
    """DELETE /api/acquisition/followed/{id} — soft unfollow."""

    def test_delete_really_removes_the_follow(self, client: TestClient, tmp_path: Path) -> None:
        """DELETE removes the row — it is not a disguised pause.

        Regression (operator, 2026-08-08): the route called set_active(False),
        the exact write « Mettre en pause » performs. Two verbs, one effect —
        the removal never happened and the follow reappeared « En pause ».
        """
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show", active=True)
        # A queued row and an in-flight one: the first must go with the follow
        # (nothing should keep searching for it), the second must SURVIVE —
        # its acquisition is real and its history stays readable.
        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, "
            "status, enqueued_at, attempts) VALUES (?, ?, 'episode', 1, 1, 'pending', 0, 0)",
            (fid, '{"tvdb_id": 1}'),
        )
        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, "
            "status, enqueued_at, attempts) VALUES (?, ?, 'episode', 1, 2, 'grabbed', 0, 0)",
            (fid, '{"tvdb_id": 1}'),
        )
        conn.commit()
        conn.close()

        resp = client.delete(
            f"/api/acquisition/followed/{fid}",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 204, resp.text
        assert resp.text == "" or resp.text is None or not resp.content

        check = sqlite3.connect(str(acquire_path))
        try:
            gone = check.execute("SELECT COUNT(*) FROM followed_series WHERE id = ?", (fid,)).fetchone()[0]
            assert gone == 0, "the follow must be REMOVED, not deactivated"
            queued = check.execute(
                "SELECT COUNT(*) FROM wanted WHERE followed_id = ? AND status = 'pending'",
                (fid,),
            ).fetchone()[0]
            assert queued == 0, "nothing may keep searching for a removed follow"
            in_flight = check.execute("SELECT COUNT(*) FROM wanted WHERE status = 'grabbed'").fetchone()[0]
            assert in_flight == 1, "an acquisition already in flight keeps its row"
        finally:
            check.close()

    def test_delete_already_inactive_returns_204(self, client: TestClient, tmp_path: Path) -> None:
        """Deleting an already-inactive series returns 204 (idempotent)."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show", active=False)
        conn.commit()
        conn.close()

        resp = client.delete(
            f"/api/acquisition/followed/{fid}",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 204, resp.text

    def test_delete_unknown_id_returns_404(self, client: TestClient) -> None:
        """Deleting a non-existent id returns 404."""
        resp = client.delete(
            "/api/acquisition/followed/99999",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 404, resp.text

    def test_delete_missing_xrw_header_returns_400(self, client: TestClient) -> None:
        """Omitting the X-Requested-With header on DELETE returns 400."""
        resp = client.delete(
            "/api/acquisition/followed/1",
            cookies=_make_auth_cookie(),
        )
        assert resp.status_code == 400, resp.text

    def test_staging_role_is_allowed_to_delete(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A18 : le rôle staging peut supprimer un suivi (DELETE) — la route d'écriture est ouverte."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test", active=True)
        conn.commit()
        conn.close()

        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.delete(
            f"/api/acquisition/followed/{fid}",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 204, resp.text


# ---------------------------------------------------------------------------
# Test cases — the two per-follow manual triggers (acq-states phase 8)
#
# POST /followed/{id}/search  → « Rechercher »          → command='prime'
# POST /followed/{id}/grab    → « Récupérer maintenant » → command='grab'
# ---------------------------------------------------------------------------


def _seed_follow_directly(tmp_path: Path, title: str = "Grab Me") -> int:
    """Seed a follow straight into acquire.db and return its id.

    Deliberately NOT through ``POST /followed``: creating a follow enqueues its
    amorce (phase 6), which leaves a LIVE ``prime`` row behind — the very row
    the « Rechercher » idempotence guard refuses on. Seeding directly gives each
    test a follow with no run in flight.
    """
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    apply_pragmas(conn)
    fid = _seed_followed(conn, 1, title, active=True)
    conn.commit()
    conn.close()
    return fid


def _insert_live_run(tmp_path: Path, run_uid: str, command: str, options_json: str) -> None:
    """Insert a live (``ended_at`` NULL, own pid) ``pipeline_run`` row."""
    import time

    conn = sqlite3.connect(str(tmp_path / "library.db"))
    apply_pragmas(conn)
    conn.execute(
        "INSERT INTO pipeline_run "
        "(run_uid, trigger, dry_run, started_at, ended_at, outcome, pid, kind, command, options_json) "
        "VALUES (?, 'web', 0, ?, NULL, 'running', ?, 'maintenance', ?, ?)",
        (run_uid, time.time(), os.getpid(), command, options_json),
    )
    conn.commit()
    conn.close()


def _reserved_run(tmp_path: Path, run_uid: str) -> tuple[str, str]:
    """Return ``(command, options_json)`` of the reserved ``pipeline_run`` row."""
    conn = sqlite3.connect(str(tmp_path / "library.db"))
    row = conn.execute("SELECT command, options_json FROM pipeline_run WHERE run_uid = ?", (run_uid,)).fetchone()
    conn.close()
    assert row is not None
    return str(row[0]), str(row[1])


class TestTriggerFollowedSearch:
    """POST /api/acquisition/followed/{id}/search — « Rechercher » (full chain)."""

    def test_trigger_unknown_returns_404(self, client: TestClient) -> None:
        """Triggering a search for an unknown series → 404."""
        resp = client.post(
            "/api/acquisition/followed/99999/search",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 404, resp.text

    def test_trigger_spawns_a_prime_run_and_returns_202(
        self, client: TestClient, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """« Rechercher » reserves a PRIME run — a bare grab would be a silent no-op."""
        spawned: list[tuple[str, int]] = []
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_triggers._spawn_prime_runner",
            lambda run_uid, followed_id: (spawned.append((run_uid, followed_id)), 4242)[1],
        )
        followed_id = _seed_follow_directly(tmp_path)

        resp = client.post(
            f"/api/acquisition/followed/{followed_id}/search",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 202, resp.text
        run_uid = resp.json()["run_uid"]
        assert spawned == [(run_uid, followed_id)]
        # Post-split, the button must run detect → search → grab, not grab alone:
        # on a follow whose episodes read en_attente/non_verifie, grab alone has
        # nothing to claim and would report success having done nothing.
        assert _reserved_run(tmp_path, run_uid) == ("prime", prime_options_json(followed_id))

    def test_trigger_409_only_on_a_live_prime_for_the_same_follow(self, client: TestClient, tmp_path: Path) -> None:
        """The duplicate of the SAME action is the only permitted refusal (§6)."""
        followed_id = _seed_follow_directly(tmp_path)
        _insert_live_run(tmp_path, "live-prime", "prime", prime_options_json(followed_id))

        resp = client.post(
            f"/api/acquisition/followed/{followed_id}/search",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 409, resp.text

    def test_a_live_grab_never_refuses_a_search(self, client: TestClient, tmp_path: Path) -> None:
        """A running « Récupérer maintenant » must not block « Rechercher » (§6)."""
        followed_id = _seed_follow_directly(tmp_path)
        _insert_live_run(tmp_path, "live-grab", "grab", f'{{"followed_id":{followed_id}}}')

        resp = client.post(
            f"/api/acquisition/followed/{followed_id}/search",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 202, resp.text

    def test_trigger_missing_xrw_returns_400(self, client: TestClient) -> None:
        """A trigger without the X-Requested-With header → 400."""
        resp = client.post(
            "/api/acquisition/followed/1/search",
            cookies=_auth_cookies(),
        )
        assert resp.status_code == 400, resp.text

    def test_staging_role_is_allowed_to_search(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A18 : le rôle staging peut déclencher une recherche — la route d'écriture est ouverte."""
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_triggers._spawn_prime_runner",
            lambda run_uid, followed_id: os.getpid(),
        )
        fid = _seed_follow_directly(tmp_path)
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.post(
            f"/api/acquisition/followed/{fid}/search",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 202, resp.text


class TestTriggerFollowedGrab:
    """POST /api/acquisition/followed/{id}/grab — « Récupérer maintenant »."""

    def test_trigger_unknown_returns_404(self, client: TestClient) -> None:
        """Grabbing an unknown series → 404."""
        resp = client.post(
            "/api/acquisition/followed/99999/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 404, resp.text

    def test_trigger_spawns_a_grab_run_and_returns_202(
        self, client: TestClient, tmp_path: Path, monkeypatch: Any
    ) -> None:
        """« Récupérer maintenant » claims what is already takeable — grab alone."""
        spawned: list[tuple[str, int]] = []
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_triggers._spawn_grab_runner",
            lambda run_uid, followed_id: (spawned.append((run_uid, followed_id)), 4242)[1],
        )
        followed_id = _seed_follow_directly(tmp_path)

        resp = client.post(
            f"/api/acquisition/followed/{followed_id}/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 202, resp.text
        run_uid = resp.json()["run_uid"]
        assert spawned == [(run_uid, followed_id)]
        assert _reserved_run(tmp_path, run_uid) == ("grab", f'{{"followed_id":{followed_id}}}')

    def test_trigger_409_when_the_same_grab_is_already_running(self, client: TestClient, tmp_path: Path) -> None:
        """A live grab for the same series is the only refusal (idempotence)."""
        followed_id = _seed_follow_directly(tmp_path)
        _insert_live_run(tmp_path, "live-grab", "grab", f'{{"followed_id":{followed_id}}}')

        resp = client.post(
            f"/api/acquisition/followed/{followed_id}/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 409, resp.text

    def test_a_live_prime_never_refuses_a_grab(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A running amorce must not block « Récupérer maintenant » (§6)."""
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_triggers._spawn_grab_runner",
            lambda run_uid, followed_id: 4242,
        )
        followed_id = _seed_follow_directly(tmp_path)
        _insert_live_run(tmp_path, "live-prime", "prime", prime_options_json(followed_id))

        resp = client.post(
            f"/api/acquisition/followed/{followed_id}/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 202, resp.text

    def test_trigger_missing_xrw_returns_400(self, client: TestClient) -> None:
        """A grab trigger without the X-Requested-With header → 400."""
        resp = client.post(
            "/api/acquisition/followed/1/grab",
            cookies=_auth_cookies(),
        )
        assert resp.status_code == 400, resp.text

    def test_staging_role_is_allowed_to_grab(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A18 : le rôle staging peut déclencher un grab — la route d'écriture est ouverte."""
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_triggers._spawn_grab_runner",
            lambda run_uid, followed_id: os.getpid(),
        )
        fid = _seed_follow_directly(tmp_path)
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.post(
            f"/api/acquisition/followed/{fid}/grab",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 202, resp.text


class TestRunnerSpawnEnvContract:
    """The env each spawner hands the runner (the canonical contract)."""

    def test_prime_spawner_asks_for_the_three_step_chain(self, monkeypatch: Any) -> None:
        """``prime`` must be requested explicitly — the runner defaults to grab."""
        from unittest.mock import MagicMock, patch

        from personalscraper.web.routes import acquisition_triggers

        # Drop the autouse neutralization: THIS test is about the spawner
        # itself, and it stays safe because Popen is mocked below.
        monkeypatch.undo()

        proc = MagicMock()
        proc.pid = 4242
        with patch.object(acquisition_triggers.subprocess, "Popen", return_value=proc) as popen:
            pid = acquisition_triggers._spawn_prime_runner("uid-1", 7)

        assert pid == 4242
        env = popen.call_args.kwargs["env"]
        assert env["PERSONALSCRAPER_ACQ_COMMAND"] == "prime"
        assert env["PERSONALSCRAPER_RUN_UID"] == "uid-1"
        assert env["PERSONALSCRAPER_GRAB_FOLLOWED_ID"] == "7"

    def test_grab_spawner_scopes_the_run_to_one_follow(self, monkeypatch: Any) -> None:
        """``grab`` is the runner default, so only the scope is passed."""
        from unittest.mock import MagicMock, patch

        from personalscraper.web.routes import acquisition_triggers

        # Undo the global anti-spawn guard — this test calls the real
        # _spawn_grab_runner (safe because subprocess.Popen is mocked below).
        monkeypatch.undo()

        proc = MagicMock()
        proc.pid = 4343
        with patch.object(acquisition_triggers.subprocess, "Popen", return_value=proc) as popen:
            pid = acquisition_triggers._spawn_grab_runner("uid-2", 9)

        assert pid == 4343
        env = popen.call_args.kwargs["env"]
        assert env.get("PERSONALSCRAPER_ACQ_COMMAND") in (None, "grab")
        assert env["PERSONALSCRAPER_RUN_UID"] == "uid-2"
        assert env["PERSONALSCRAPER_GRAB_FOLLOWED_ID"] == "9"


# ═══════════════════════════════════════════════════════════════════════════════
# POST /journeys/{info_hash}/rescrape  and  /requeue  (spine-actions, F4)
# ═══════════════════════════════════════════════════════════════════════════════


def _seed_provenance_row(tmp_path: Path, info_hash: str) -> None:
    """Seed a tracked provenance row in the client's acquire.db so by_hash finds it."""
    from personalscraper.acquire.store import build_acquire_store
    from personalscraper.conf.models.acquire import AcquireConfig
    from personalscraper.core.identity import MediaRef

    store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        store.provenance.upsert_grab(
            info_hash, followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1
        )
    finally:
        store.close()


class TestTriggerJourneyRescrape:
    """POST /api/acquisition/journeys/{info_hash}/rescrape — « Re-scraper » (F4)."""

    def test_untracked_hash_returns_404(self, client: TestClient) -> None:
        """A hash with no spine row → 404 (a manual/direct item has nothing to act on)."""
        resp = client.post("/api/acquisition/journeys/nope/rescrape", cookies=_auth_cookies(), headers=_xrw_headers())
        assert resp.status_code == 404, resp.text

    def test_tracked_hash_spawns_and_returns_202(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A tracked item reserves a run + spawns the rescrape runner (202)."""
        spawned: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_triggers._spawn_hash_runner",
            lambda run_uid, action, info_hash: (spawned.append((run_uid, action, info_hash)), 4242)[1],
        )
        _seed_provenance_row(tmp_path, "beef")

        resp = client.post("/api/acquisition/journeys/beef/rescrape", cookies=_auth_cookies(), headers=_xrw_headers())
        assert resp.status_code == 202, resp.text
        run_uid = resp.json()["run_uid"]
        assert spawned == [(run_uid, "rescrape", "beef")]

    def test_missing_xrw_returns_400(self, client: TestClient) -> None:
        """Without the X-Requested-With header → 400 (CSRF guard)."""
        resp = client.post("/api/acquisition/journeys/beef/rescrape", cookies=_auth_cookies())
        assert resp.status_code == 400, resp.text

    def test_staging_role_is_allowed_to_rescrape(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A18 : le rôle staging peut déclencher un re-scrape — la route d'écriture est ouverte."""
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_triggers._spawn_hash_runner",
            lambda run_uid, action, info_hash: os.getpid(),
        )
        _seed_provenance_row(tmp_path, "beef")
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.post("/api/acquisition/journeys/beef/rescrape", cookies=_auth_cookies(), headers=_xrw_headers())
        assert resp.status_code == 202, resp.text


class TestTriggerJourneyRequeue:
    """POST /api/acquisition/journeys/{info_hash}/requeue — « Requeue » (F4)."""

    def test_untracked_hash_returns_404(self, client: TestClient) -> None:
        """A hash with no spine row → 404."""
        resp = client.post("/api/acquisition/journeys/nope/requeue", cookies=_auth_cookies(), headers=_xrw_headers())
        assert resp.status_code == 404, resp.text

    def test_tracked_hash_spawns_and_returns_202(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A tracked item reserves a run + spawns the requeue runner (202)."""
        spawned: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_triggers._spawn_hash_runner",
            lambda run_uid, action, info_hash: (spawned.append((run_uid, action, info_hash)), 7)[1],
        )
        _seed_provenance_row(tmp_path, "cafe")
        resp = client.post("/api/acquisition/journeys/cafe/requeue", cookies=_auth_cookies(), headers=_xrw_headers())
        assert resp.status_code == 202, resp.text
        assert spawned == [(resp.json()["run_uid"], "requeue", "cafe")]

    def test_staging_role_is_allowed_to_requeue(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """A18 : le rôle staging peut déclencher une remise en file — la route d'écriture est ouverte."""
        monkeypatch.setattr(
            "personalscraper.web.routes.acquisition_triggers._spawn_hash_runner",
            lambda run_uid, action, info_hash: os.getpid(),
        )
        _seed_provenance_row(tmp_path, "cafe")
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.post("/api/acquisition/journeys/cafe/requeue", cookies=_auth_cookies(), headers=_xrw_headers())
        assert resp.status_code == 202, resp.text
