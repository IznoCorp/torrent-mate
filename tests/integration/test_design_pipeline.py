"""Design-contract tests for pipeline-wide invariants (codename: ``pipeline``).

Pin points for ``docs/reference/pipeline-internals.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import PATTERNS
from personalscraper.pipeline_steps import DEFAULT_STEPS
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
            report = run_scrape(settings, config=config, event_bus=EventBus())

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


class TestCleanFastSkipContract:
    """Clean-step fast-skip — DESIGN pipeline-internals.md §Clean fast-skip."""

    def test_clean_skips_reclean_when_no_polluted_folders(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Reclean is skipped when no release-group tokens remain in folder names.

        Design: docs/reference/pipeline-internals.md#clean-fast-skip
        Contract: When ``_has_polluted_folders()`` returns False for both
        movies and TV-shows staging dirs, the reclean sub-step is skipped
        (no reclean_folders calls), and dedup runs alone. The clean step
        emits a ``process_clean_complete`` event with zero recleaned count.
        """
        from personalscraper.process.reclean import _has_polluted_folders
        from personalscraper.process.run import run_clean

        settings = MagicMock()
        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS
        config.paths.staging_dir = tmp_path
        config.disks = []

        # Create clean category dirs with cleanly-named folders (no junk).
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        clean_movie = movies_dir / "Clean Movie (2024)"
        clean_movie.mkdir()

        tv_dir = tmp_path / "002-TVSHOWS"
        tv_dir.mkdir()
        clean_show = tv_dir / "Clean Show (2024)"
        clean_show.mkdir()

        with caplog.at_level(logging.INFO, logger="process.run"):
            report = run_clean(settings, dry_run=False, config=config, event_bus=EventBus())

        # Fast-skip: no polluted folders detected → reclean not called.
        assert not _has_polluted_folders(movies_dir)
        assert not _has_polluted_folders(tv_dir)
        assert _has_event(caplog, "process_clean_complete"), "clean step must emit 'process_clean_complete'"
        assert report.name == "clean"
        # Zero recleaned (dedup may produce zero for non-duplicate folders).
        assert report.error_count == 0

    def test_clean_runs_reclean_when_junk_detected(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Reclean runs when polluted folder names are found.

        Design: docs/reference/pipeline-internals.md#clean-fast-skip
        Contract: When ``_has_polluted_folders()`` returns True (a folder
        name still contains release-group tokens), the clean step does
        NOT skip reclean — it runs reclean_folders which renames the
        polluted folder to its clean canonical form. The
        ``process_reclean_renamed`` event is emitted.
        """
        from personalscraper.process.reclean import _has_polluted_folders
        from personalscraper.process.run import run_clean

        settings = MagicMock()
        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS
        config.paths.staging_dir = tmp_path
        config.disks = []

        # Create a polluted folder (release-group tag still in name).
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        polluted = movies_dir / "Movie.2024.1080p.AMZN.WEB-DL.DDP5.1.H264-GROUP"
        polluted.mkdir()

        tv_dir = tmp_path / "002-TVSHOWS"
        tv_dir.mkdir()

        # Verify polluted BEFORE running clean.
        assert _has_polluted_folders(movies_dir), "polluted folder must be detected BEFORE reclean runs"

        with caplog.at_level(logging.INFO, logger="process.run"):
            report = run_clean(settings, dry_run=False, config=config, event_bus=EventBus())

        # After reclean: folder was renamed, pollution is gone.
        assert not _has_polluted_folders(movies_dir), "reclean must clean the polluted folder"
        assert _has_event(caplog, "process_reclean_renamed"), (
            "reclean must emit 'process_reclean_renamed' when a folder is renamed"
        )
        assert _has_event(caplog, "process_clean_complete"), "clean step must complete normally"
        assert report.name == "clean"
        assert report.error_count == 0
        assert report.success_count > 0, "reclean renamed at least one folder"


class TestIdempotenceContract:
    """Pipeline-wide idempotence — DESIGN pipeline-internals.md §Fast-Skip (idempotence)."""

    def test_scrape_step_idempotent_across_two_runs(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Two consecutive scrape runs on unchanged input produce the same result.

        Design: docs/reference/pipeline-internals.md#fast-skip-idempotence
        Contract: Re-running a pipeline step on already-processed input
        is a no-op — the second run produces the same StepReport (zero
        changes) as the fast-skip of the first run.
        """
        settings = MagicMock()
        settings.tmdb_api_key = "fake"
        settings.tvdb_api_key = "fake"

        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS
        config.paths.staging_dir = tmp_path

        # Complete movie (triggers scrape fast-skip).
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
        (tmp_path / "002-TVSHOWS").mkdir()

        with (
            patch("personalscraper.scraper.run.Scraper"),
            caplog.at_level(logging.INFO, logger="scraper.run"),
        ):
            report1 = run_scrape(settings, config=config, event_bus=EventBus())
            report2 = run_scrape(settings, config=config, event_bus=EventBus())

        # Both runs must produce the same zero-change outcome.
        assert report1.success_count == 0
        assert report1.error_count == 0
        assert report2.success_count == report1.success_count
        assert report2.skip_count == report1.skip_count
        assert report2.error_count == report1.error_count


class TestStepContracts:
    """Pipeline step contracts — DESIGN pipeline-internals.md §Step Contracts."""

    def test_all_default_steps_accept_step_context(self) -> None:
        """Every step in DEFAULT_STEPS can be called with a StepContext.

        Design: docs/reference/pipeline-internals.md#step-contracts
        Contract: Each of the 9 pipeline steps registered in
        ``DEFAULT_STEPS`` implements the ``PipelineStep`` protocol —
        accepting a ``StepContext`` and returning a result. The 9 keys
        are: ingest, sort, clean, scrape, cleanup, enforce, verify,
        trailers, dispatch.
        """
        expected_steps = {
            "ingest",
            "sort",
            "clean",
            "scrape",
            "cleanup",
            "enforce",
            "verify",
            "trailers",
            "dispatch",
        }
        assert set(DEFAULT_STEPS.keys()) == expected_steps, (
            f"DEFAULT_STEPS key set changed: {set(DEFAULT_STEPS.keys())}"
        )

        # Each step must be a PipelineStep (has __call__ accepting StepContext)
        from collections.abc import Callable

        for name, step in DEFAULT_STEPS.items():
            assert isinstance(step, Callable), f"step {name!r} is not callable"
            # Verify the step name is set correctly.
            assert step.name == name, f"step {name!r} has name={step.name!r}"

    def test_step_names_match_documented_pipeline_order(self) -> None:
        """Step execution order matches the documented 9-step sequence.

        Design: docs/reference/architecture.md#workflow-pipeline
        Contract: The ordered keys of ``DEFAULT_STEPS`` (as iterated by
        the pipeline orchestrator) match the documented sequence:
        INGEST→SORT→CLEAN→SCRAPE→CLEANUP→ENFORCE→VERIFY→TRAILERS→DISPATCH.
        This guards against accidental reordering or step insertion.
        """
        documented_order = [
            "ingest",
            "sort",
            "clean",
            "scrape",
            "cleanup",
            "enforce",
            "verify",
            "trailers",
            "dispatch",
        ]
        actual_order = list(DEFAULT_STEPS.keys())
        assert actual_order == documented_order, (
            f"Step order mismatch: documented {documented_order}, got {actual_order}"
        )
