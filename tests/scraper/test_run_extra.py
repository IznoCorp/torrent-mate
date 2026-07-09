"""Additional coverage tests for ``personalscraper.scraper.run``.

Targets the residual gaps in :func:`run_scrape`, :func:`_to_step_report`,
:func:`_has_unscraped_items`, and :func:`_needs_repair`:

* ``_has_unscraped_items``: missing dirs, NFO-complete with missing
  artwork (poster + landscape), TV drift detection, return False path.
* ``_needs_repair``: non-existent dir, hidden subdirs, root-level NFO
  residuals.
* ``_to_step_report``: ``artwork_recovered`` and ``repaired`` action
  branches.
* ``run_scrape``: OSError fallback in repair-check, branches when one of
  the staging dirs is missing.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.core.media_types import FileType
from personalscraper.naming_patterns import PATTERNS
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.run import (
    _has_unscraped_items,
    _needs_repair,
    _to_step_report,
    run_scrape,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _make_settings() -> MagicMock:
    """Return a Settings-shaped mock with placeholder API keys."""
    s = MagicMock()
    s.tmdb_api_key = "fake"
    s.tvdb_api_key = "fake"
    return s


def _make_config(tmp_path: Path) -> MagicMock:
    """Return a Config-shaped mock with canonical staging layout under tmp_path."""
    c = MagicMock()
    c.staging_dirs = CANONICAL_STAGING_DIRS
    c.paths.staging_dir = tmp_path
    return c


# ---------------------------------------------------------------------------
# _has_unscraped_items
# ---------------------------------------------------------------------------


class TestHasUnscrapedItems:
    """Cover branches inside ``_has_unscraped_items``."""

    def test_returns_false_when_no_category_dirs(self, tmp_path: Path) -> None:
        """No staging subdirs created → False (continue branches both fire)."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        # Neither 001-MOVIES nor 002-TVSHOWS exist.
        assert _has_unscraped_items(settings, config) is False

    def test_returns_false_when_hidden_only(self, tmp_path: Path) -> None:
        """Hidden + non-dir entries are skipped (continue branch on iterdir)."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        (movies / ".DS_Store").write_text("")  # not a dir
        (movies / ".hidden_dir").mkdir()  # hidden dir
        (tmp_path / "002-TVSHOWS").mkdir()
        assert _has_unscraped_items(settings, config) is False

    def test_returns_true_when_movie_missing_poster(self, tmp_path: Path) -> None:
        """Valid NFO but missing poster → True (line 64 branch)."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        movie = movies / "The Matrix (1999)"
        movie.mkdir()
        # Title comes from _parse_folder_name → "The Matrix"
        (movie / "The Matrix.nfo").write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')
        # No poster, no landscape.
        (tmp_path / "002-TVSHOWS").mkdir()
        assert _has_unscraped_items(settings, config) is True

    def test_returns_true_when_movie_missing_landscape(self, tmp_path: Path) -> None:
        """Poster present, landscape missing → True (line 67 branch)."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        movie = movies / "Inception (2010)"
        movie.mkdir()
        (movie / "Inception.nfo").write_text('<movie><uniqueid type="tmdb">27205</uniqueid></movie>')
        # Poster present, but no landscape.
        poster_name = PATTERNS.format("movie_poster", Title="Inception")
        (movie / poster_name).write_bytes(b"\xff\xd8")
        (tmp_path / "002-TVSHOWS").mkdir()
        assert _has_unscraped_items(settings, config) is True

    def test_returns_false_when_movie_complete(self, tmp_path: Path) -> None:
        """Valid NFO + poster + landscape on the only category → False."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        movie = movies / "Inception (2010)"
        movie.mkdir()
        (movie / "Inception.nfo").write_text('<movie><uniqueid type="tmdb">27205</uniqueid></movie>')
        poster = PATTERNS.format("movie_poster", Title="Inception")
        landscape = PATTERNS.format("movie_landscape", Title="Inception")
        (movie / poster).write_bytes(b"\xff\xd8")
        (movie / landscape).write_bytes(b"\xff\xd8")
        # 002-TVSHOWS dir absent — exercises the cat_dir.exists() branch.
        assert _has_unscraped_items(settings, config) is False

    def test_returns_true_on_tvshow_drift(self, tmp_path: Path) -> None:
        """Complete tvshow.nfo but drift detected → True (line 80 branch)."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        (tmp_path / "001-MOVIES").mkdir()
        tvshows = tmp_path / "002-TVSHOWS"
        tvshows.mkdir()
        show = tvshows / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text(
            '<tvshow><title>Show</title><year>2020</year><uniqueid type="tmdb">100</uniqueid></tvshow>'
        )
        # Force drift by mocking verify_tvshow_scrape_drift to return False.
        with patch(
            "personalscraper.scraper.run.verify_tvshow_scrape_drift",
            return_value=(False, "synthetic_drift"),
        ):
            assert _has_unscraped_items(settings, config) is True


# ---------------------------------------------------------------------------
# _needs_repair
# ---------------------------------------------------------------------------


class TestNeedsRepairExtras:
    """Branches not yet exercised by the existing test_run_scrape suite."""

    def test_missing_category_dir_returns_false(self, tmp_path: Path) -> None:
        """Non-existent category dir → False without iterating."""
        assert _needs_repair(tmp_path / "missing", FileType.MOVIE) is False

    def test_hidden_and_non_dir_entries_skipped(self, tmp_path: Path) -> None:
        """Hidden subdirs + files at top level are ignored (continue branch line 107)."""
        cat = tmp_path / "001-MOVIES"
        cat.mkdir()
        (cat / ".hidden").mkdir()
        (cat / "loose_file.txt").write_text("not a dir")
        assert _needs_repair(cat, FileType.MOVIE) is False

    def test_root_residual_episode_nfo_returns_true(self, tmp_path: Path) -> None:
        """A root-level non-tvshow NFO triggers repair (line 133 branch)."""
        cat = tmp_path / "002-TVSHOWS"
        cat.mkdir()
        show = cat / "Show (2020)"
        show.mkdir()
        # Structurally clean folder (no season dirs, no residual subdirs)
        # but a stray episode NFO at root must trigger repair.
        (show / "S01E01.nfo").write_text("<episodedetails/>")
        assert _needs_repair(cat, FileType.TVSHOW) is True


# ---------------------------------------------------------------------------
# _to_step_report
# ---------------------------------------------------------------------------


class TestToStepReportExtraActions:
    """Cover the artwork_recovered + repaired action branches."""

    def test_artwork_recovered_with_artwork(self) -> None:
        """artwork_recovered increments success and lists the artwork count."""
        results = [
            ScrapeResult(
                media_path=Path("Movie Dir"),
                media_type="movie",
                action="artwork_recovered",
                artwork_downloaded=["poster.jpg"],
            )
        ]
        report = _to_step_report(results)
        assert report.success_count == 1
        assert any("recovered" in d and "1 artwork" in d for d in report.details)

    def test_artwork_recovered_without_artwork(self) -> None:
        """artwork_recovered with empty artwork list still counts as success."""
        results = [
            ScrapeResult(
                media_path=Path("Movie Dir"),
                media_type="movie",
                action="artwork_recovered",
            )
        ]
        report = _to_step_report(results)
        assert report.success_count == 1
        assert any("recovered" in d for d in report.details)

    def test_repaired_action_counts_as_success(self) -> None:
        """``repaired`` action increments success_count + adds detail."""
        results = [
            ScrapeResult(
                media_path=Path("Movie Dir"),
                media_type="movie",
                action="repaired",
            )
        ]
        report = _to_step_report(results)
        assert report.success_count == 1
        assert any("repaired" in d for d in report.details)


# ---------------------------------------------------------------------------
# run_scrape — repair-check OSError + missing dir branches
# ---------------------------------------------------------------------------


class TestRunScrapeRepairCheckOsError:
    """Cover the OSError fallbacks in the fast-skip repair check."""

    def test_movie_repair_oserror_forces_full_run(self, tmp_path: Path) -> None:
        """An OSError in movie ``_needs_repair`` forces ``needs_movie_repair=True``."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        (tmp_path / "001-MOVIES").mkdir()
        (tmp_path / "002-TVSHOWS").mkdir()

        with (
            patch(
                "personalscraper.scraper.run._needs_repair",
                side_effect=[OSError("io error movies"), False],
            ),
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=False),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_movies.return_value = []
            MockScraper.return_value.process_tvshows.return_value = []
            report = run_scrape(settings, config=config, event_bus=EventBus(), registry=MagicMock())

        # The fast-skip was bypassed because needs_movie_repair=True.
        MockScraper.assert_called_once()
        assert report.name == "scrape"

    def test_tvshow_repair_oserror_forces_full_run(self, tmp_path: Path) -> None:
        """An OSError in TV show ``_needs_repair`` forces ``needs_tvshow_repair=True``."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        (tmp_path / "001-MOVIES").mkdir()
        (tmp_path / "002-TVSHOWS").mkdir()

        with (
            patch(
                "personalscraper.scraper.run._needs_repair",
                side_effect=[False, OSError("io error tv")],
            ),
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=False),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_movies.return_value = []
            MockScraper.return_value.process_tvshows.return_value = []
            run_scrape(settings, config=config, event_bus=EventBus(), registry=MagicMock())

        MockScraper.assert_called_once()


class TestRunScrapeMissingDirBranches:
    """Cover the ``movies_dir.exists()`` / ``tvshows_dir.exists()`` skip branches."""

    def test_movies_dir_missing_skips_process_movies(self, tmp_path: Path) -> None:
        """When 001-MOVIES is absent the scraper does not call process_movies."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        # Only TV shows exists.
        (tmp_path / "002-TVSHOWS").mkdir()

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_tvshows.return_value = []
            run_scrape(settings, config=config, event_bus=EventBus(), registry=MagicMock())

        MockScraper.return_value.process_movies.assert_not_called()
        MockScraper.return_value.process_tvshows.assert_called_once()

    def test_tvshows_dir_missing_skips_process_tvshows(self, tmp_path: Path) -> None:
        """When 002-TVSHOWS is absent the scraper does not call process_tvshows."""
        settings = _make_settings()
        config = _make_config(tmp_path)
        (tmp_path / "001-MOVIES").mkdir()
        # 002-TVSHOWS missing.

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_movies.return_value = []
            run_scrape(settings, config=config, event_bus=EventBus(), registry=MagicMock())

        MockScraper.return_value.process_movies.assert_called_once()
        MockScraper.return_value.process_tvshows.assert_not_called()


def test_to_step_report_unknown_skipped_action() -> None:
    """A non-low-confidence ``skipped_*`` action increments skip_count only.

    Exercises the catch-all ``elif r.action.startswith("skipped")`` branch.
    """
    results = [
        ScrapeResult(
            media_path=Path("X"),
            media_type="movie",
            action="skipped_no_category",
        )
    ]
    report = _to_step_report(results)
    assert report.skip_count == 1
    assert any("skipped" in d for d in report.details)
    # ``unmatched`` counter stays at zero — only ``skipped_low_confidence``
    # surfaces there.
    assert "unmatched" not in report.counts


# ---------------------------------------------------------------------------
# scrape-arbiter decision enqueue wiring (sub-phase 1.5b)
# ---------------------------------------------------------------------------

_MIGRATION_013_PATH = (
    Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations" / "013_scrape_decision.sql"
)


def _create_decision_db(db_path: Path) -> None:
    """Create a SQLite DB with the ``scrape_decision`` table.

    Mirrors ``tests/scraper/test_decision_writer.py::_create_db``.
    The migration 013 script references ``schema_version``; create that
    table first, then run the full migration via ``executescript``.

    Args:
        db_path: Path to the on-disk SQLite database file to create.
    """
    import sqlite3

    from personalscraper.core.sqlite._pragmas import apply_pragmas

    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
    conn.commit()
    migration_sql = _MIGRATION_013_PATH.read_text(encoding="utf-8")
    conn.executescript(migration_sql)
    conn.close()


class TestDecisionEnqueue:
    """Tests for scrape-arbiter decision enqueue wiring in ``run_scrape``."""

    def test_enqueued_item_upserted_to_db(self, tmp_path: Path) -> None:
        """Item with ``queued_for_decision`` action → row inserted in scrape_decision.

        Verifies that:
        - The staging_path is NFC-normalized in the DB.
        - All fields (media_kind, extracted_title, extracted_year, trigger,
          candidates_json, status, run_uid, timestamps) are populated.
        - The row is queryable after ``run_scrape`` returns.
        """
        import sqlite3

        from personalscraper.scraper.decision_candidate import DecisionCandidate

        db_path = tmp_path / "library.db"
        _create_decision_db(db_path)

        staging = tmp_path / "staging"
        staging.mkdir()
        movies_dir = staging / "001-MOVIES"
        movies_dir.mkdir()
        tvshows_dir = staging / "002-TVSHOWS"
        tvshows_dir.mkdir()
        movie_folder = movies_dir / "Inception (2010)"
        movie_folder.mkdir()

        settings = _make_settings()
        config = _make_config(tmp_path)
        config.paths.staging_dir = staging
        config.indexer.db_path = db_path

        candidates = [
            DecisionCandidate(
                provider="tmdb",
                provider_id=27205,
                title="Inception",
                year=2010,
                score=0.65,
            ),
            DecisionCandidate(
                provider="tmdb",
                provider_id=99999,
                title="Inception 2",
                year=2012,
                score=0.55,
            ),
        ]
        result = ScrapeResult(
            media_path=movie_folder,
            media_type="movie",
            action="queued_for_decision",
            decision_candidates=candidates,
            decision_trigger="mid_band",
        )

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_movies.return_value = [result]
            MockScraper.return_value.process_tvshows.return_value = []
            run_scrape(
                settings,
                config=config,
                event_bus=EventBus(),
                registry=MagicMock(),
            )

        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT staging_path, media_kind, extracted_title, extracted_year, "
            '"trigger", candidates_json, status, run_uid, created_at, updated_at '
            "FROM scrape_decision WHERE staging_path = ?",
            (str(movie_folder),),
        ).fetchone()
        conn.close()

        assert row is not None, "Row should exist for the enqueued item"
        (
            staging_path_db,
            media_kind,
            title,
            year,
            trigger,
            candidates_json,
            status,
            run_uid_val,
            created_at,
            updated_at,
        ) = row
        assert staging_path_db == str(movie_folder)  # NFC (already NFC here)
        assert media_kind == "movie"
        assert title == "Inception"
        assert year == 2010
        assert trigger == "mid_band"
        assert status == "pending"
        assert run_uid_val is None
        assert created_at > 0
        assert updated_at > 0
        assert created_at == updated_at
        parsed = json.loads(candidates_json)
        assert len(parsed) == 2
        assert parsed[0]["provider"] == "tmdb"
        assert parsed[0]["provider_id"] == 27205

    def test_no_db_path_no_crash(self, tmp_path: Path) -> None:
        """config.indexer.db_path is None → enqueue is skipped, no crash."""
        from personalscraper.scraper.decision_candidate import DecisionCandidate

        staging = tmp_path / "staging"
        staging.mkdir()
        movies_dir = staging / "001-MOVIES"
        movies_dir.mkdir()
        tvshows_dir = staging / "002-TVSHOWS"
        tvshows_dir.mkdir()
        movie_folder = movies_dir / "Unknown (2024)"
        movie_folder.mkdir()

        settings = _make_settings()
        config = _make_config(tmp_path)
        config.paths.staging_dir = staging
        config.indexer.db_path = None  # No DB → should skip gracefully

        candidates = [
            DecisionCandidate(
                provider="tmdb",
                provider_id=1,
                title="Test",
                year=2024,
                score=0.30,
            ),
        ]
        result = ScrapeResult(
            media_path=movie_folder,
            media_type="movie",
            action="queued_for_decision",
            decision_candidates=candidates,
            decision_trigger="below_threshold",
        )

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_movies.return_value = [result]
            MockScraper.return_value.process_tvshows.return_value = []
            report = run_scrape(
                settings,
                config=config,
                event_bus=EventBus(),
                registry=MagicMock(),
            )

        # Should return a valid StepReport without crashing.
        assert report.name == "scrape"

    def test_orphan_gc_called_after_enqueue(self, tmp_path: Path) -> None:
        """``mark_superseded_orphans`` runs after enqueue when db_path is set.

        We insert an orphan row (staging path that does not exist on disk)
        before the run and assert it is superseded afterwards.
        """
        import sqlite3
        import time

        from personalscraper.core.sqlite._pragmas import apply_pragmas
        from personalscraper.scraper.decision_candidate import DecisionCandidate

        db_path = tmp_path / "library.db"
        _create_decision_db(db_path)

        staging = tmp_path / "staging"
        staging.mkdir()
        movies_dir = staging / "001-MOVIES"
        movies_dir.mkdir()
        tvshows_dir = staging / "002-TVSHOWS"
        tvshows_dir.mkdir()
        movie_folder = movies_dir / "Real Movie (2024)"
        movie_folder.mkdir()

        # Pre-insert an orphan row for a path that does NOT exist.
        orphan_path = str(movies_dir / "Deleted Movie (2021)")
        now = time.time()
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        apply_pragmas(conn)
        conn.execute(
            "INSERT INTO scrape_decision "
            "(staging_path, media_kind, extracted_title, extracted_year, "
            '"trigger", candidates_json, status, run_uid, created_at, updated_at) '
            "VALUES (?, 'movie', 'Deleted Movie', 2021, 'mid_band', '[]', "
            "'pending', NULL, ?, ?)",
            (orphan_path, now, now),
        )
        conn.commit()
        conn.close()

        settings = _make_settings()
        config = _make_config(tmp_path)
        config.paths.staging_dir = staging
        config.indexer.db_path = db_path

        candidates = [
            DecisionCandidate(
                provider="tmdb",
                provider_id=1,
                title="Real Movie",
                year=2024,
                score=0.65,
            ),
        ]
        result = ScrapeResult(
            media_path=movie_folder,
            media_type="movie",
            action="queued_for_decision",
            decision_candidates=candidates,
            decision_trigger="mid_band",
        )

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_movies.return_value = [result]
            MockScraper.return_value.process_tvshows.return_value = []
            run_scrape(
                settings,
                config=config,
                event_bus=EventBus(),
                registry=MagicMock(),
            )

        # Orphan row should be superseded.
        conn = sqlite3.connect(str(db_path))
        orphan_status = conn.execute(
            "SELECT status FROM scrape_decision WHERE staging_path = ?",
            (orphan_path,),
        ).fetchone()
        conn.close()
        assert orphan_status is not None
        assert orphan_status[0] == "superseded"

    def test_skipped_low_confidence_with_candidates_also_enqueued(self, tmp_path: Path) -> None:
        """``skipped_low_confidence`` with decision_candidates → enqueued additively.

        Items below LOW_CONFIDENCE keep their ``skipped_low_confidence`` action
        but carry ``decision_candidates`` for the additive decision queue row.
        """
        import sqlite3

        from personalscraper.scraper.decision_candidate import DecisionCandidate

        db_path = tmp_path / "library.db"
        _create_decision_db(db_path)

        staging = tmp_path / "staging"
        staging.mkdir()
        movies_dir = staging / "001-MOVIES"
        movies_dir.mkdir()
        tvshows_dir = staging / "002-TVSHOWS"
        tvshows_dir.mkdir()
        movie_folder = movies_dir / "Obscure Film (1999)"
        movie_folder.mkdir()

        settings = _make_settings()
        config = _make_config(tmp_path)
        config.paths.staging_dir = staging
        config.indexer.db_path = db_path

        candidates = [
            DecisionCandidate(
                provider="tmdb",
                provider_id=42,
                title="Obscure Film",
                year=1999,
                score=0.30,
            ),
        ]
        result = ScrapeResult(
            media_path=movie_folder,
            media_type="movie",
            action="skipped_low_confidence",
            decision_candidates=candidates,
            decision_trigger="below_threshold",
        )

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_movies.return_value = [result]
            MockScraper.return_value.process_tvshows.return_value = []
            run_scrape(
                settings,
                config=config,
                event_bus=EventBus(),
                registry=MagicMock(),
            )

        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            'SELECT extracted_title, media_kind, "trigger", status FROM scrape_decision WHERE staging_path = ?',
            (str(movie_folder),),
        ).fetchone()
        conn.close()
        assert row is not None, "Additive enqueue for skipped_low_confidence should create a row"
        assert row[0] == "Obscure Film"
        assert row[1] == "movie"
        assert row[2] == "below_threshold"
        assert row[3] == "pending"


# ---------------------------------------------------------------------------
# scrape-arbiter sub-phase 1.6 — StepReport counting + ItemProgressed emission
# ---------------------------------------------------------------------------


class TestQueuedForDecisionReporting:
    """Tests for ``queued_for_decision`` counting and event emission."""

    # -- _to_step_report ---------------------------------------------------

    def test_to_step_report_counts_queued_for_decision(self) -> None:
        """``queued_for_decision`` items counted in ``counts["queued_for_decision"]``.

        Paths also appear in ``unmatched_paths`` for operator visibility.
        """
        from personalscraper.scraper.decision_candidate import DecisionCandidate

        candidates = [
            DecisionCandidate(provider="tmdb", provider_id=1, title="T", year=2020, score=0.65),
        ]
        results = [
            ScrapeResult(
                media_path=Path("Mid Movie"),
                media_type="movie",
                action="queued_for_decision",
                decision_candidates=candidates,
                decision_trigger="mid_band",
            ),
        ]
        report = _to_step_report(results)
        assert report.counts.get("queued_for_decision") == 1
        assert "queued_for_decision" not in report.counts.get("unmatched", {})
        # Not counted as success: queued items are pending operator review.
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0
        assert "Mid Movie" in report.unmatched_paths
        assert any("queued_for_decision" in d for d in report.details)

    def test_to_step_report_additive_skipped_low_confidence(self) -> None:
        """``skipped_low_confidence`` with candidates also counted in ``queued_for_decision``.

        The item stays counted as both ``unmatched`` (existing behaviour) and
        ``queued_for_decision`` (additive enqueue). The path appears once in
        ``unmatched_paths`` (no double-append).
        """
        from personalscraper.scraper.decision_candidate import DecisionCandidate

        candidates = [
            DecisionCandidate(provider="tmdb", provider_id=42, title="X", year=1999, score=0.30),
        ]
        results = [
            ScrapeResult(
                media_path=Path("Low Movie"),
                media_type="movie",
                action="skipped_low_confidence",
                decision_candidates=candidates,
                decision_trigger="below_threshold",
            ),
        ]
        report = _to_step_report(results)
        assert report.counts.get("unmatched") == 1  # existing counter
        assert report.counts.get("queued_for_decision") == 1  # additive
        assert report.skip_count == 1
        assert report.success_count == 0
        # Path appears exactly once in unmatched_paths.
        assert report.unmatched_paths == ["Low Movie"]

    def test_to_step_report_mixed_items(self) -> None:
        """Mix of queued, skipped_low_confidence+candidates, and clean items."""
        from personalscraper.scraper.decision_candidate import DecisionCandidate

        candidates_a = [
            DecisionCandidate(provider="tmdb", provider_id=1, title="A", year=2020, score=0.65),
        ]
        candidates_b = [
            DecisionCandidate(provider="tmdb", provider_id=2, title="B", year=2020, score=0.49),
        ]
        results = [
            ScrapeResult(
                media_path=Path("Mid A"),
                media_type="movie",
                action="queued_for_decision",
                decision_candidates=candidates_a,
                decision_trigger="mid_band",
            ),
            ScrapeResult(
                media_path=Path("Low B"),
                media_type="movie",
                action="skipped_low_confidence",
                decision_candidates=candidates_b,
                decision_trigger="below_threshold",
            ),
            ScrapeResult(
                media_path=Path("Clean C"),
                media_type="movie",
                action="scraped",
                nfo_written=True,
            ),
            ScrapeResult(
                media_path=Path("Low No Candidates D"),
                media_type="movie",
                action="skipped_low_confidence",
                # No decision_candidates — not enqueued.
            ),
        ]
        report = _to_step_report(results)
        assert report.counts.get("queued_for_decision") == 2  # Mid A + Low B
        assert report.counts.get("unmatched") == 2  # Low B + Low No Candidates D
        assert report.success_count == 1  # Clean C
        assert report.skip_count == 2  # Low B + Low No Candidates D
        assert set(report.unmatched_paths) == {"Mid A", "Low B", "Low No Candidates D"}

    # -- run_scrape event emission -----------------------------------------

    def test_run_scrape_emits_item_progressed_queued(self, tmp_path: Path) -> None:
        """``run_scrape`` emits one ``ItemProgressed(status="queued_for_decision")`` per enqueued item.

        Each event carries ``trigger``, ``confidence``, and ``candidates_count``
        in its ``details`` dict.  The ``started`` event still fires first
        (existing behaviour).
        """
        from personalscraper.scraper.decision_candidate import DecisionCandidate

        staging = tmp_path / "staging"
        staging.mkdir()
        movies_dir = staging / "001-MOVIES"
        movies_dir.mkdir()
        tvshows_dir = staging / "002-TVSHOWS"
        tvshows_dir.mkdir()
        movie_folder = movies_dir / "Mid Movie (2024)"
        movie_folder.mkdir()

        settings = _make_settings()
        config = _make_config(tmp_path)
        config.paths.staging_dir = staging
        config.indexer.db_path = None  # skip DB wiring

        candidates = [
            DecisionCandidate(provider="tmdb", provider_id=1, title="Mid Movie", year=2024, score=0.65),
        ]
        result = ScrapeResult(
            media_path=movie_folder,
            media_type="movie",
            action="queued_for_decision",
            decision_candidates=candidates,
            decision_trigger="mid_band",
        )

        bus = EventBus()
        captured: list[ItemProgressed] = []
        bus.subscribe(ItemProgressed, captured.append)

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_movies.return_value = [result]
            MockScraper.return_value.process_tvshows.return_value = []
            run_scrape(settings, config=config, event_bus=bus, registry=MagicMock())

        queued_events = [e for e in captured if e.status == "queued_for_decision"]
        assert len(queued_events) == 1, f"Expected 1 queued_for_decision event, got {len(queued_events)}"
        event = queued_events[0]
        assert event.step == "scrape"
        assert event.item == "Mid Movie (2024)"
        assert event.details is not None
        assert event.details["trigger"] == "mid_band"
        assert event.details["candidates_count"] == 1
        # ``started`` event also emitted (existing behaviour).
        started_events = [e for e in captured if e.status == "started"]
        assert len(started_events) == 1

    def test_run_scrape_queued_report_counts(self, tmp_path: Path) -> None:
        """StepReport returned by ``run_scrape`` includes ``queued_for_decision`` count."""
        from personalscraper.scraper.decision_candidate import DecisionCandidate

        staging = tmp_path / "staging"
        staging.mkdir()
        movies_dir = staging / "001-MOVIES"
        movies_dir.mkdir()
        tvshows_dir = staging / "002-TVSHOWS"
        tvshows_dir.mkdir()
        movie_folder = movies_dir / "Ambiguous Film (2023)"
        movie_folder.mkdir()

        settings = _make_settings()
        config = _make_config(tmp_path)
        config.paths.staging_dir = staging
        config.indexer.db_path = None

        candidates = [
            DecisionCandidate(provider="tmdb", provider_id=10, title="Ambiguous Film", year=2023, score=0.85),
            DecisionCandidate(provider="tmdb", provider_id=11, title="Ambiguous Film", year=2023, score=0.83),
        ]
        result = ScrapeResult(
            media_path=movie_folder,
            media_type="movie",
            action="queued_for_decision",
            decision_candidates=candidates,
            decision_trigger="ambiguous",
        )

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            MockScraper.return_value.process_movies.return_value = [result]
            MockScraper.return_value.process_tvshows.return_value = []
            report = run_scrape(
                settings,
                config=config,
                event_bus=EventBus(),
                registry=MagicMock(),
            )

        assert report.counts.get("queued_for_decision") == 1
        assert "Ambiguous Film (2023)" in report.unmatched_paths
