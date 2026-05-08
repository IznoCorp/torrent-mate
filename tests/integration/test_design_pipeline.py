"""Design-contract tests for pipeline-wide invariants (codename: ``pipeline``).

Pin points for ``docs/reference/pipeline-internals.md``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.naming_patterns import PATTERNS
from personalscraper.scraper.run import run_scrape
from tests.fixtures.config import CANONICAL_STAGING_DIRS


class TestScrapeFastSkipContract:
    """Scrape fast-skip — DESIGN pipeline-internals.md §Scrape fast-skip."""

    def test_complete_nfo_short_circuits_scrape_step(self, tmp_path: Path) -> None:
        """run_scrape returns without contacting any provider when nothing needs work.

        Design: docs/reference/pipeline-internals.md#scrape-fast-skip
        Contract: When every staged item already has a complete NFO and
        all required artwork, the scrape step's fast-skip path returns
        an empty StepReport without instantiating the Scraper, so no
        TMDB / TVDB request is issued. This is the integration-level
        contract on top of the unit-level ``is_nfo_complete`` invariant
        pinned in test_design_scraper.py.
        """
        settings = MagicMock()
        settings.tmdb_api_key = "fake"
        settings.tvdb_api_key = "fake"

        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS
        config.paths.staging_dir = tmp_path

        # Build a movies staging tree with one complete movie:
        #   <staging>/001-MOVIES/Sample (2024)/Sample.nfo  (complete)
        #   <staging>/001-MOVIES/Sample (2024)/Sample-poster.jpg
        #   <staging>/001-MOVIES/Sample (2024)/Sample-landscape.jpg
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        movie = movies_dir / "Sample (2024)"
        movie.mkdir()
        (movie / PATTERNS.format("movie_nfo", Title="Sample")).write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<movie><uniqueid type="tmdb">42</uniqueid><title>Sample</title></movie>\n',
            encoding="utf-8",
        )
        (movie / PATTERNS.format("movie_poster", Title="Sample")).write_bytes(b"\x00")
        (movie / PATTERNS.format("movie_landscape", Title="Sample")).write_bytes(b"\x00")

        # TV shows staging is empty — no work there either.
        (tmp_path / "002-TVSHOWS").mkdir()

        with patch("personalscraper.scraper.run.Scraper") as MockScraper:
            report = run_scrape(settings, config=config)

        assert report.name == "scrape"
        # Fast-skip path: no Scraper instance should have been built and no
        # provider call should have been issued.
        MockScraper.assert_not_called()
        assert report.success_count == 0
        assert report.error_count == 0
