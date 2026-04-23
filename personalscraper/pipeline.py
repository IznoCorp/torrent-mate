"""Sequential exhaustive pipeline orchestrator.

Executes 6 phases producing 8 StepReports:
INGEST → SORT → (gate: 097-TEMP empty) → PROCESS (clean, scrape, cleanup)
→ ENFORCE → VERIFY → DISPATCH.

Each phase must complete fully before the next one starts. The dispatch
phase only runs if verified items exist. Phase 3 (PROCESS) runs 3
independent sub-steps, each with its own error isolation.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console

from personalscraper.conf.models import Config
from personalscraper.conf.staging import ensure_staging_tree, find_ingest_dir, staging_path
from personalscraper.config import Settings
from personalscraper.models import PipelineReport, StepReport

if TYPE_CHECKING:
    from personalscraper.verify.verifier import VerifyResult


class PipelineGateError(Exception):
    """Raised when a pipeline gate check fails."""


class _CriticalStepError(Exception):
    """Raised internally when a critical pipeline step crashes.

    Used to abort the pipeline early when ingest or sort fail fatally,
    since downstream steps depend on their output.
    """


class Pipeline:
    """Sequential exhaustive pipeline orchestrator.

    Executes 6 phases producing 8 StepReports. Each phase must
    complete fully before the next one starts. The dispatch phase
    only runs if verified items exist.

    Attributes:
        config: Config with paths and disk layout.
        settings: Pipeline configuration (secrets, thresholds).
        dry_run: Preview mode — no filesystem changes.
        interactive: Prompt user for ambiguous matches.
        verbose: Show per-item details in console output.
        console: Rich console for output.
    """

    def __init__(
        self,
        config: Config,
        settings: Settings,
        dry_run: bool = False,
        interactive: bool = False,
        verbose: bool = False,
        console: Console | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            config: Config with paths and disk layout.
            settings: Pipeline configuration (secrets, thresholds).
            dry_run: If True, preview operations without modifying files.
            interactive: If True, prompt for ambiguous matches.
            verbose: If True, show per-item details.
            console: Rich console. Created if not provided.
        """
        self.config = config
        self.settings = settings
        self.dry_run = dry_run
        self.interactive = interactive
        self.verbose = verbose
        self.console = console or Console()
        self._log = logging.getLogger("pipeline")

    def _recover_from_previous_run(
        self,
        lockout_path: Path | None = None,
    ) -> int:
        """Clean up artifacts from a previous interrupted pipeline run.

        Runs at pipeline startup before INGEST. Handles:
        1. Orphan _tmp_dispatch_* directories on storage disks
        2. Expired qBit auth lockout file (>1 hour)
        3. Orphan .ingest_tmp_* directories in staging

        Args:
            lockout_path: Override lockout file path (for testing).
                Defaults to ~/.cache/personalscraper/qbit_auth_lockout.

        Returns:
            Number of artifacts cleaned.
        """
        import shutil
        from pathlib import Path as _Path

        from personalscraper.ingest.ingest import _cleanup_orphan_temps

        cleaned = 0

        # 1. Clean _tmp_dispatch_* on ALL storage disks
        for disk_config in self.config.disks:
            if not disk_config.path.exists():
                continue
            try:
                for category_dir in disk_config.path.iterdir():
                    if not category_dir.is_dir():
                        continue
                    for item in category_dir.iterdir():
                        if item.name.startswith("_tmp_dispatch_"):
                            try:
                                shutil.rmtree(item)
                                self._log.info("Crash recovery: cleaned dispatch orphan %s", item)
                                cleaned += 1
                            except OSError as exc:
                                self._log.warning(
                                    "Crash recovery: cannot clean %s: %s",
                                    item,
                                    exc,
                                )
            except OSError as exc:
                self._log.warning("Crash recovery: cannot scan disk %s: %s", disk_config.path, exc)
                continue

        # 2. Clean expired qBit lockout
        if lockout_path is None:
            lockout_path = _Path.home() / ".cache" / "personalscraper" / "qbit_auth_lockout"
        if lockout_path.exists():
            try:
                age = time.time() - lockout_path.stat().st_mtime
                if age > 3600:
                    lockout_path.unlink(missing_ok=True)
                    self._log.info("Crash recovery: cleaned expired lockout (%ds old)", int(age))
                    cleaned += 1
            except OSError as exc:
                self._log.warning("Crash recovery: cannot clean lockout %s: %s", lockout_path, exc)

        # 3. Clean .ingest_tmp_* in staging
        ingest_dir = staging_path(self.config, find_ingest_dir(self.config))
        if ingest_dir.exists():
            cleaned += _cleanup_orphan_temps(ingest_dir)

        if cleaned:
            self._log.info("Crash recovery: cleaned %d artifact(s)", cleaned)
        return cleaned

    def run(self) -> PipelineReport:
        """Execute all pipeline phases sequentially with gates.

        Phase 1: INGEST — complete/ → 097-TEMP/
        Phase 2: SORT — 097-TEMP/ → 001-MOVIES/, 002-TVSHOWS/
        Gate: assert 097-TEMP empty
        Phase 3: PROCESS — re-clean + dedup + scrape + cleanup
        Phase 4: ENFORCE — validate and correct conventions
        Phase 5: VERIFY — coherence check
        Phase 6: DISPATCH — only if verified items exist

        Returns:
            PipelineReport with 8 StepReports (ingest, sort, clean,
            scrape, cleanup, enforce, verify, dispatch).
        """
        from datetime import datetime

        from personalscraper.ingest.ingest import run_ingest
        from personalscraper.sorter.run import run_sort

        # Bootstrap staging tree on first run (idempotent, no-op if already exists)
        ensure_staging_tree(self.config)

        report = PipelineReport(started_at=datetime.now())

        # Recover from previous interrupted run (best-effort, never blocks pipeline)
        if not self.dry_run:
            try:
                self._recover_from_previous_run()
            except Exception as exc:
                self._log.error("Crash recovery failed (pipeline continues): %s", exc)
        else:
            self._log.info("[DRY RUN] Crash recovery skipped")

        # Phase 1: INGEST — abort pipeline on fatal crash because
        # sort depends on ingest having deposited files into 097-TEMP
        try:
            self._run_step(
                "ingest",
                lambda: run_ingest(self.settings, dry_run=self.dry_run, config=self.config),
                report,
                critical=True,
            )
        except _CriticalStepError:
            self._log.error("Ingest crashed fatally, aborting pipeline")
            report.finished_at = datetime.now()
            return report

        # Phase 2: SORT — abort pipeline on fatal crash because
        # process/scrape depend on files being in category dirs
        try:
            self._run_step(
                "sort",
                lambda: run_sort(
                    self.settings,
                    staging_dir=self.config.paths.staging_dir,
                    dry_run=self.dry_run,
                    config=self.config,
                ),
                report,
                critical=True,
            )
        except _CriticalStepError:
            self._log.error("Sort crashed fatally, aborting pipeline")
            report.finished_at = datetime.now()
            return report

        # GATE: assert 097-TEMP is empty after sort
        self._check_temp_empty_gate()

        # Phase 3: PROCESS (re-clean + dedup + scrape + cleanup)
        # Returns 3 StepReports added individually
        self._run_process_phase(report)

        # Phase 4: ENFORCE (validate and correct conventions)
        from personalscraper.enforce.run import run_enforce

        self._run_step(
            "enforce",
            lambda: run_enforce(self.settings, self.config, dry_run=self.dry_run),
            report,
        )

        # Phase 5: VERIFY
        verified = self._run_step(
            "verify",
            lambda: self._run_verify(),
            report,
        )

        # Phase 6: DISPATCH (only if verified items exist)
        if verified:
            from personalscraper.dispatch.run import run_dispatch

            self._run_step(
                "dispatch",
                lambda: run_dispatch(
                    self.settings,
                    config=self.config,
                    dry_run=self.dry_run,
                    verified=verified,
                ),
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
                StepReport(name="dispatch", skip_count=1, details=["Skipped: no verified items"]),
            )

        report.finished_at = datetime.now()
        return report

    def _run_verify(self) -> tuple[StepReport, list["VerifyResult"]]:
        """Run verify and return (StepReport, dispatchable list).

        Returns:
            Tuple of (StepReport, list of VerifyResult).
        """
        from personalscraper.verify.run import run_verify

        return run_verify(self.settings, self.config, dry_run=self.dry_run, fix=False)

    def _run_process_phase(self, report: PipelineReport) -> None:
        """Execute Phase 3: PROCESS as 3 independent steps.

        Each sub-step is wrapped in _run_step for individual error
        isolation, timing, and structured logging. If clean crashes,
        scrape and cleanup still run.

        Steps:
        1. clean — reclean + dedup (movies + tvshows)
        2. scrape — TMDB/TVDB matching, NFO, artwork
        3. cleanup — remove empty directories

        Args:
            report: PipelineReport to add step results to.
        """
        from personalscraper.process.run import run_clean, run_cleanup
        from personalscraper.scraper.run import run_scrape

        self._run_step(
            "clean",
            lambda: run_clean(self.settings, dry_run=self.dry_run, config=self.config),
            report,
        )

        self._run_step(
            "scrape",
            lambda: run_scrape(
                self.settings,
                staging_dir=self.config.paths.staging_dir,
                dry_run=self.dry_run,
                interactive=self.interactive,
            ),
            report,
        )

        self._run_step(
            "cleanup",
            lambda: run_cleanup(self.settings, dry_run=self.dry_run, config=self.config),
            report,
        )

    def _check_temp_empty_gate(self) -> None:
        """Gate: verify 097-TEMP is empty after sort.

        Logs a warning if unsorted files remain but does NOT block
        the pipeline. The remaining files will be processed on the
        next run.
        """
        from personalscraper.sorter.run import assert_temp_empty

        remaining = assert_temp_empty(self.settings, staging_dir=self.config.paths.staging_dir, config=self.config)
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

    def _step_icon(self, name: str) -> str:
        """Return the step number indicator for console output.

        Args:
            name: Step name.

        Returns:
            Formatted step number string (e.g. "[cyan]1/7[/cyan]").
        """
        icons = {
            "ingest": "[cyan]1/8[/cyan]",
            "sort": "[cyan]2/8[/cyan]",
            "clean": "[cyan]3/8[/cyan]",
            "scrape": "[cyan]4/8[/cyan]",
            "cleanup": "[cyan]5/8[/cyan]",
            "enforce": "[cyan]6/8[/cyan]",
            "verify": "[cyan]7/8[/cyan]",
            "dispatch": "[cyan]8/8[/cyan]",
        }
        return icons.get(name, "")

    def _run_step(
        self,
        name: str,
        fn: Callable[[], Any],
        report: PipelineReport,
        *,
        critical: bool = False,
    ) -> Any:
        """Execute a pipeline step with logging, timing, and console feedback.

        If fn raises an exception, it is caught and recorded as a fatal
        error in the report. The step still contributes to the pipeline
        report rather than aborting — unless ``critical=True``, in which
        case ``_CriticalStepError`` is re-raised after recording.

        Args:
            name: Step name for display and logging.
            fn: Callable that returns StepReport or (StepReport, extra).
            report: PipelineReport to add results to.
            critical: If True, re-raise after recording so the caller
                can abort the pipeline for data-dependent steps.

        Returns:
            Extra data from fn (e.g. verified list), or None.

        Raises:
            _CriticalStepError: If ``critical=True`` and fn raises.
        """
        icon = self._step_icon(name)
        self.console.print(f"\n{icon} [bold]{name.upper()}[/bold]", highlight=False)
        self._log.info("Step %s started", name)
        t0 = time.monotonic()
        extra = None
        crashed = False

        try:
            result = fn()
            # Some steps return (StepReport, extra_data)
            if isinstance(result, tuple):
                step_report, extra = result
            else:
                step_report = result
            report.add_step(name, step_report)
        except Exception as exc:
            crashed = True
            self._log.exception("Step %s failed fatally", name)
            error_msg = f"{type(exc).__name__}: {exc}"
            step_report = StepReport(
                name=name,
                error_count=1,
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
            name,
            ok,
            skip,
            err,
            elapsed,
        )

        if crashed and critical:
            raise _CriticalStepError(f"Critical step '{name}' crashed")

        return extra
