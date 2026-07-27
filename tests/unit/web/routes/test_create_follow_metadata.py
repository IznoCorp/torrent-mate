"""Unit tests for create-follow server-side metadata enrichment (acq-states phase 7.1 — failing-first).

Covers the four scenarios of the §7.1 contract, at the provider-registry boundary
so the assertions pin *behaviour*, not a particular internal function signature.

INTENTIONALLY FAILING — the server does not enrich metadata yet;
``_write_follow_metadata`` early-returns when the client supplies nothing
(poster_url=overview=year=None), and ``create_follow`` never queries a provider.
Phases 7.2 / 7.3 will make these pass.

Reuses the spawn-neutralizing pattern from ``test_create_follow_priming.py``
(the autouse fixture is MANDATORY — without it every POST detaches a real
priming runner against the production DBs).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from personalscraper.config import Settings
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.web.app import create_app
from personalscraper.web.auth.tokens import create_session_token

# ---------------------------------------------------------------------------
# DDL (migration 001 base — the store's apply_migrations adds the rest)
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

# Known provider ID + its metadata (mirrors the Furious incident: tvdb_id=468000).
_TVDB_ID: int = 468000
_PROVIDER_YEAR: int = 2024
_PROVIDER_OVERVIEW: str = "A series about furious things."
_PROVIDER_POSTER: str = "https://artworks.thetvdb.com/banners/posters/468000-1.jpg"

# Distinct client-supplied values so tests 3/4 can tell them apart from provider ones.
_CLIENT_POSTER: str = "https://client.example.com/poster.jpg"
_CLIENT_OVERVIEW: str = "Client-supplied overview."
_CLIENT_YEAR: int = 2023


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_acquire_db(db_path: Path) -> None:
    """Create a temp acquire.db with the base (migration-001) schema.

    The store's ``apply_migrations`` (called by ``build_acquire_store`` at
    first use) adds the later columns — ``kind`` (006), ``poster_url`` /
    ``overview`` / ``year`` / ``season_count`` (005) — on top.  Same contract
    the priming tests rely on.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.executescript(_ACQUIRE_DDL)
    conn.commit()
    conn.close()


def _create_indexer_db(indexer_path: Path) -> None:
    """Create a temp library.db for the priming runner (pipeline_run table)."""
    indexer_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(indexer_path))
    apply_pragmas(conn)
    conn.executescript(_PIPELINE_RUN_DDL)
    conn.commit()
    conn.close()


def _auth_cookies() -> dict[str, str]:
    """Return auth cookies for the TestClient."""
    token = create_session_token("izno", "testsecret", 24)
    return {"tm_session": token}


def _xrw_headers() -> dict[str, str]:
    """Return headers with the required ``X-Requested-With`` value."""
    return {"X-Requested-With": "TorrentMate"}


def _read_follow_row(db_path: Path, follow_id: int) -> dict[str, Any] | None:
    """Read a single ``followed_series`` row as a plain dict (all columns)."""
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM followed_series WHERE id = ?", (follow_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _deactivate_follow(db_path: Path, follow_id: int) -> None:
    """Set active=0 on a follow row so reactivation can be tested."""
    conn = sqlite3.connect(str(db_path))
    apply_pragmas(conn)
    conn.execute("UPDATE followed_series SET active = 0 WHERE id = ?", (follow_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_real_prime_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize the create-follow priming spawn (acq-states phase 6).

    MANDATORY — without this patch every POST triggers
    ``python -m personalscraper.web.acquisition.runner``, which loads the
    OPERATOR's config (not the synthetic test one) and chains detect →
    search → grab against the production DBs and the trackers.

    Mirrors the same fixture in ``test_acquisition_write.py`` and the
    ``spawned_primes`` autouse fixture in ``test_create_follow_priming.py``.
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

    # Point acquire.db at a temp file (same pattern as test_acquisition_write.py).
    acquire_path = tmp_path / "acquire.db"
    config.acquire.db_path = acquire_path
    _create_acquire_db(acquire_path)

    # Point library.db at a temp file (needed by app boot + priming writes).
    indexer_path = tmp_path / "library.db"
    config.indexer.db_path = indexer_path
    _create_indexer_db(indexer_path)

    data_dir = config.paths.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    app = create_app(config, settings)
    return TestClient(app)


@pytest.fixture
def mock_provider_boundary(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch ``_build_provider_clients`` with a fake that can answer TVDB lookups.

    Returns the MagicMock wrapping the patched function so tests can assert
    on ``.called`` / ``.call_count``.

    The fake TVDB client answers ``get_series(tvdb_id)`` for the known ID
    with a minimal stand-in carrying ``year``, ``overview``, and ``images``
    (a poster ``ArtworkItem``).  When the server calls the provider, the
    fake's fields are the ones that must land in the DB row.
    """
    import personalscraper.web.routes.acquisition as acq_routes

    class _FakeArtwork:
        """Minimal stand-in for :class:`personalscraper.api.metadata._base.ArtworkItem`."""

        def __init__(self, type_: str, url: str) -> None:
            self.type = type_
            self.url = url

    class _FakeMediaDetails:
        """Minimal stand-in for :class:`personalscraper.api.metadata._base.MediaDetails`.

        Carries the three fields the enrichment function will extract:
        ``images`` (list of ArtworkItem → poster_url), ``overview``, and ``year``.
        """

        def __init__(self, year: int | None, overview: str, poster_url: str) -> None:
            self.year = year
            self.overview = overview
            self.images = [_FakeArtwork("poster", poster_url)] if poster_url else []

    class _FakeTvdbClient:
        """Fake TVDB client — answers ``get_series`` for the known ID."""

        def get_series(self, series_id: int) -> _FakeMediaDetails | None:  # pyright: ignore[reportReturnType]
            if series_id == _TVDB_ID:
                return _FakeMediaDetails(_PROVIDER_YEAR, _PROVIDER_OVERVIEW, _PROVIDER_POSTER)
            return None

    fake_tmdb = MagicMock()
    fake_tvdb = _FakeTvdbClient()
    mock = MagicMock(return_value=(fake_tmdb, fake_tvdb))
    monkeypatch.setattr(acq_routes, "_build_provider_clients", mock)
    return mock


# ---------------------------------------------------------------------------
# Test cases — POST /api/acquisition/followed metadata enrichment
# ---------------------------------------------------------------------------


class TestCreateFollowMetadata:
    """POST /api/acquisition/followed — server-side metadata enrichment (§7.1)."""

    def test_follow_added_by_tvdb_id_alone_gets_server_side_metadata(
        self,
        client: TestClient,
        tmp_path: Path,
        mock_provider_boundary: MagicMock,
    ) -> None:
        """Adding by bare TVDB id must still yield poster + overview + year.

        Reproduces the founding incident: Furious was added through the manual
        by-ID form, which posts ``{tvdb_id, kind, title}`` and nothing else,
        so ``_write_follow_metadata`` early-returned on three NULLs and the
        card stayed posterless forever — while TVDB exposed six posters for
        that very series.
        """
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": _TVDB_ID, "kind": "show", "title": "Furious"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        follow_id: int = data["id"]
        assert follow_id > 0

        # The DB row must carry server-fetched metadata.  FAILS TODAY:
        # _write_follow_metadata early-returns on three Nones, so
        # poster_url / overview / year stay NULL.
        row = _read_follow_row(tmp_path / "acquire.db", follow_id)
        assert row is not None
        assert row["poster_url"] == _PROVIDER_POSTER, (
            f"Expected poster_url={_PROVIDER_POSTER!r} (server-fetched), "
            f"got {row['poster_url']!r} — _write_follow_metadata early-return"
        )
        assert row["overview"] == _PROVIDER_OVERVIEW, (
            f"Expected overview={_PROVIDER_OVERVIEW!r} (server-fetched), "
            f"got {row['overview']!r} — _write_follow_metadata early-return"
        )
        assert row["year"] == _PROVIDER_YEAR, (
            f"Expected year={_PROVIDER_YEAR} (server-fetched), "
            f"got {row['year']!r} — _write_follow_metadata early-return"
        )

    def test_provider_outage_does_not_fail_follow_creation(
        self,
        client: TestClient,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Metadata enrichment is a nicety; the follow itself must still be created."""
        caplog.set_level(logging.WARNING)

        import personalscraper.web.routes.acquisition as acq_routes

        def _provider_boom(_request: Any) -> tuple[object, object]:
            raise RuntimeError("TVDB API is unreachable")

        monkeypatch.setattr(acq_routes, "_build_provider_clients", _provider_boom)

        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": _TVDB_ID, "kind": "show", "title": "Furious"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        # The follow must still be created (fail-soft: provider outage never
        # blocks the 201).
        assert resp.status_code == 201, resp.text
        data = resp.json()
        follow_id: int = data["id"]
        assert follow_id > 0

        # The DB row exists with NULL metadata — the follow itself survived.
        row = _read_follow_row(tmp_path / "acquire.db", follow_id)
        assert row is not None
        assert row["poster_url"] is None, "Metadata must be NULL when provider fails"
        assert row["overview"] is None, "Metadata must be NULL when provider fails"
        assert row["year"] is None, "Metadata must be NULL when provider fails"

        # FAILS TODAY: no provider call happens → no warning is logged.
        # The enrichment path doesn't exist yet, so nothing catches + logs
        # the exception.
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) > 0, (
            "A provider outage must be logged at WARNING level or above "
            "(fail-soft: the follow succeeds, the failure is loud). "
            "FAILS TODAY: no provider call → no warning logged."
        )

    def test_client_supplied_candidate_wins_over_provider(
        self,
        client: TestClient,
        tmp_path: Path,
        mock_provider_boundary: MagicMock,
    ) -> None:
        """POST carries poster_url/overview/year → row keeps the client values.

        The provider boundary is NOT called — the operator validated the search
        candidate visually; re-querying the provider wastes an API call and
        risks a wrong result (provider search vs provider-by-id are different
        endpoints).
        """
        resp = client.post(
            "/api/acquisition/followed",
            json={
                "tvdb_id": _TVDB_ID,
                "kind": "show",
                "title": "Furious",
                "poster_url": _CLIENT_POSTER,
                "overview": _CLIENT_OVERVIEW,
                "year": _CLIENT_YEAR,
            },
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        follow_id: int = data["id"]
        assert follow_id > 0

        # The DB row must carry the CLIENT values, NOT the provider values.
        row = _read_follow_row(tmp_path / "acquire.db", follow_id)
        assert row is not None
        assert row["poster_url"] == _CLIENT_POSTER, f"Client poster_url must win; got {row['poster_url']!r}"
        assert row["overview"] == _CLIENT_OVERVIEW, f"Client overview must win; got {row['overview']!r}"
        assert row["year"] == _CLIENT_YEAR, f"Client year must win; got {row['year']!r}"

        # The provider boundary MUST NOT be called — the client supplied the
        # candidate.  PASSES today: create_follow does not call the provider
        # at all.  Must still pass after 7.2 adds the enrichment path.
        assert mock_provider_boundary.call_count == 0, (
            "Provider boundary must NOT be called when the client supplies a candidate"
        )

        # The response echoes the client values.
        assert data["poster_url"] == _CLIENT_POSTER
        assert data["overview"] == _CLIENT_OVERVIEW
        assert data["year"] == _CLIENT_YEAR

    def test_reactivation_backfills_missing_metadata(
        self,
        client: TestClient,
        tmp_path: Path,
        mock_provider_boundary: MagicMock,
    ) -> None:
        """Reactivating an inactive follow must backfill its NULL metadata too.

        Reactivation is the same POST endpoint as creation — an inactive follow
        matched by provider ID is set active=True.  The enrichment must run on
        both the new-follow and the reactivation branches.
        """
        acquire_db = tmp_path / "acquire.db"

        # Step 1: Create a follow (without metadata — by-ID form).
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": _TVDB_ID, "kind": "show", "title": "Furious"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        follow_id: int = resp.json()["id"]

        # Sanity: the follow was created without metadata (current behaviour).
        row = _read_follow_row(acquire_db, follow_id)
        assert row is not None
        assert row["poster_url"] is None, "Sanity: first POST must leave poster NULL"

        # Step 2: Deactivate it — simulates the operator having unfollowed.
        _deactivate_follow(acquire_db, follow_id)

        # Reset the mock call count.  (The first POST didn't call the provider
        # either, but we want a clean baseline for the reactivation assertion.)
        mock_provider_boundary.reset_mock()

        # Step 3: Reactivate — same POST payload, no metadata in body.
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": _TVDB_ID, "kind": "show", "title": "Furious"},
            cookies=_auth_cookies(),
            headers=_xrw_headers(),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["id"] == follow_id, "Reactivated — must reuse the same row"

        # FAILS TODAY: the reactivation branch calls _write_follow_metadata
        # with the body (no poster_url/overview/year), which early-returns.
        row = _read_follow_row(acquire_db, follow_id)
        assert row is not None
        assert row["poster_url"] == _PROVIDER_POSTER, f"Reactivation must backfill poster; got {row['poster_url']!r}"
        assert row["overview"] == _PROVIDER_OVERVIEW, f"Reactivation must backfill overview; got {row['overview']!r}"
        assert row["year"] == _PROVIDER_YEAR, f"Reactivation must backfill year; got {row['year']!r}"
