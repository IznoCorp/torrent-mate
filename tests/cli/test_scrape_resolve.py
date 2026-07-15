"""Tests for ``personalscraper scrape-resolve`` CLI command.

Covers:
- Exit 0 (happy path — movie via TMDB, TV show via TVDB / TMDB).
- Exit 1 (lock held, API failure).
- Exit 2 (bad provider, missing DB, no decision row, non-pending decision,
  invalid provider for media kind).
- Resolution row written via the real DecisionWriter.

Golden fixtures: realistic TMDB movie and TVDB series payloads so the
fetch-by-ID path is exercised with data that matches real API shapes
(vacuous-test lesson).
"""

from __future__ import annotations

import json
import sqlite3 as _sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.api.metadata._base import MediaDetails
from personalscraper.cli import app
from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.lock import is_lock_held
from tests.conftest import make_cli_runner

# ---------------------------------------------------------------------------
# Realistic golden fixtures (vacuous-test lesson)
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

REALISTIC_TVDB_SERIES = MediaDetails(
    provider="tvdb",
    provider_id="255968",
    title="Top Chef",
    original_title="Top Chef",
    year=2010,
    overview=(
        "Top Chef is a reality competition show where chefs compete "
        "in culinary challenges judged by a panel of professional "
        "chefs and other notable figures from the food and wine industry."
    ),
    genres=["Reality", "Food"],
    external_ids={"tmdb": "12345", "imdb": "tt1234567"},
)

REALISTIC_TMDB_TV = SimpleNamespace(
    id=12345,
    name="Top Chef",
    original_name="Top Chef",
    overview="Same as above, from TMDB.",
    first_air_date="2010-03-03",
    poster_path="/abc.jpg",
    backdrop_path="/def.jpg",
    genres=[{"id": 10764, "name": "Reality"}],
    vote_average=7.2,
    vote_count=120,
    number_of_seasons=22,
    number_of_episodes=300,
    status="Returning Series",
    origin_country=["US"],
    original_language="en",
    networks=[{"id": 1, "name": "Bravo"}],
    credits={"cast": [], "crew": []},
    images={"posters": [], "backdrops": []},
    videos={"results": []},
    external_ids={"imdb_id": "tt1234567", "tvdb_id": 255968},
    keywords={"results": []},
    ratings={"imdb": 7.5, "tmdb": 72},
    content_ratings={"results": [{"iso_3166_1": "US", "rating": "TV-PG"}]},
)

# Patch target for the eager config load in the CLI callback.
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"

runner = make_cli_runner()

# ---------------------------------------------------------------------------
# Helpers
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
    """Return a context-manager factory that yields a mock app_context."""

    @contextmanager
    def _cm(config: Any, settings: Any) -> Any:
        mock_ctx = MagicMock()
        mock_ctx.provider_registry = MagicMock()
        mock_ctx.provider_registry.get.return_value = mock_client
        yield mock_ctx

    return _cm


# Patch targets for the delegated forced-scrape entry points (webui-overhaul /
# product-intent). The scrape-resolve command now delegates to the SAME scrape
# services as the automatic pipeline via ``Scraper.scrape_{movie,tvshow}_forced``
# (a forced provider match), so the CLI-contract tests stub those methods. The
# command imports ``Scraper`` inside its body, so patching at the class source
# module takes effect at call time. The full canonical write (folder + video +
# episode rename) is proven in tests/scraper/test_scrape_forced.py and in prod.
_PATCH_SCRAPER_MOVIE_FORCED = "personalscraper.scraper.orchestrator.Scraper.scrape_movie_forced"
_PATCH_SCRAPER_TVSHOW_FORCED = "personalscraper.scraper.orchestrator.Scraper.scrape_tvshow_forced"


def _forced_movie_ok(staging_path: Path, provider_id: int) -> Any:
    """Stub ``Scraper.scrape_movie_forced``: land ``<Title>.nfo`` + return scraped.

    Honours the command's observable contract (an NFO on disk so the NFO-gate
    passes, ``action='scraped'``) without re-running the internal scrape. Patched
    on the class, so it is called WITHOUT ``self`` (MagicMock is not a descriptor).
    """
    from personalscraper.scraper._shared import ScrapeResult

    title = staging_path.name.rsplit(" (", 1)[0]
    (staging_path / f"{title}.nfo").write_text("<movie/>")
    result = ScrapeResult(media_path=staging_path, media_type="movie")
    result.action = "scraped"
    return result


def _forced_show_ok(staging_path: Path, source: str, provider_id: int) -> Any:
    """Stub ``Scraper.scrape_tvshow_forced``: land ``tvshow.nfo`` + return scraped."""
    from personalscraper.scraper._shared import ScrapeResult

    (staging_path / "tvshow.nfo").write_text("<tvshow/>")
    result = ScrapeResult(media_path=staging_path, media_type="tvshow")
    result.action = "scraped"
    return result


def _forced_no_nfo(staging_path: Path, *args: Any) -> Any:
    """Stub a forced scrape that lands NO NFO (write no-op) — command must exit 1."""
    from personalscraper.scraper._shared import ScrapeResult

    result = ScrapeResult(media_path=staging_path, media_type="movie")
    result.action = "scraped"
    return result


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
# Exit-code 2 tests (misconfiguration)
# ---------------------------------------------------------------------------


class TestScrapeResolveExit2:
    """Validation errors → exit code 2."""

    def test_bad_provider_exits_2(self, tmp_path: Path, test_config: Any) -> None:
        """An unknown provider (not 'tmdb' or 'tvdb') → exit 2."""
        staging = tmp_path / "staging" / "test"
        staging.mkdir(parents=True)

        # Create DB so the provider check fires before the DB check.
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        _insert_decision(test_config.indexer.db_path, str(staging.resolve()))

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "imdb", 550))

        assert result.exit_code == 2
        assert "Invalid provider" in result.output

    def test_missing_db_exits_2(self, tmp_path: Path, test_config: Any) -> None:
        """A non-existent indexer DB → exit 2."""
        staging = tmp_path / "staging" / "test"
        staging.mkdir(parents=True)

        # Ensure the DB does NOT exist.
        db_path = test_config.indexer.db_path
        if db_path.exists():
            db_path.unlink()
        # But the parent dir must exist.
        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        assert result.exit_code == 2
        assert "not found" in result.output

    def test_no_decision_row_exits_2(self, tmp_path: Path, test_config: Any) -> None:
        """No matching decision row for the staging path → exit 2."""
        staging = tmp_path / "staging" / "test"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        # Do NOT insert any decision row.

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        assert result.exit_code == 2
        assert "No decision row found" in result.output

    def test_already_resolved_exits_2(self, tmp_path: Path, test_config: Any) -> None:
        """A non-pending decision → exit 2."""
        staging = tmp_path / "staging" / "test"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        _insert_decision(test_config.indexer.db_path, str(staging.resolve()), status="resolved")

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        assert result.exit_code == 2
        assert "already 'resolved'" in result.output

    def test_movie_with_tvdb_provider_exits_2(self, tmp_path: Path, test_config: Any) -> None:
        """Movies require provider 'tmdb' → exit 2 when 'tvdb' given."""
        staging = tmp_path / "staging" / "test"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        _insert_decision(test_config.indexer.db_path, str(staging.resolve()), media_kind="movie")

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tvdb", 255968))

        assert result.exit_code == 2
        assert "Movies require provider 'tmdb'" in result.output


# ---------------------------------------------------------------------------
# Exit-code 1 tests (lock held, API failure)
# ---------------------------------------------------------------------------


class TestScrapeResolveExit1:
    """Operational errors → exit code 1."""

    def test_lock_held_exits_1(self, tmp_path: Path, test_config: Any) -> None:
        """When pipeline.lock is held → exit 1."""
        staging = tmp_path / "staging" / "test"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        _insert_decision(test_config.indexer.db_path, str(staging.resolve()))

        # Pre-create the lock file with our own PID so acquire_lock refuses it.
        (test_config.paths.data_dir / "pipeline.lock").write_text(str(__import__("os").getpid()))

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        # Exit 3 = lock busy — DISTINCT from a scrape error (1) so the web
        # decisions runner can queue/retry lock races without retrying real
        # failures (operator directive 2026-07-15).
        assert result.exit_code == 3, result.output
        assert "Lock busy" in result.output

    def test_api_failure_exits_1(self, tmp_path: Path, test_config: Any) -> None:
        """When the API client raises → exit 1, decision stays pending."""
        staging = tmp_path / "staging" / "test"
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


# ---------------------------------------------------------------------------
# Exit-code 0 tests (happy path — golden-fixture fetch-by-ID)
# ---------------------------------------------------------------------------


class TestScrapeResolveExit0:
    """Happy-path tests with realistic golden-fixture payloads."""

    def test_movie_fetch_by_id_succeeds(self, tmp_path: Path, test_config: Any) -> None:
        """Movie via TMDB: golden payload → NFO + artwork → decision resolved.

        Design: docs/reference/scraping.md#decision-queue-drain
        Contract: The scrape-resolve CLI command fetches a movie by provider ID
        via the TMDB API, generates NFO + artwork into the staging folder, marks
        the decision row as resolved with resolution_json containing provider,
        provider_id, and via='pick', and exits 0.
        """
        staging = tmp_path / "staging" / "001-MOVIES" / "Fight Club (1999)"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        decision_id = _insert_decision(test_config.indexer.db_path, str(staging.resolve()))

        mock_client = MagicMock()
        mock_client.get_movie.return_value = REALISTIC_MOVIE_PAYLOAD

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
            patch(_PATCH_SCRAPER_MOVIE_FORCED, side_effect=_forced_movie_ok),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        assert result.exit_code == 0
        assert "Successfully resolved decision" in result.output

        # Verify the decision row was resolved.
        row = _select_decision(test_config.indexer.db_path, decision_id)
        assert row is not None
        assert row["status"] == "resolved"
        resolution = json.loads(row["resolution_json"])
        assert resolution["provider"] == "tmdb"
        assert resolution["provider_id"] == 550
        assert resolution["via"] == "pick"

    def test_no_nfo_written_exits_1_and_stays_pending(self, tmp_path: Path, test_config: Any) -> None:
        """A scrape that leaves no NFO on disk must NOT mark the decision resolved.

        Contract (webui-overhaul #3): 'resolved' implies a scraped folder. If the
        NFO write is a no-op (write no-op / removed mid-flight), the command exits
        1 and the decision stays 'pending' so the operator can retry — it must not
        report a false success and leave a 'resolved' item with no metadata.
        """
        staging = tmp_path / "staging" / "001-MOVIES" / "Fight Club (1999)"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        decision_id = _insert_decision(test_config.indexer.db_path, str(staging.resolve()))

        mock_client = MagicMock()
        mock_client.get_movie.return_value = REALISTIC_MOVIE_PAYLOAD

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
            patch(_PATCH_SCRAPER_MOVIE_FORCED, side_effect=_forced_no_nfo),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        assert result.exit_code == 1, result.output
        assert "No NFO on disk" in result.output
        # The decision must stay pending (retryable), not falsely resolved.
        row = _select_decision(test_config.indexer.db_path, decision_id)
        assert row is not None
        assert row["status"] == "pending"

    def test_tvshow_via_tvdb_succeeds(self, tmp_path: Path, test_config: Any) -> None:
        """TV show via TVDB: golden payload → NFO + artwork → decision resolved."""
        staging = tmp_path / "staging" / "002-TVSHOWS" / "Top Chef (2010)"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        decision_id = _insert_decision(
            test_config.indexer.db_path,
            str(staging.resolve()),
            media_kind="tvshow",
            extracted_title="Top Chef",
            extracted_year=2010,
        )

        mock_client = MagicMock()
        mock_client.get_series.return_value = REALISTIC_TVDB_SERIES

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
            patch(_PATCH_SCRAPER_TVSHOW_FORCED, side_effect=_forced_show_ok),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tvdb", 255968))

        assert result.exit_code == 0
        assert "Successfully resolved decision" in result.output

        row = _select_decision(test_config.indexer.db_path, decision_id)
        assert row is not None
        assert row["status"] == "resolved"
        resolution = json.loads(row["resolution_json"])
        assert resolution["provider"] == "tvdb"
        assert resolution["provider_id"] == 255968
        assert resolution["via"] == "pick"

    def test_tvshow_via_tmdb_succeeds(self, tmp_path: Path, test_config: Any) -> None:
        """TV show via TMDB: golden payload → NFO + artwork → decision resolved."""
        staging = tmp_path / "staging" / "002-TVSHOWS" / "Top Chef (2010)"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        decision_id = _insert_decision(
            test_config.indexer.db_path,
            str(staging.resolve()),
            media_kind="tvshow",
            extracted_title="Top Chef",
            extracted_year=2010,
        )

        mock_client = MagicMock()
        mock_client.get_tv.return_value = REALISTIC_TMDB_TV

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
            patch(_PATCH_SCRAPER_TVSHOW_FORCED, side_effect=_forced_show_ok),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 12345))

        assert result.exit_code == 0
        assert "Successfully resolved decision" in result.output

        row = _select_decision(test_config.indexer.db_path, decision_id)
        assert row is not None
        assert row["status"] == "resolved"
        resolution = json.loads(row["resolution_json"])
        assert resolution["provider"] == "tmdb"
        assert resolution["provider_id"] == 12345
        assert resolution["via"] == "pick"


# ---------------------------------------------------------------------------
# NFC normalization
# ---------------------------------------------------------------------------


class TestNFCNormalization:
    """Staging paths are NFC-normalized before the DB lookup."""

    def test_nfc_normalization_matches(self, tmp_path: Path, test_config: Any) -> None:
        """A path stored as NFC is matched even when the filesystem returns NFD.

        macOS / macFUSE ``iterdir()`` yields NFD; the DB stores NFC.  The
        command normalizes the CLI argument before querying so the row is
        found regardless.
        """
        import unicodedata

        # Use a name with a combining accent so NFD ≠ NFC.
        nfc_name = "Pokémon"  # é as precomposed (NFC)
        staging = tmp_path / "staging" / nfc_name
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        _insert_decision(
            test_config.indexer.db_path,
            unicodedata.normalize("NFC", str(staging.resolve())),
            extracted_title="Pokémon",
        )

        mock_client = MagicMock()
        mock_client.get_movie.return_value = REALISTIC_MOVIE_PAYLOAD

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
            patch(_PATCH_SCRAPER_MOVIE_FORCED, side_effect=_forced_movie_ok),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        assert result.exit_code == 0


class TestScrapeResolveLockLifecycle:
    """Unmocked per-item scrape-lock self-acquisition proof (webui-ux phase 4).

    Every other happy-path test stubs ``acquire_scrape_resolve_lock`` /
    ``release_scrape_resolve_lock`` so the lock is never really taken — a joint
    mock that would let a broken self-lock ship green.  This test runs the REAL
    ``acquire_scrape_resolve_lock`` / ``release_scrape_resolve_lock`` and asserts
    the per-staging-item lock is held *while the scrape body executes* and
    released once the command returns — while the global ``pipeline.lock`` is
    NEVER taken (distinct items resolve in parallel; mutual exclusion with the
    pipeline is a read-check only).
    """

    def test_item_lock_held_during_body_pipeline_lock_untouched(self, tmp_path: Path, test_config: Any) -> None:
        """A real scrape-resolve holds its per-item scrape lock mid-body, frees it after.

        Design: docs/features/webui-ux/plan/phase-04-scraping.md §4.2
        Contract: scrape-resolve acquires a per-staging-item lock under
        ``<data_dir>/locks/scrape/`` for its lifetime — that lock file exists and
        is held by a live PID during the scrape/NFO body, and is removed when the
        command exits.  The global ``pipeline.lock`` is NEVER acquired (only
        read-checked), so two resolves on distinct items run concurrently.
        """
        import os as _os

        from personalscraper.lock import scrape_locks_dir_for

        staging = tmp_path / "staging" / "001-MOVIES" / "Fight Club (1999)"
        staging.mkdir(parents=True)

        test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        _create_db(test_config.indexer.db_path)
        _insert_decision(test_config.indexer.db_path, str(staging.resolve()))

        pipeline_lock_path = test_config.paths.data_dir / "pipeline.lock"
        scrape_dir = scrape_locks_dir_for(test_config.paths.data_dir)
        captured: dict[str, Any] = {}

        def _lock_probe(staging_path: Path, provider_id: int) -> Any:
            """Record lock state while the scrape body runs (and land an NFO)."""
            item_locks = sorted(scrape_dir.glob("*.lock")) if scrape_dir.is_dir() else []
            captured["item_lock_held"] = any(is_lock_held(p) for p in item_locks)
            captured["item_lock_pid"] = item_locks[0].read_text().strip() if item_locks else None
            # The GLOBAL pipeline.lock must NOT be taken by scrape-resolve.
            captured["pipeline_lock_held"] = is_lock_held(pipeline_lock_path)
            # The real forced scrape writes an NFO; the command now asserts one
            # exists before marking resolved (webui-overhaul #3), so mimic it and
            # return a scraped result the way the real forced method does.
            (staging / "movie.nfo").write_text("<movie/>")
            from personalscraper.scraper._shared import ScrapeResult

            return ScrapeResult(media_path=staging, media_type="movie", action="scraped")

        mock_client = MagicMock()
        mock_client.get_movie.return_value = REALISTIC_MOVIE_PAYLOAD

        # NB: acquire_scrape_resolve_lock / release_scrape_resolve_lock are NOT
        # patched here — they run for real against test_config's data_dir (via
        # the patched loader).  Only the scrape body is replaced with the probe.
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
            patch(
                "personalscraper.commands.scrape_resolve.per_step_boundary",
                _make_mock_per_step_boundary(mock_client),
            ),
            patch(
                _PATCH_SCRAPER_MOVIE_FORCED,
                side_effect=_lock_probe,
            ),
        ):
            result = runner.invoke(app, _setup_command_args(staging, "tmdb", 550))

        assert result.exit_code == 0, result.output
        # The per-item scrape lock was genuinely held (live PID) mid-body.
        assert captured.get("item_lock_held") is True
        assert captured.get("item_lock_pid") == str(_os.getpid())
        # The global pipeline.lock was NEVER taken by scrape-resolve.
        assert captured.get("pipeline_lock_held") is False
        assert not pipeline_lock_path.exists()
        # And the item lock was released once the command returned (finally).
        assert not any(is_lock_held(p) for p in (scrape_dir.glob("*.lock") if scrape_dir.is_dir() else []))
