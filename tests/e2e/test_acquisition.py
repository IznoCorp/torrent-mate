"""End-to-end tests for the acquisition REST surface (acq-watch S7).

Exercises the full CRUD flow against a real FastAPI app (TestClient with
create_app) backed by temp acquire.db + library.db with the full real DDL
(migrations 001+002+003).  All tests carry the ``e2e`` marker and are NOT
run by default — invoke explicitly:

    pytest tests/e2e/test_acquisition.py -v -m e2e

No ``Design:`` or ``Contract:`` markers — acquisition e2e tests do not
participate in the feature-map coverage system.
"""

from __future__ import annotations

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
# Constants
# ---------------------------------------------------------------------------

TEST_USERNAME = "testuser"
TEST_SECRET = "acq-e2e-test-secret-32-chars!!!x"

# ---------------------------------------------------------------------------
# DDL — full real schemas for acquire.db (001+002+003) + library.db
# ---------------------------------------------------------------------------

_ACQUIRE_DDL = """
-- 001_init.sql
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

CREATE INDEX IF NOT EXISTS idx_seed_dispatched_path
    ON seed_obligation (dispatched_path)
    WHERE dispatched_path IS NOT NULL;

CREATE TABLE IF NOT EXISTS ratio_state (
    tracker_name            TEXT    PRIMARY KEY,
    observed_ratio          REAL    NOT NULL DEFAULT 0.0,
    accumulated_seed_time_s INTEGER NOT NULL DEFAULT 0,
    hnr_count               INTEGER NOT NULL DEFAULT 0,
    updated_at              INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);

-- 002_cross_seed.sql
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

-- 003_watch_state.sql
CREATE TABLE IF NOT EXISTS watch_state (
    key   TEXT PRIMARY KEY,
    value REAL NOT NULL
);
"""

_PIPELINE_RUN_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_run (
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

CREATE INDEX IF NOT EXISTS idx_pipeline_run_started ON pipeline_run(started_at);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_acquire_db(db_path: Path) -> None:
    """Create a temp acquire.db with the full real schema (001+002+003).

    Args:
        db_path: Absolute path for the new acquire.db file.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.executescript(_ACQUIRE_DDL)
    conn.commit()
    conn.close()


def _create_library_db(db_path: Path) -> None:
    """Create a temp library.db with the pipeline_run table.

    Args:
        db_path: Absolute path for the new library.db file.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.executescript(_PIPELINE_RUN_DDL)
    conn.commit()
    conn.close()


def _auth_cookies(username: str = TEST_USERNAME, secret: str = TEST_SECRET) -> dict[str, str]:
    """Create a ``tm_session`` cookie dict from a forged JWT.

    Args:
        username: The ``sub`` claim in the JWT.
        secret: The HS256 signing secret.

    Returns:
        A dict suitable for passing as ``cookies=`` to TestClient methods.
    """
    token = create_session_token(username, secret, 24)
    return {"tm_session": token}


def _xrw_headers() -> dict[str, str]:
    """Return headers with the required ``X-Requested-With`` value."""
    return {"X-Requested-With": "TorrentMate"}


def _assert_row_active(acquire_path: Path, row_id: int, expected_active: bool) -> None:
    """Assert the active flag of a followed_series row in the DB.

    Args:
        acquire_path: Path to the temp acquire.db.
        row_id: The row id to check.
        expected_active: Expected active value (True/False).
    """
    conn = sqlite3.connect(str(acquire_path))
    apply_pragmas(conn)
    row = conn.execute("SELECT active FROM followed_series WHERE id = ?", (row_id,)).fetchone()
    conn.close()
    assert row is not None, f"Row {row_id} not found in DB"
    assert bool(row[0]) == expected_active, f"Expected active={expected_active}, got active={bool(row[0])}"


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path, test_config: Any) -> TestClient:
    """Build a TestClient with temp acquire.db + library.db, wired via create_app.

    The synthetic config's ``acquire.db_path`` and ``indexer.db_path`` are
    pointed at temp files so the real store opens them.  ``web.enabled`` is
    set to ``False`` so the lifespan does not attempt Redis connections.

    Args:
        tmp_path: Pytest temporary directory (unique per test function).
        test_config: Synthetic ``Config`` fixture from tests/fixtures/config.py.

    Returns:
        An unauthenticated ``TestClient``.
    """
    cfg = test_config

    # Point both DB paths at temp files.
    acquire_path = tmp_path / "acquire.db"
    cfg.acquire.db_path = acquire_path
    _create_acquire_db(acquire_path)

    indexer_path = tmp_path / "library.db"
    cfg.indexer.db_path = indexer_path
    _create_library_db(indexer_path)

    # Ensure data_dir exists (needed for watcher.paused sentinel probe).
    cfg.paths.data_dir.mkdir(parents=True, exist_ok=True)

    # Disable Redis relay so the lifespan is a no-op.
    cfg.web.enabled = False
    cfg.web.username = TEST_USERNAME

    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        web_jwt_secret=TEST_SECRET,
    )
    app = create_app(cfg, settings)
    return TestClient(app)


@pytest.fixture
def authed_client(client: TestClient) -> TestClient:
    """Return a client with a forged tm_session cookie pre-set.

    Each test that uses this fixture is already authenticated — no login
    round-trip needed.  The cookie is created via ``create_session_token``
    (same as the real auth flow).

    Args:
        client: The unauthenticated fixture above.

    Returns:
        The same TestClient, now with ``cookies`` pre-populated.
    """
    client.cookies = _auth_cookies()  # type: ignore[assignment]
    return client


# ---------------------------------------------------------------------------
# E2E — Full CRUD flow
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestAcquisitionCRUD:
    """Full lifecycle: follow → read → patch → unfollow → verify soft-delete."""

    def test_full_crud_lifecycle(self, authed_client: TestClient, tmp_path: Path) -> None:
        """POST → GET → PATCH cadence → PATCH active → DELETE → verify active=0."""
        client = authed_client
        acquire_path = tmp_path / "acquire.db"

        # ── POST: create follow ──
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 99999, "title": "E2E Test Show"},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, f"POST create: {resp.text}"
        data = resp.json()
        assert data["title"] == "E2E Test Show"
        assert data["media_ref"]["tvdb_id"] == 99999
        assert data["active"] is True
        assert data["wanted_pending"] == 0
        assert isinstance(data["id"], int)
        assert data["id"] > 0
        followed_id: int = data["id"]

        # ── GET /followed: item present ──
        resp = client.get("/api/acquisition/followed")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(item["id"] == followed_id for item in items), f"Created item {followed_id} not in active list"

        # ── GET /followed?active=all: item present ──
        resp = client.get("/api/acquisition/followed?active=all")
        assert resp.status_code == 200
        all_items = resp.json()["items"]
        assert any(item["id"] == followed_id for item in all_items)

        # ── GET /followed?active=inactive: item NOT present ──
        resp = client.get("/api/acquisition/followed?active=inactive")
        assert resp.status_code == 200
        inactive_items = resp.json()["items"]
        assert not any(item["id"] == followed_id for item in inactive_items), (
            "Active item should not appear in inactive list"
        )

        # ── POST duplicate → 409 ──
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 99999, "title": "Duplicate"},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 409, f"POST duplicate: expected 409, got {resp.status_code}"

        # ── PATCH cadence ──
        resp = client.patch(
            f"/api/acquisition/followed/{followed_id}",
            json={"cadence": {"interval_minutes": 120}},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, f"PATCH cadence: {resp.text}"
        assert resp.json()["cadence"] == {"interval_minutes": 120}

        # ── PATCH active=false ──
        resp = client.patch(
            f"/api/acquisition/followed/{followed_id}",
            json={"active": False},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200, f"PATCH active: {resp.text}"
        assert resp.json()["active"] is False

        # Assert DB reflects the toggle.
        _assert_row_active(acquire_path, followed_id, False)

        # ── PATCH active=true (re-activate) ──
        resp = client.patch(
            f"/api/acquisition/followed/{followed_id}",
            json={"active": True},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is True

        # ── DELETE (soft unfollow) ──
        resp = client.delete(
            f"/api/acquisition/followed/{followed_id}",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 204, f"DELETE: expected 204, got {resp.status_code}"
        assert not resp.content

        # Assert DB: row exists with active=0 (soft delete).
        _assert_row_active(acquire_path, followed_id, False)

        # ── POST reactivate (inactive → active) ──
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 99999, "title": "E2E Test Show Reactivated"},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, f"POST reactivate: {resp.text}"
        assert resp.json()["active"] is True
        assert resp.json()["id"] == followed_id, "Reactivated row must reuse the same id"

        # Only one row should exist.
        conn = sqlite3.connect(str(acquire_path))
        apply_pragmas(conn)
        count = conn.execute("SELECT COUNT(*) FROM followed_series").fetchone()[0]
        conn.close()
        assert count == 1, f"Expected 1 row after reactivation, got {count}"

    def test_create_no_title_accepted(self, authed_client: TestClient) -> None:
        """POST without title → 201 (title defaults to empty string)."""
        resp = authed_client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 77777},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["title"] == ""

    def test_create_no_provider_id_returns_422(self, authed_client: TestClient) -> None:
        """POST without any provider ID → 422 (Pydantic validation)."""
        resp = authed_client.post(
            "/api/acquisition/followed",
            json={"title": "No ID"},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 422, resp.text

    def test_patch_unknown_id_returns_404(self, authed_client: TestClient) -> None:
        """PATCH on a non-existent id → 404."""
        resp = authed_client.patch(
            "/api/acquisition/followed/999999",
            json={"active": False},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 404, resp.text

    def test_delete_unknown_id_returns_404(self, authed_client: TestClient) -> None:
        """DELETE on a non-existent id → 404."""
        resp = authed_client.delete(
            "/api/acquisition/followed/999999",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# E2E — Auth + staging guards
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestAcquisitionGuards:
    """Unauthenticated → 401, staging writes → 403, missing XRW → 400."""

    def test_unauth_reads_return_401(self, client: TestClient) -> None:
        """All four GET endpoints require auth."""
        for path in (
            "/api/acquisition/followed",
            "/api/acquisition/wanted",
            "/api/acquisition/obligations",
            "/api/acquisition/status",
        ):
            resp = client.get(path)
            assert resp.status_code == 401, f"{path}: expected 401, got {resp.status_code}"

    def test_unauth_writes_return_401(self, client: TestClient) -> None:
        """All three mutating endpoints require auth."""
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 1, "title": "X"},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 401, f"POST: expected 401, got {resp.status_code}"

        resp = client.patch(
            "/api/acquisition/followed/1",
            json={"active": False},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 401, f"PATCH: expected 401, got {resp.status_code}"

        resp = client.delete(
            "/api/acquisition/followed/1",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 401, f"DELETE: expected 401, got {resp.status_code}"

    def test_write_missing_xrw_returns_400(self, authed_client: TestClient) -> None:
        """Mutating endpoints require X-Requested-With header."""
        resp = authed_client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 1, "title": "No XRW"},
        )
        assert resp.status_code == 400, f"POST no-XRW: expected 400, got {resp.status_code}"

        resp = authed_client.patch(
            "/api/acquisition/followed/1",
            json={"active": False},
        )
        assert resp.status_code == 400, f"PATCH no-XRW: expected 400, got {resp.status_code}"

        resp = authed_client.delete("/api/acquisition/followed/1")
        assert resp.status_code == 400, f"DELETE no-XRW: expected 400, got {resp.status_code}"

    def test_staging_write_returns_403(
        self,
        authed_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Setting PERSONALSCRAPER_WEB_ROLE=staging blocks writes with 403."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")

        resp = authed_client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 1, "title": "Staging"},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403, f"POST staging: expected 403, got {resp.status_code}"

        resp = authed_client.patch(
            "/api/acquisition/followed/1",
            json={"active": False},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403, f"PATCH staging: expected 403, got {resp.status_code}"

        resp = authed_client.delete(
            "/api/acquisition/followed/1",
            headers=_xrw_headers(),
        )
        assert resp.status_code == 403, f"DELETE staging: expected 403, got {resp.status_code}"

    def test_staging_reads_allowed(
        self,
        authed_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Staging role allows GET reads (no require_not_staging on reads)."""
        monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")

        resp = authed_client.get("/api/acquisition/followed")
        assert resp.status_code == 200, f"GET /followed staging: expected 200, got {resp.status_code}"

        resp = authed_client.get("/api/acquisition/wanted")
        assert resp.status_code == 200

        resp = authed_client.get("/api/acquisition/obligations")
        assert resp.status_code == 200

        resp = authed_client.get("/api/acquisition/status")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# E2E — Read endpoints shape checks
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestAcquisitionReadShapes:
    """Each GET endpoint returns the documented response shape."""

    def test_followed_response_shape(self, authed_client: TestClient) -> None:
        """GET /followed returns {items: [...]} with the correct item keys."""
        resp = authed_client.get("/api/acquisition/followed")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_wanted_response_shape(self, authed_client: TestClient) -> None:
        """GET /wanted returns paginated {items, total, page, page_size}."""
        resp = authed_client.get("/api/acquisition/wanted")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert data["page"] == 1

    def test_obligations_response_shape(self, authed_client: TestClient) -> None:
        """GET /obligations returns {items: [...]}."""
        resp = authed_client.get("/api/acquisition/obligations")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_status_response_shape(self, authed_client: TestClient) -> None:
        """GET /status returns {last_successful_run_at, watcher_enabled, recent_runs}."""
        resp = authed_client.get("/api/acquisition/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "last_successful_run_at" in data
        assert "watcher_enabled" in data
        assert "recent_runs" in data
        assert isinstance(data["watcher_enabled"], bool)
        assert isinstance(data["recent_runs"], list)
        # On a fresh DB with no data, last_successful_run_at is null.
        assert data["last_successful_run_at"] is None or isinstance(data["last_successful_run_at"], (int, float))

    def test_wanted_pagination(self, authed_client: TestClient) -> None:
        """GET /wanted supports page and page_size query params."""
        resp = authed_client.get("/api/acquisition/wanted?page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 10


# ---------------------------------------------------------------------------
# E2E — FollowedSeriesItem frozen shape
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestFollowedItemShape:
    """Every FollowedSeriesItem has the documented keys."""

    _EXPECTED_KEYS = {
        "id",
        "title",
        "media_ref",
        "active",
        "cadence",
        "added_at",
        "wanted_pending",
        "quality_profile",
    }

    def test_item_keys_exact(self, authed_client: TestClient, tmp_path: Path) -> None:
        """Create a follow, then assert every key in the response matches."""
        resp = authed_client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 55555, "title": "Shape Test"},
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201
        item = resp.json()
        assert set(item.keys()) == self._EXPECTED_KEYS, f"Item keys {set(item.keys())} != {self._EXPECTED_KEYS}"
        assert isinstance(item["id"], int)
        assert isinstance(item["title"], str)
        assert isinstance(item["active"], bool)
        assert isinstance(item["added_at"], (int, float))
        assert isinstance(item["wanted_pending"], int)
        # media_ref sub-shape.
        mr = item["media_ref"]
        assert set(mr.keys()) == {"tvdb_id", "tmdb_id", "imdb_id"}
        assert mr["tvdb_id"] == 55555


# ---------------------------------------------------------------------------
# E2E — watcher.paused sentinel affects /status
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestAcquisitionStatusSentinel:
    """Watcher paused sentinel toggles watcher_enabled in GET /status."""

    def test_watcher_enabled_default_true(self, authed_client: TestClient) -> None:
        """With no sentinel, watcher_enabled is True."""
        resp = authed_client.get("/api/acquisition/status")
        assert resp.status_code == 200
        assert resp.json()["watcher_enabled"] is True

    def test_watcher_enabled_false_with_sentinel(
        self,
        authed_client: TestClient,
        tmp_path: Path,
        test_config: Any,
    ) -> None:
        """With watcher.paused sentinel present, watcher_enabled is False."""
        paused = test_config.paths.data_dir / "watcher.paused"
        paused.write_text("")
        try:
            resp = authed_client.get("/api/acquisition/status")
            assert resp.status_code == 200
            assert resp.json()["watcher_enabled"] is False
        finally:
            paused.unlink(missing_ok=True)
