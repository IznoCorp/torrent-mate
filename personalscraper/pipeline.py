"""Sequential exhaustive pipeline orchestrator.

Executes the 5 pipeline phases with gates between them:
INGEST → SORT → (gate: 097-TEMP empty) → PROCESS → VERIFY → DISPATCH.

Each phase must complete fully before the next one starts. The dispatch
phase only runs if verified items exist. Replaces the inline logic
that was in cli.py:run().
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from rich.console import Console

from personalscraper.config import Settings
from personalscraper.models import PipelineReport, StepReport


class PipelineGateError(Exception):
    """Raised when a pipeline gate check fails."""


class Pipeline:
    """Sequential exhaustive pipeline orchestrator.

    Executes 5 phases with gates between them. Each phase must
    complete fully before the next one starts. The dispatch phase
    only runs if verified items exist.

    Attributes:
        settings: Pipeline configuration.
        dry_run: Preview mode — no filesystem changes.
        interactive: Prompt user for ambiguous matches.
        verbose: Show per-item details in console output.
        console: Rich console for output.
    """

    def __init__(
        self,
        settings: Settings,
        dry_run: bool = False,
        interactive: bool = False,
        verbose: bool = False,
        console: Console | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            settings: Pipeline configuration.
            dry_run: If True, preview operations without modifying files.
            interactive: If True, prompt for ambiguous matches.
            verbose: If True, show per-item details.
            console: Rich console. Created if not provided.
        """
        self.settings = settings
        self.dry_run = dry_run
        self.interactive = interactive
        self.verbose = verbose
        self.console = console or Console()
        self._log = logging.getLogger("pipeline")

    def run(self) -> PipelineReport:
        """Execute all pipeline phases sequentially with gates.

        Phase 1: INGEST — complete/ → 097-TEMP/
        Phase 2: SORT — 097-TEMP/ → 001-MOVIES/, 002-TVSHOWS/
        Gate: assert 097-TEMP empty
        Phase 3: PROCESS — re-clean + dedup + scrape + cleanup
        Phase 4: VERIFY — coherence check
        Phase 5: DISPATCH — only if verified items exist

        Returns:
            PipelineReport with 7 StepReports (ingest, sort, clean,
            scrape, cleanup, verify, dispatch).
        """
        from datetime import datetime

        from personalscraper.ingest.ingest import run_ingest
        from personalscraper.sorter.run import run_sort

        report = PipelineReport(started_at=datetime.now())

        # Phase 1: INGEST
        self._run_step(
            "ingest",
            lambda: run_ingest(self.settings, dry_run=self.dry_run),
            report,
        )

        # Phase 2: SORT
        self._run_step(
            "sort",
            lambda: run_sort(self.settings, dry_run=self.dry_run),
            report,
        )

        # GATE: assert 097-TEMP is empty after sort
        self._check_temp_empty_gate()

        # Phase 3: PROCESS (re-clean + dedup + scrape + cleanup)
        # Returns 3 StepReports added individually
        self._run_process_phase(report)

        # Phase 4: VERIFY
        verified = self._run_step(
            "verify",
            lambda: self._run_verify(),
            report,
        )

        # Phase 5: DISPATCH (only if verified items exist)
        if verified:
            from personalscraper.dispatch.run import run_dispatch

            self._run_step(
                "dispatch",
                lambda: run_dispatch(self.settings, dry_run=self.dry_run, verified=verified),
                report,
            )
        else:
            self._log.warning("Skipping dispatch: no dispatchable items")
            self.console.print(
                f"\n{self._step_icon('dispatch')} [bold]DISPATCH[/bold]",
                highlight=False,
            )
            self.console.print(
                "   [yellow]SKIPPED: no verified items to dispatch[/yellow]",
                highlight=False,
            )
            report.add_step(
                "dispatch",
                StepReport(name="dispatch", skip_count=1,
                           details=["Skipped: no verified items"]),
            )

        report.finished_at = datetime.now()
        return report

    def _run_verify(self) -> tuple[StepReport, list]:
        """Run verify and return (StepReport, dispatchable list).

        Returns:
            Tuple of (StepReport, list of VerifyResult).
        """
        from personalscraper.verify.run import run_verify

        return run_verify(self.settings, dry_run=self.dry_run)

    def _run_process_phase(self, report: PipelineReport) -> None:
        """Execute Phase 3: PROCESS as 3 separate steps.

        Calls run_process() which coordinates:
        1. reclean + dedup (movies + tvshows) → clean StepReport
        2. scrape → scrape StepReport
        3. cleanup empty dirs → cleanup StepReport

        Each sub-step is wrapped in _run_step for timing and error handling.

        Args:
            report: PipelineReport to add step results to.
        """
        from personalscraper.process.run import run_process

        # run_process returns (clean, scrape, cleanup) as a tuple
        # We wrap it in _run_step calls for individual timing/error handling
        def _run_clean_and_scrape_and_cleanup():
            return run_process(
                self.settings,
                dry_run=self.dry_run,
                interactive=self.interactive,
            )

        try:
            clean_report, scrape_report, cleanup_report = _run_clean_and_scrape_and_cleanup()
            report.add_step("clean", clean_report)
            self._log_step_summary("clean", clean_report)
            report.add_step("scrape", scrape_report)
            self._log_step_summary("scrape", scrape_report)
            report.add_step("cleanup", cleanup_report)
            self._log_step_summary("cleanup", cleanup_report)
        except Exception as exc:
            self._log.exception("Process phase failed fatally")
            error_msg = f"{type(exc).__name__}: {exc}"
            # Add error reports for any missing steps
            for step_name in ("clean", "scrape", "cleanup"):
                if step_name not in report.steps:
                    report.add_step(
                        step_name,
                        StepReport(name=step_name, error_count=1,
                                   details=[f"Fatal: {error_msg}"]),
                    )
            self.console.print(f"   [red]FATAL: {error_msg}[/red]", highlight=False)

    def _check_temp_empty_gate(self) -> None:
        """Gate: verify 097-TEMP is empty after sort.

        Logs a warning if unsorted files remain but does NOT block
        the pipeline. The remaining files will be processed on the
        next run.
        """
        from personalscraper.sorter.run import assert_temp_empty

        remaining = assert_temp_empty(self.settings)
        if remaining:
            self._log.warning(
                "Gate 097-TEMP: %d unsorted files remain: %s",
                len(remaining),
                ", ".join(remaining[:5]),
            )
            self.console.print(
                f"   [yellow]! 097-TEMP not empty: {len(remaining)} files remain[/yellow]",
                highlight=False,
            )

    def _log_step_summary(self, name: str, step_report: StepReport) -> None:
        """Log a brief console summary for a process sub-step.

        Used by _run_process_phase to show inline feedback for
        clean/scrape/cleanup steps without full _run_step wrapping.

        Args:
            name: Step name for display.
            step_report: Completed StepReport.
        """
        icon = self._step_icon(name)
        self.console.print(f"\n{icon} [bold]{name.upper()}[/bold]", highlight=False)
        ok = step_report.success_count
        skip = step_report.skip_count
        err = step_report.error_count
        parts = []
        if ok:
            parts.append(f"[green]{ok} OK[/green]")
        if skip:
            parts.append(f"[yellow]{skip} skip[/yellow]")
        if err:
            parts.append(f"[red]{err} err[/red]")
        summary = ", ".join(parts) if parts else "[dim]nothing to do[/dim]"
        self.console.print(f"   {summary}", highlight=False)

        if self.verbose:
            for detail in step_report.details:
                if "skipped_already_done" in detail:
                    continue
                self.console.print(f"   [dim]{detail}[/dim]", highlight=False)
            for warning in step_report.warnings:
                self.console.print(f"   [yellow]! {warning}[/yellow]", highlight=False)

    def _step_icon(self, name: str) -> str:
        """Return the step number indicator for console output.

        Args:
            name: Step name.

        Returns:
            Formatted step number string (e.g. "[cyan]1/7[/cyan]").
        """
        icons = {
            "ingest": "[cyan]1/7[/cyan]",
            "sort": "[cyan]2/7[/cyan]",
            "clean": "[cyan]3/7[/cyan]",
            "scrape": "[cyan]4/7[/cyan]",
            "cleanup": "[cyan]5/7[/cyan]",
            "verify": "[cyan]6/7[/cyan]",
            "dispatch": "[cyan]7/7[/cyan]",
        }
        return icons.get(name, "")

    def _run_step(
        self,
        name: str,
        fn: Callable,
        report: PipelineReport,
    ) -> Any:
        """Execute a pipeline step with logging, timing, and console feedback.

        Args:
            name: Step name for display and logging.
            fn: Callable that returns StepReport or (StepReport, extra).
            report: PipelineReport to add results to.

        Returns:
            Extra data from fn (e.g. verified list), or None.
        """
        icon = self._step_icon(name)
        self.console.print(f"\n{icon} [bold]{name.upper()}[/bold]", highlight=False)
        self._log.info("Step %s started", name)
        t0 = time.monotonic()
        extra = None

        try:
            result = fn()
            # Some steps return (StepReport, extra_data)
            if isinstance(result, tuple):
                step_report, extra = result
            else:
                step_report = result
            report.add_step(name, step_report)
        except Exception as exc:
            self._log.exception("Step %s failed fatally", name)
            error_msg = f"{type(exc).__name__}: {exc}"
            step_report = StepReport(
                name=name, error_count=1,
                details=[f"Fatal: {error_msg}"],
            )
            report.add_step(name, step_report)
            self.console.print(f"   [red]FATAL: {error_msg}[/red]", highlight=False)

        elapsed = time.monotonic() - t0
        elapsed_str = f"{elapsed:.1f}s"

        # Inline summary after each step
        ok = step_report.success_count
        skip = step_report.skip_count
        err = step_report.error_count
        parts = []
        if ok:
            parts.append(f"[green]{ok} OK[/green]")
        if skip:
            parts.append(f"[yellow]{skip} skip[/yellow]")
        if err:
            parts.append(f"[red]{err} err[/red]")
        summary = ", ".join(parts) if parts else "[dim]nothing to do[/dim]"
        self.console.print(f"   {summary} ({elapsed_str})", highlight=False)

        # Show details in verbose mode — skip "already done" noise
        if self.verbose:
            for detail in step_report.details:
                if "skipped_already_done" in detail:
                    continue
                self.console.print(f"   [dim]{detail}[/dim]", highlight=False)
            for warning in step_report.warnings:
                self.console.print(f"   [yellow]! {warning}[/yellow]", highlight=False)

        self._log.info(
            "Step %s finished: ok=%d skip=%d err=%d (%.1fs)",
            name, ok, skip, err, elapsed,
        )
        return extra
