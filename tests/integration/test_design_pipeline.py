"""Design-contract tests for pipeline-wide invariants (codename: ``pipeline``).

Pin points for ``docs/reference/pipeline-internals.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.naming_patterns import PATTERNS
from personalscraper.scraper.run import run_scrape
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _has_event(caplog: pytest.LogCaptureFixture, event: str) -> bool:
    """Return True iff *event* appears as a structlog event name in *caplog*.

    structlog passes the event dict as ``LogRecord.msg`` before the
    ProcessorFormatter renders it; ``msg["event"]`` is the literal string
    passed to ``log.info`` / ``log.warning`` / ``log.exception``. Matching on
    that key catches renames even when logger name or context fields stay the
    same.
    """
    for record in caplog.records:
        msg = record.msg
        if isinstance(msg, dict) and msg.get("event") == event:
            return True
    return False


class TestScrapeFastSkipContract:
    """Scrape fast-skip — DESIGN pipeline-internals.md §Scrape fast-skip."""

    def test_complete_nfo_short_circuits_scrape_step(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """run_scrape returns without contacting any provider when nothing needs work.

        Design: docs/reference/pipeline-internals.md#scrape-fast-skip
        Contract: When every staged item already has a complete NFO and
        all required artwork, the scrape step's fast-skip path returns
        an empty StepReport without instantiating the Scraper, so no
        TMDB / TVDB request is issued.

        Three independent pins:

        1. ``Scraper`` is not constructed (no provider client built, hence
           no HTTP request can fire).
        2. The ``scrape_fast_skip`` log event is emitted — this is the
           uniquely identifying side effect of the fast-skip code path.
           A future refactor that early-returns on a different code path
           (e.g. before the unscraped-items check) would not emit it and
           would be caught here.
        3. The returned ``StepReport`` carries zero success/skip/error
           counts (fast-skip means *no item was processed at all*, not
           "all items were skipped"). Pinning all three counters
           defends against a refactor that, say, starts double-counting
           a fast-skip as a skip per item.
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

        with (
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
            caplog.at_level(logging.INFO, logger="scraper.run"),
        ):
            report = run_scrape(settings, config=config)

        # Pin 1: no Scraper instance constructed.
        MockScraper.assert_not_called()
        # Pin 2: fast-skip code path emitted its identifying log event.
        assert _has_event(caplog, "scrape_fast_skip"), (
            "fast-skip path did not emit the 'scrape_fast_skip' event — "
            "the early return may have moved to a different code path."
        )
        # Pin 3: StepReport carries zero counts (fast-skip != per-item skip).
        assert report.name == "scrape"
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0
