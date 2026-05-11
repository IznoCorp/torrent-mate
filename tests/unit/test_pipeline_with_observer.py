"""Tests for pipeline running with observer callbacks."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from unittest.mock import MagicMock, patch

from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline import Pipeline
from personalscraper.pipeline_observer import CollectorObserver, PipelineObserverBase


class TestPipelineWithObserver:
    """Pipeline observer integration tests."""

    @staticmethod
    def _make_fake_steps():
        class FakeStep:
            def __init__(self, name):
                self.name = name

            def __call__(self, *args, **kwargs):
                if self.name == "verify":
                    return StepReport(name=self.name, success_count=1), [MagicMock()]
                return StepReport(name=self.name, success_count=1)

        return {
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

    @staticmethod
    def _make_config():
        config = MagicMock()
        config.disks = []
        config.paths.staging_dir = MagicMock()
        config.paths.data_dir = MagicMock()
        config.trailers.pipeline.skip = True
        config.trailers.pipeline.continue_on_error = True
        config.trailers.enabled = False
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]
        return config

    def test_all_step_callbacks_called_in_order(self) -> None:
        """on_step_start + on_step_end called for each step in order."""
        collector = CollectorObserver()
        pipeline = Pipeline(
            self._make_config(),
            MagicMock(),
            observers=[collector],
            step_overrides=self._make_fake_steps(),
        )

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                with patch.object(Pipeline, "_recover_from_previous_run", return_value=0):
                    pipeline.run()

        assert len(collector.starts) == 9
        assert len(collector.ends) == 9
        assert collector.starts[0] == "ingest"
        assert collector.ends[-1][0] == "dispatch"

    def test_on_step_error_called_on_failure(self) -> None:
        """on_step_error is called when a step raises."""
        collector = CollectorObserver()
        overrides = self._make_fake_steps()

        class CrashStep:
            name = "ingest"

            def __call__(self, *args, **kwargs):
                raise ValueError("boom")

        overrides["ingest"] = CrashStep()

        pipeline = Pipeline(
            self._make_config(),
            MagicMock(),
            observers=[collector],
            step_overrides=overrides,
        )

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                with patch.object(Pipeline, "_recover_from_previous_run", return_value=0):
                    pipeline.run()

        assert len(collector.errors) == 1
        assert "boom" in str(collector.errors[0][1])

    def test_on_pipeline_start_called_once(self) -> None:
        """on_pipeline_start is called exactly once at the beginning."""
        collector = CollectorObserver()
        pipeline = Pipeline(
            self._make_config(),
            MagicMock(),
            observers=[collector],
            step_overrides=self._make_fake_steps(),
        )

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                with patch.object(Pipeline, "_recover_from_previous_run", return_value=0):
                    pipeline.run()

        assert len(collector.pipeline_starts) == 1
        assert len(collector.pipeline_ends) == 1

    def test_on_pipeline_end_called(self) -> None:
        """on_pipeline_end is called after all steps."""
        collector = CollectorObserver()
        pipeline = Pipeline(
            self._make_config(),
            MagicMock(),
            observers=[collector],
            step_overrides=self._make_fake_steps(),
        )

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                with patch.object(Pipeline, "_recover_from_previous_run", return_value=0):
                    pipeline.run()

        assert len(collector.pipeline_ends) == 1
        assert isinstance(collector.pipeline_ends[0], PipelineReport)

    def test_crashing_lifecycle_observer_does_not_abort_pipeline(self) -> None:
        """A broken observer lifecycle callback is isolated from pipeline execution."""

        class CrashingObserver(PipelineObserverBase):
            name = "crashing"

            def on_step_start(self, step: str) -> None:
                raise RuntimeError(f"broken start {step}")

            def on_pipeline_end(self, report: PipelineReport) -> None:
                raise RuntimeError("broken end")

        collector = CollectorObserver()
        pipeline = Pipeline(
            self._make_config(),
            MagicMock(),
            observers=[CrashingObserver(), collector],
            step_overrides=self._make_fake_steps(),
        )

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                with patch.object(Pipeline, "_recover_from_previous_run", return_value=0):
                    report = pipeline.run()

        assert len(report.steps) == 9
        assert len(collector.starts) == 9
        assert len(collector.pipeline_ends) == 1

    def test_notify_observers_overloads_are_checked_by_mypy(self) -> None:
        """Static overloads reject invalid lifecycle callback argument shapes."""
        snippet = textwrap.dedent(
            """
            from typing import cast

            from personalscraper.models import StepReport
            from personalscraper.pipeline import Pipeline

            p = cast(Pipeline, object())
            p._notify_observers("on_step_end", "sort", StepReport(name="sort"), 1.5)
            p._notify_observers("on_step_start", "ingest", "extra")
            """
        )

        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--config-file=/dev/null", "-c", snippet],
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert 'No overload variant of "_notify_observers"' in result.stdout
        assert "on_step_start" in result.stdout
