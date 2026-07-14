"""Unit tests for acquisition write routes (acq-watch Phase 2).

Covers POST/PATCH/DELETE /api/acquisition/followed, including:
- Create (201), reactivate (201), dedup conflict (409)
- Staging guard (403), XRW guard (400)
- PATCH cadence / active toggle
- DELETE soft-unfollow (204)
- 404 for unknown IDs, 422 for missing provider IDs

Uses the FastAPI TestClient with a synthetic Config + temp acquire.db,
mirroring the Phase 1 read test structure.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.app import create_app
from personalscraper.web.auth.tokens import create_session_token

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
    app = create_app(config, settings)
    return TestClient(app)


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

    def test_create_with_tmdb_id(self, client: TestClient, tmp_path: Path) -> None:
        """Following via tmdb_id (no tvdb_id) works."""
        resp = client.post(
            "/api/acquisition/followed",
            json={"tmdb_id": 999, "title": "TMDB Only"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["media_ref"]["tmdb_id"] == 999
        assert data["media_ref"]["tvdb_id"] is None

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

    def test_staging_role_returns_403(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """Setting PERSONALSCRAPER_WEB_ROLE=staging blocks writes with 403."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 123, "title": "Test"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403, resp.text


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

    def test_patch_staging_role_returns_403(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """Setting PERSONALSCRAPER_WEB_ROLE=staging blocks PATCH with 403."""
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
        assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Test cases — DELETE /api/acquisition/followed/{id}
# ---------------------------------------------------------------------------


class TestDeleteFollow:
    """DELETE /api/acquisition/followed/{id} — soft unfollow."""

    def test_delete_soft_unfollow_returns_204(self, client: TestClient, tmp_path: Path) -> None:
        """Deleting an active series soft-unfollows it (active=0) and returns 204."""
        acquire_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        fid = _seed_followed(conn, 1, "Test Show", active=True)
        conn.commit()
        conn.close()

        resp = client.delete(
            f"/api/acquisition/followed/{fid}",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 204, resp.text
        assert resp.text == "" or resp.text is None or not resp.content

        # Row still exists with active=0 (soft delete).
        _assert_row_active(acquire_path, fid, False)

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

    def test_delete_staging_role_returns_403(self, client: TestClient, tmp_path: Path, monkeypatch: Any) -> None:
        """Setting PERSONALSCRAPER_WEB_ROLE=staging blocks DELETE with 403."""
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
        assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Test cases — POST /api/acquisition/followed/{id}/search (OBJ3 manual grab)
# ---------------------------------------------------------------------------


class TestTriggerFollowedSearch:
    """POST /api/acquisition/followed/{id}/search — per-series manual grab."""

    def _create_follow(self, client: TestClient) -> int:
        """Create a followed series via the API and return its id."""
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 555, "title": "Grab Me"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        return int(resp.json()["id"])

    def test_trigger_unknown_returns_404(self, client: TestClient) -> None:
        """Triggering a grab for an unknown series → 404."""
        resp = client.post(
            "/api/acquisition/followed/99999/search",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 404, resp.text

    def test_trigger_spawns_and_returns_202(self, client: TestClient, tmp_path: Path) -> None:
        """A valid trigger reserves a grab run, spawns the runner, returns 202."""
        from unittest.mock import MagicMock, patch

        followed_id = self._create_follow(client)
        proc = MagicMock()
        proc.pid = 4242
        with patch(
            "personalscraper.web.routes.acquisition_triggers.subprocess.Popen",
            return_value=proc,
        ) as popen:
            resp = client.post(
                f"/api/acquisition/followed/{followed_id}/search",
                cookies=_auth_cookies(),
                headers=_xrw_headers(),
            )
        assert resp.status_code == 202, resp.text
        run_uid = resp.json()["run_uid"]
        assert run_uid
        popen.assert_called_once()
        # A grab pipeline_run row was reserved for this series.
        conn = sqlite3.connect(str(tmp_path / "library.db"))
        row = conn.execute("SELECT command, options_json FROM pipeline_run WHERE run_uid = ?", (run_uid,)).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "grab"
        assert row[1] == f'{{"followed_id":{followed_id}}}'

    def test_trigger_409_when_grab_already_running(self, client: TestClient, tmp_path: Path) -> None:
        """A live grab for the same series makes a second trigger 409."""
        import os
        import time

        followed_id = self._create_follow(client)
        # Insert a live (ended_at NULL) grab run for THIS series with our own pid.
        conn = sqlite3.connect(str(tmp_path / "library.db"))
        apply_pragmas(conn)
        conn.execute(
            "INSERT INTO pipeline_run "
            "(run_uid, trigger, dry_run, started_at, ended_at, outcome, pid, kind, command, options_json) "
            "VALUES ('live-grab', 'web', 0, ?, NULL, 'running', ?, 'maintenance', 'grab', ?)",
            (time.time(), os.getpid(), f'{{"followed_id":{followed_id}}}'),
        )
        conn.commit()
        conn.close()

        resp = client.post(
            f"/api/acquisition/followed/{followed_id}/search",
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 409, resp.text

    def test_trigger_missing_xrw_returns_400(self, client: TestClient) -> None:
        """A trigger without the X-Requested-With header → 400."""
        resp = client.post(
            "/api/acquisition/followed/1/search",
            cookies=_auth_cookies(),
        )
        assert resp.status_code == 400, resp.text
