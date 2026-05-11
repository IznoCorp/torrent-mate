"""Tests for pipeline headless mode (observers=[])."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline import Pipeline


class TestPipelineHeadless:
    """Pipeline with observers=[] runs without rich.Console."""

    def test_constructs_with_empty_observers(self) -> None:
        """Pipeline accepts observers=[] without error."""
        config = MagicMock()
        config.disks = []
        config.paths.staging_dir = MagicMock()
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]
        config.paths.data_dir = MagicMock()
        settings = MagicMock()

        pipeline = Pipeline(config, settings, observers=[])
        assert pipeline._observers == []

    def test_default_creates_rich_console_observer(self) -> None:
        """observers=None auto-creates RichConsoleObserver."""
        config = MagicMock()
        config.disks = []
        config.paths.staging_dir = MagicMock()
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]
        config.paths.data_dir = MagicMock()
        settings = MagicMock()

        pipeline = Pipeline(config, settings)
        assert len(pipeline._observers) == 1
        assert pipeline._observers[0].name == "rich-console"

    def test_default_rich_console_observer_receives_dry_run_flag(self) -> None:
        """Pipeline dry-run mode is reflected by the default console observer."""
        config = MagicMock()
        config.disks = []
        config.paths.staging_dir = MagicMock()
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]
        config.paths.data_dir = MagicMock()
        settings = MagicMock()

        pipeline = Pipeline(config, settings, dry_run=True)

        assert pipeline._observers[0].dry_run is True

    def test_run_with_no_observers(self) -> None:
        """Pipeline runs to completion with observers=[]."""
        config = MagicMock()
        config.disks = []
        config.paths.staging_dir = MagicMock()
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]
        config.paths.data_dir = MagicMock()
        config.trailers.pipeline.skip = True
        config.trailers.pipeline.continue_on_error = True
        config.trailers.enabled = False
        settings = MagicMock()

        class FakeStep:
            def __init__(self, step_name):
                self.name = step_name

            def __call__(self, *args, **kwargs):
                if self.name == "verify":
                    return StepReport(name=self.name, success_count=1), [MagicMock()]
                return StepReport(name=self.name, success_count=1)

        overrides = {
            n: FakeStep(n)
            for n in [
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
        }

        pipeline = Pipeline(config, settings, observers=[], step_overrides=overrides)

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                with patch.object(Pipeline, "_recover_from_previous_run", return_value=0):
                    report = pipeline.run()

        assert isinstance(report, PipelineReport)
        assert len(report.steps) == 9
