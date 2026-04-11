"""Tests for E2E assertions — verify assertion functions work correctly."""

from unittest.mock import MagicMock

import pytest

from tests.e2e.assertions import (
    assert_cleanup_complete,
    assert_dispatch_complete,
    assert_ingest_complete,
    assert_pipeline_report,
    assert_scrape_complete,
    assert_sort_complete,
    assert_verify_complete,
)
from tests.e2e.markers import place_marker
from tests.e2e.registry import TestRegistry


class TestAssertIngestComplete:
    """Tests for assert_ingest_complete()."""

    def test_passes_when_items_present(self, tmp_path):
        """No assertion error when expected items exist in staging."""
        (tmp_path / "The.Matrix.1999").mkdir()
        expected = [{"name": "Matrix"}]
        assert_ingest_complete(tmp_path, expected)  # Should not raise

    def test_fails_when_item_missing(self, tmp_path):
        """Raises AssertionError when expected item is not found."""
        expected = [{"name": "NonExistent"}]
        with pytest.raises(AssertionError, match="not found in staging"):
            assert_ingest_complete(tmp_path, expected)


class TestAssertSortComplete:
    """Tests for assert_sort_complete()."""

    def test_passes_movies_in_correct_dir(self, tmp_path):
        """No error when movie is in 001-MOVIES."""
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        (movies / "The Matrix (1999)").mkdir()
        expected = [{"name": "Matrix", "type": "movie"}]
        assert_sort_complete(movies, tmp_path / "002-TVSHOWS", expected)

    def test_fails_movie_in_wrong_dir(self, tmp_path):
        """Raises when movie is not in 001-MOVIES."""
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        expected = [{"name": "Missing", "type": "movie"}]
        with pytest.raises(AssertionError, match="not found"):
            assert_sort_complete(movies, tmp_path / "002-TVSHOWS", expected)


class TestAssertScrapeComplete:
    """Tests for assert_scrape_complete()."""

    def test_passes_with_valid_nfo(self, tmp_path):
        """No error when movie has valid NFO and poster."""
        movies = tmp_path / "001-MOVIES"
        movie_dir = movies / "The Matrix (1999)"
        movie_dir.mkdir(parents=True)
        (movie_dir / "The Matrix.nfo").write_text(
            '<?xml version="1.0"?><movie><title>The Matrix</title><year>1999</year></movie>'
        )
        (movie_dir / "The Matrix-poster.jpg").write_text("fake")

        expected = [{"name": "Matrix", "type": "movie", "verify_nfo_fields": ["title", "year"]}]
        assert_scrape_complete(movies, tmp_path, expected)

    def test_fails_missing_nfo(self, tmp_path):
        """Raises when movie has no NFO."""
        movies = tmp_path / "001-MOVIES"
        (movies / "The Matrix (1999)").mkdir(parents=True)
        expected = [{"name": "Matrix", "type": "movie", "verify_nfo_fields": []}]
        with pytest.raises(AssertionError, match="no .nfo"):
            assert_scrape_complete(movies, tmp_path, expected)


class TestAssertVerifyComplete:
    """Tests for assert_verify_complete()."""

    def test_passes_valid_results(self):
        """No error when all results are valid/fixed."""
        r1 = MagicMock(status="valid", category="films", media_path=MagicMock(name="Movie"))
        r2 = MagicMock(status="fixed", category="series", media_path=MagicMock(name="Show"))
        assert_verify_complete([r1, r2])

    def test_fails_blocked_result(self):
        """Raises when a result is blocked."""
        r = MagicMock(status="blocked", media_path=MagicMock(name="Bad"), issues=["missing nfo"])
        with pytest.raises(AssertionError, match="blocked"):
            assert_verify_complete([r])


class TestAssertDispatchComplete:
    """Tests for assert_dispatch_complete()."""

    def test_passes_item_on_disk(self, tmp_path):
        """No error when item is on disk with marker."""
        disk = tmp_path / "Disk1" / "medias"
        film_dir = disk / "films" / "The Matrix (1999)"
        film_dir.mkdir(parents=True)
        place_marker(film_dir, "test-session")

        expected = [{"name": "Matrix", "expected_category": "films"}]
        assert_dispatch_complete([disk], expected)

    def test_fails_missing_marker(self, tmp_path):
        """Raises when item is on disk but marker is missing."""
        disk = tmp_path / "Disk1" / "medias"
        (disk / "films" / "The Matrix (1999)").mkdir(parents=True)

        expected = [{"name": "Matrix", "expected_category": "films"}]
        with pytest.raises(AssertionError, match="marker missing"):
            assert_dispatch_complete([disk], expected)


class TestAssertPipelineReport:
    """Tests for assert_pipeline_report()."""

    def test_passes_complete_report(self):
        """No error when report has all steps."""
        from datetime import datetime

        from personalscraper.models import PipelineReport, StepReport

        report = PipelineReport(started_at=datetime.now())
        for step in ("ingest", "sort", "scrape", "verify", "dispatch"):
            report.add_step(step, StepReport(name=step))
        report.finished_at = datetime.now()
        assert_pipeline_report(report)

    def test_fails_missing_steps(self):
        """Raises when steps are missing."""
        from datetime import datetime

        from personalscraper.models import PipelineReport, StepReport

        report = PipelineReport(started_at=datetime.now())
        report.add_step("ingest", StepReport(name="ingest"))
        report.finished_at = datetime.now()
        with pytest.raises(AssertionError, match="missing steps"):
            assert_pipeline_report(report)


class TestAssertCleanupComplete:
    """Tests for assert_cleanup_complete()."""

    def test_passes_clean_state(self, tmp_path):
        """No error when all paths are gone."""
        reg = TestRegistry(session_id="clean", base_dir=tmp_path)
        reg.created_paths = [str(tmp_path / "gone")]  # Path doesn't exist
        assert_cleanup_complete(reg, base_paths=[tmp_path])

    def test_fails_path_still_exists(self, tmp_path):
        """Raises when a registered path still exists."""
        reg = TestRegistry(session_id="dirty", base_dir=tmp_path)
        leftover = tmp_path / "still_here"
        leftover.mkdir()
        reg.created_paths = [str(leftover)]
        with pytest.raises(AssertionError, match="still exists"):
            assert_cleanup_complete(reg)
