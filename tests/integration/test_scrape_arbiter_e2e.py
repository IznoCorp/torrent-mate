"""End-to-end integration tests for the scrape-arbiter resolve flow.

Sub-phase 5.1 — exercises the full ``scrape-resolve`` CLI command against a
real tmp library.db and a real staging folder, with provider clients mocked
with realistic ``MediaDetails`` payloads.  Asserts the NFO file is written,
the decision row is ``resolved`` with ``resolution_json``, and artwork calls
are attempted.

Mirrors the harness of ``tests/integration/scraper/test_chain_exhaustion_e2e.py``
(staging folder + DB + CliRunner) and the provider/mock patterns of
``tests/cli/test_scrape_resolve.py`` (load_config patched, per_step_boundary
context-manager factory, golden-fixture payloads).

Negative path: provider raises → exit 1, decision stays ``'pending'``.
"""

from __future__ import annotations

import json
import sqlite3 as _sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.cli import app
from personalscraper.core.sqlite._pragmas import apply_pragmas
from tests.conftest import make_cli_runner

# ---------------------------------------------------------------------------
# Golden fixture — realistic TMDB movie payload (same source as CLI tests)
# ---------------------------------------------------------------------------

REALISTIC_MOVIE_PAYLOAD: dict[str, Any] = {
    "id": 550,
    "title": "Fight Club",
    "original_title": "Fight Club",
    "overview": (
        "A ticking-time-bomb insomniac and a slippery soap salesman "
        "channel primal male aggression into a shocking new form of "
        "therapy. Their concept catches on, with underground 'fight "
        "clubs' forming in every town."
    ),
    "tagline": "Mischief. Mayhem. Soap.",
    "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
    "backdrop_path": "/hZkgoQYus5gzQhH7AbJxE8AmzL.jpg",
    "release_date": "1999-10-15",
    "runtime": 139,
    "budget": 63000000,
    "revenue": 100853753,
    "vote_average": 8.433,
    "vote_count": 29651,
    "genres": [
        {"id": 18, "name": "Drama"},
    ],
    "production_companies": [
        {"id": 508, "name": "Regency Enterprises"},
        {"id": 25, "name": "20th Century Fox"},
    ],
    "production_countries": [
        {"iso_3166_1": "US", "name": "United States of America"},
    ],
    "spoken_languages": [{"iso_639_1": "en", "name": "English"}],
    "status": "Released",
    "original_language": "en",
    "credits": {
        "cast": [
            {
                "id": 819,
                "name": "Edward Norton",
                "character": "The Narrator",
                "profile_path": "/eIkFHNlrretLo0psa5OP1wqRArh.jpg",
                "order": 0,
            },
            {
                "id": 287,
                "name": "Brad Pitt",
                "character": "Tyler Durden",
                "profile_path": "/cckcYc2v0yhKCoE3cmL8yAuuHwf.jpg",
                "order": 1,
            },
        ],
        "crew": [
            {
                "id": 7467,
                "name": "David Fincher",
                "job": "Director",
                "department": "Directing",
            },
        ],
    },
    "images": {
        "posters": [
            {
                "file_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
                "iso_639_1": "en",
                "vote_average": 5.8,
            },
        ],
        "backdrops": [
            {
                "file_path": "/hZkgoQYus5gzQhH7AbJxE8AmzL.jpg",
                "iso_639_1": None,
                "vote_average": 5.7,
            },
        ],
    },
    "videos": {"results": []},
    "recommendations": {"results": []},
    "similar": {"results": []},
    "external_ids": {"imdb_id": "tt0137523", "tvdb_id": 0},
    "keywords": {"keywords": []},
    "ratings": {"imdb": 8.8, "rotten_tomatoes": 80, "metacritic": 67, "trakt": 85, "tmdb": 84},
    "content_ratings": {"results": [{"iso_3166_1": "US", "rating": "R"}]},
    "release_dates": {
        "results": [
            {
                "iso_3166_1": "US",
                "release_dates": [{"certification": "R", "type": 3}],
            },
        ],
    },
}

# Patch targets (mirror tests/cli/test_scrape_resolve.py).
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_EXTRACT_STREAM_INFO = "personalscraper.scraper.mediainfo.extract_stream_info"
_PATCH_NFO_GENERATOR = "personalscraper.scraper.nfo_generator.NFOGenerator"
_PATCH_ARTWORK_DOWNLOADER = "personalscraper.scraper.artwork.ArtworkDownloader"

runner = make_cli_runner()

# ---------------------------------------------------------------------------
# Helpers — DB setup
# ---------------------------------------------------------------------------

SCRAPE_DECISION_DDL = """
CREATE TABLE scrape_decision (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    staging_path    TEXT    UNIQUE NOT NULL,
    media_kind      TEXT    NOT NULL,
    extracted_title TEXT    NOT NULL,
    extracted_year  INTEGER,
    "trigger"       TEXT    NOT NULL,
    candidates_json TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending',
    resolution_json TEXT,
    run_uid         TEXT,
    created_at      REAL    NOT NULL,
    updated_at      REAL    NOT NULL,
    resolved_at     REAL
);
CREATE INDEX idx_scrape_decision_status ON scrape_decision(status);
"""


def _create_db(db_path: Path) -> None:
    """Create an on-disk SQLite DB with the ``scrape_decision`` table."""
    conn = _sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.executescript(SCRAPE_DECISION_DDL)
    conn.commit()
    conn.close()


def _insert_decision(
    db_path: Path,
    staging_path: str,
    media_kind: str = "movie",
    status: str = "pending",
    extracted_title: str = "Fight Club",
    extracted_year: int | None = 1999,
    trigger: str = "mid_band",
) -> int:
    """Insert a decision row and return its id."""
    now = time.time()
    candidates = json.dumps(
        [
            {
                "provider": "tmdb",
                "provider_id": 550,
                "title": "Fight Club",
                "year": 1999,
                "score": 0.65,
                "poster_url": None,
                "overview": None,
            }
        ]
    )
    conn = _sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    cursor = conn.execute(
        "INSERT INTO scrape_decision "
        "(staging_path, media_kind, extracted_title, extracted_year, "
        '"trigger", candidates_json, status, run_uid, created_at, updated_at) '
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            staging_path,
            media_kind,
            extracted_title,
            extracted_year,
            trigger,
            candidates,
            status,
            "run-uid-test",
            now,
            now,
        ),
    )
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    assert row_id is not None
    return row_id


def _select_decision(db_path: Path, decision_id: int) -> dict | None:
    """Return the decision row as a dict, or ``None``."""
    conn = _sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.row_factory = _sqlite3.Row
    row = conn.execute("SELECT * FROM scrape_decision WHERE id = ?", (decision_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _make_mock_per_step_boundary(mock_client: Any) -> Any:
    """Return a context-manager factory that yields a mock ``app_context``.

    The yielded context has a ``provider_registry`` whose ``get()`` returns
    *mock_client* — so ``app_context.provider_registry.get("tmdb")`` returns
    the configured mock.
    """

    @contextmanager
    def _cm(config: Any, settings: Any) -> Any:
        mock_ctx = MagicMock()
        mock_ctx.provider_registry = MagicMock()
        mock_ctx.provider_registry.get.return_value = mock_client
        yield mock_ctx

    return _cm


def _mock_nfo_generator_that_writes() -> MagicMock:
    """Return a ``NFOGenerator`` mock that actually writes the NFO file.

    ``generate_movie_nfo`` returns ``"<movie/>"``; ``write_nfo`` writes the
    XML content to the real filesystem path so the test can assert the file
    exists.
    """
    instance = MagicMock()
    instance.generate_movie_nfo.return_value = "<movie/>"

    def _write_nfo(xml: str, nfo_path: Path) -> None:
        nfo_path.parent.mkdir(parents=True, exist_ok=True)
        nfo_path.write_text(xml, encoding="utf-8")

    instance.write_nfo.side_effect = _write_nfo
    return instance


def _mock_artwork_downloader() -> MagicMock:
    """Return a pre-configured ``ArtworkDownloader`` mock instance."""
    return MagicMock()


def _setup_command_args(staging_dir: Path, provider: str, provider_id: int) -> list[str]:
    """Build CLI argv for the scrape-resolve command."""
    return [
        "scrape-resolve",
        str(staging_dir),
        "--provider",
        provider,
        "--id",
        str(provider_id),
    ]


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------


class TestScrapeArbiterE2E:
    """End-to-end scrape-resolve flow with real DB, real staging folder, mocked providers."""

    def test_resolve_movie_writes_nfo_and_resolves_decision(self, tmp_path: Path, test_config: Any) -> None:
        """Happy path: provider returns golden payload → NFO written, decision resolved.

        Asserts:
        - Exit code 0.
        - NFO file exists in the staging folder.
        - Decision row status is ``'resolved'`` with ``resolution_json``.
        - artwork downloader was called.
        """
        staging = tmp_path / "staging" / "001-MOVIES" / "Fight Club (1999)"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        decision_id = _insert_decision(test_config.indexer.db_path, str(staging.resolve()))

        mock_client = MagicMock()
        mock_client.get_movie.return_value = REALISTIC_MOVIE_PAYLOAD

        # True E2E: the command delegates to the REAL ``Scraper.scrape_movie_forced``
        # (which runs the SAME canonical write as the automatic scrape). Only the
        # artwork METHOD is patched on the class — this affects the Scraper's real
        # ArtworkDownloader instance, so no network I/O happens while still proving
        # the delegation reaches artwork. The real NFOGenerator writes the NFO.
        art_mock = MagicMock(return_value=[])

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
            patch(
                "personalscraper.commands.scrape_resolve.acquire_scrape_resolve_lock",
                return_value=Path("/fake/scrape.lock"),
            ),
            patch("personalscraper.commands.scrape_resolve.release_scrape_resolve_lock"),
            patch(
                "personalscraper.commands.scrape_resolve.per_step_boundary",
                _make_mock_per_step_boundary(mock_client),
            ),
            patch("personalscraper.scraper.artwork.ArtworkDownloader.download_movie_artwork", art_mock),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        assert result.exit_code == 0, result.output
        assert "Successfully resolved decision" in result.output

        # NFO must be written under the CANONICAL name (parsed title, no "(Year)"),
        # exactly as the automatic scrape does — so the pipeline's enforce/verify steps
        # recognise it and never re-un-identify the item. Regression (operator loop): it
        # used to be written as "Fight Club (1999).nfo", which enforce deletes as an
        # "extra NFO" and verify never finds (it looks for "Fight Club.nfo").
        nfo_path = staging / "Fight Club.nfo"
        assert nfo_path.exists(), f"NFO file not found at {nfo_path}"
        assert not (staging / "Fight Club (1999).nfo").exists()

        # Decision row must be resolved.
        row = _select_decision(test_config.indexer.db_path, decision_id)
        assert row is not None
        assert row["status"] == "resolved"
        resolution = json.loads(row["resolution_json"])
        assert resolution["provider"] == "tmdb"
        assert resolution["provider_id"] == 550
        assert resolution["via"] == "pick"

        # The real delegation reached artwork download.
        assert art_mock.call_count >= 1, "artwork downloader was not called"

    def test_provider_failure_leaves_decision_pending(self, tmp_path: Path, test_config: Any) -> None:
        """Provider raises → exit 1, decision stays ``'pending'``.

        A failed scrape-resolve must not resolve the decision — the operator
        can retry with a different provider or ID.
        """
        staging = tmp_path / "staging" / "001-MOVIES" / "Fight Club (1999)"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        decision_id = _insert_decision(test_config.indexer.db_path, str(staging.resolve()))

        mock_client = MagicMock()
        mock_client.get_movie.side_effect = RuntimeError("TMDB API down")

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
            patch(
                "personalscraper.commands.scrape_resolve.acquire_scrape_resolve_lock",
                return_value=Path("/fake/scrape.lock"),
            ),
            patch("personalscraper.commands.scrape_resolve.release_scrape_resolve_lock"),
            patch(
                "personalscraper.commands.scrape_resolve.per_step_boundary",
                _make_mock_per_step_boundary(mock_client),
            ),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        assert result.exit_code == 1

        # Decision must still be pending.
        row = _select_decision(test_config.indexer.db_path, decision_id)
        assert row is not None
        assert row["status"] == "pending"
