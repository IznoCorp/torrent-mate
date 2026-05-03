"""Sequential exhaustive pipeline orchestrator.

Executes 7 phases producing 9 StepReports:
INGEST → SORT → (gate: ingest dir empty) → PROCESS (clean, scrape, cleanup)
→ ENFORCE → VERIFY → TRAILERS → DISPATCH.

Each phase must complete fully before the next one starts. The dispatch
phase only runs if verified items exist. Phase 3 (PROCESS) runs 3
independent sub-steps, each with its own error isolation.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from rich.console import Console

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import ensure_staging_tree, find_ingest_dir, staging_path
from personalscraper.config import Settings
from personalscraper.logger import get_logger
from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline_protocol import StepContext
from personalscraper.pipeline_steps import DEFAULT_STEPS, apply_step_overrides
from personalscraper.reports import STEP_REPORT_CONTRACT


class _CriticalStepError(Exception):
    """Raised internally when a critical pipeline step crashes.

    Used to abort the pipeline early when ingest or sort fail fatally,
    since downstream steps depend on their output.
    """


class Pipeline:
    """Sequential exhaustive pipeline orchestrator.

    Executes 7 phases producing 9 StepReports. Each phase must
    complete fully before the next one starts. The dispatch phase
    only runs if verified items exist.

    Attributes:
        config: Config with paths and disk layout.
        settings: Pipeline configuration (secrets, thresholds).
        dry_run: Preview mode — no filesystem changes.
        interactive: Prompt user for ambiguous matches.
        verbose: Show per-item details in console output.
        console: Rich console for output.
        skip_trailers: Skip the trailers download step entirely.
        continue_on_trailer_error: Continue to dispatch even when the
            trailers step returns status=error.
    """

    def __init__(
        self,
        config: Config,
        settings: Settings,
        dry_run: bool = False,
        interactive: bool = False,
        verbose: bool = False,
        console: Console | None = None,
        step_overrides: Mapping[str, Callable[..., Any]] | None = None,
        skip_trailers: bool = False,
        continue_on_trailer_error: bool = False,
    ) -> None:
        """Initialize the pipeline.

        Args:
            config: Config with paths and disk layout.
            settings: Pipeline configuration (secrets, thresholds).
            dry_run: If True, preview operations without modifying files.
            interactive: If True, prompt for ambiguous matches.
            verbose: If True, show per-item details.
            console: Rich console. Created if not provided.
            step_overrides: Optional mapping of step name to replacement
                callable. Keys: "ingest", "sort", "clean", "scrape",
                "cleanup", "enforce", "verify", "trailers", "dispatch". Used by tests
                to inject fakes without monkey-patching module globals.
                Default ``None`` means no overrides — production behaviour
                is unchanged.
            skip_trailers: If True, skip the trailers download step.
            continue_on_trailer_error: Non-blocking by default; per-item failures
                are logged and dispatch proceeds. ``continue_on_trailer_error=False``
                (the default) aborts dispatch when the trailers step returns
                ``status='error'`` — typically only on lock contention or unexpected
                crash. Set to ``True`` to log and fall through to dispatch regardless.
        """
        self.config = config
        self.settings = settings
        self.dry_run = dry_run
        self.interactive = interactive
        self.verbose = verbose
        self.console = console or Console()
        self._log = get_logger("pipeline")
        # Freeze into a protocol registry so callers cannot mutate after init.
        self._steps = apply_step_overrides(DEFAULT_STEPS, step_overrides)
        self.skip_trailers = skip_trailers
        self.continue_on_trailer_error = continue_on_trailer_error

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
                                self._log.info("crash_recovery_dispatch_orphan", path=str(item))
                                cleaned += 1
                            except OSError as exc:
                                self._log.warning(
                                    "crash_recovery_cannot_clean",
                                    path=str(item),
                                    error=str(exc),
                                )
            except OSError as exc:
                self._log.warning("crash_recovery_cannot_scan_disk", path=str(disk_config.path), error=str(exc))
                continue

        # 2. Clean expired qBit lockout
        if lockout_path is None:
            lockout_path = _Path.home() / ".cache" / "personalscraper" / "qbit_auth_lockout"
        if lockout_path.exists():
            try:
                age = time.time() - lockout_path.stat().st_mtime
                if age > 3600:
                    lockout_path.unlink(missing_ok=True)
                    self._log.info("crash_recovery_lockout_cleaned", age_s=int(age))
                    cleaned += 1
            except OSError as exc:
                self._log.warning("crash_recovery_cannot_clean_lockout", path=str(lockout_path), error=str(exc))

        # 3. Clean .ingest_tmp_* in staging
        ingest_dir = staging_path(self.config, find_ingest_dir(self.config))
        if ingest_dir.exists():
            cleaned += _cleanup_orphan_temps(ingest_dir)

        if cleaned:
            self._log.info("crash_recovery_done", cleaned=cleaned)
        return cleaned

    def run(self) -> PipelineReport:
        """Execute all pipeline phases sequentially with gates.

        Phase 1: INGEST — complete/ → {ingest_dir}/
        Phase 2: SORT — {ingest_dir}/ → {movies_dir}/, {tvshows_dir}/
        Gate: assert ingest dir empty
        Phase 3: PROCESS — re-clean + dedup + scrape + cleanup
        Phase 4: ENFORCE — validate and correct conventions
        Phase 5: VERIFY — coherence check
        Phase 6: TRAILERS — download trailers (non-blocking by default)
        Phase 7: DISPATCH — only if verified items exist

        Returns:
            PipelineReport with 9 StepReports (ingest, sort, clean,
            scrape, cleanup, enforce, verify, trailers, dispatch).
        """
        from datetime import datetime

        # Bootstrap staging tree on first run (idempotent, no-op if already exists)
        ensure_staging_tree(self.config)

        report = PipelineReport(started_at=datetime.now())
        extras: dict[str, Any] = {
            "skip_trailers": self.skip_trailers,
        }

        # Recover from previous interrupted run (best-effort, never blocks pipeline)
        if not self.dry_run:
            try:
                self._recover_from_previous_run()
            except Exception as exc:
                self._log.error("crash_recovery_failed", error=str(exc), message="Pipeline continues", exc_info=True)
        else:
            self._log.info("crash_recovery_skipped", reason="dry_run")

        # Phase 1: INGEST — abort pipeline on fatal crash because
        # sort depends on ingest having deposited files into ingest_dir
        try:
            self._run_step(
                "ingest",
                lambda: self._steps["ingest"](self._step_context(report, extras)),
                report,
                critical=True,
            )
        except _CriticalStepError:
            self._log.error("pipeline_aborted", step="ingest", reason="fatal_crash")
            report.finished_at = datetime.now()
            return report

        # Phase 2: SORT — abort pipeline on fatal crash because
        # process/scrape depend on files being in category dirs
        try:
            self._run_step(
                "sort",
                lambda: self._steps["sort"](self._step_context(report, extras)),
                report,
                critical=True,
            )
        except _CriticalStepError:
            self._log.error("pipeline_aborted", step="sort", reason="fatal_crash")
            report.finished_at = datetime.now()
            return report

        # GATE: assert ingest dir is empty after sort
        self._check_temp_empty_gate()

        # Phase 3: PROCESS (re-clean + dedup + scrape + cleanup)
        # Returns 3 StepReports added individually
        self._run_process_phase(report, extras)

        # Phase 4: ENFORCE (validate and correct conventions)
        self._run_step(
            "enforce",
            lambda: self._steps["enforce"](self._step_context(report, extras)),
            report,
        )

        # Phase 5: VERIFY
        verified = self._run_step(
            "verify",
            lambda: self._steps["verify"](self._step_context(report, extras)),
            report,
        )
        extras["verified"] = verified or []

        # Phase 6: TRAILERS (non-blocking by default -- partial/skipped does not abort dispatch)
        # Runs after verify so items that failed verify are never downloaded.
        # Runs before dispatch so trailers are placed (Plex-conformant) alongside
        # media in staging and moved together in one atomic dispatch operation.
        self._run_step(
            "trailers",
            lambda: self._steps["trailers"](self._step_context(report, extras)),
            report,
        )

        # _run_step appends the StepReport to report.steps (keyed by step name).
        # Read it back to inspect status without relying on the return value of _run_step,
        # which returns the extra tuple element (None for steps returning only StepReport).
        trailers_step = report.steps.get("trailers")
        if trailers_step is not None and trailers_step.status == "error":
            if not self.continue_on_trailer_error:
                # Trailers step failed and the caller did not opt into ignoring it.
                # Abort before dispatch so a broken trailer acquisition never silently
                # lets corrupted or missing state reach the library.  The CLI catches
                # TrailerStepFailed and exits with code 2 to distinguish this abort
                # from a generic pipeline error (exit 1).
                from personalscraper.trailers.state import TrailerStepFailed  # noqa: PLC0415

                raise TrailerStepFailed(
                    "trailers step failed; use --continue-on-trailer-error to proceed to dispatch anyway"
                )
            # continue_on_trailer_error=True: log the error and fall through to dispatch.
            self._log.warning(
                "trailers_step_error_suppressed",
                status=trailers_step.status,
                hint="continue_on_trailer_error=True — dispatch will proceed despite trailer errors",
            )

        # Phase 7: DISPATCH (only if verified items exist)
        if verified:
            self._run_step(
                "dispatch",
                lambda: self._steps["dispatch"](self._step_context(report, extras)),
                report,
            )
        else:
            self._log.warning("dispatch_skipped", reason="no_dispatchable_items")
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
                self._with_details_payload(
                    "dispatch",
                    StepReport(name="dispatch", skip_count=1, details=["Skipped: no verified items"]),
                ),
            )

        report.finished_at = datetime.now()
        return report

    def _step_context(self, report: PipelineReport, extras: dict[str, Any]) -> StepContext:
        """Build a StepContext for the current pipeline state."""
        return StepContext(
            config=self.config,
            settings=self.settings,
            dry_run=self.dry_run,
            interactive=self.interactive,
            verbose=self.verbose,
            console=self.console,
            upstream=report.steps,
            extras=extras,
        )

    def _run_process_phase(self, report: PipelineReport, extras: dict[str, Any]) -> None:
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
            extras: Mutable artifact map shared by step adapters.
        """
        self._run_step(
            "clean",
            lambda: self._steps["clean"](self._step_context(report, extras)),
            report,
        )

        self._run_step(
            "scrape",
            lambda: self._steps["scrape"](self._step_context(report, extras)),
            report,
        )

        self._run_step(
            "cleanup",
            lambda: self._steps["cleanup"](self._step_context(report, extras)),
            report,
        )

    def _check_temp_empty_gate(self) -> None:
        """Gate: verify ingest dir is empty after sort.

        Logs a warning if unsorted files remain but does NOT block
        the pipeline. The remaining files will be processed on the
        next run.
        """
        from personalscraper.sorter.run import assert_temp_empty

        remaining = assert_temp_empty(self.settings, staging_dir=self.config.paths.staging_dir, config=self.config)
        if remaining:
            self._log.warning(
                "ingest_dir_not_empty",
                count=len(remaining),
                sample=remaining[:5],
            )
            self.console.print(
                f"   [yellow]! Ingest dir not empty: {len(remaining)} files remain[/yellow]",
                highlight=False,
            )

    def _step_icon(self, name: str) -> str:
        """Return the step number indicator for console output.

        Args:
            name: Step name.

        Returns:
            Formatted step number string (e.g. "[cyan]1/9[/cyan]").
        """
        icons = {
            "ingest": "[cyan]1/9[/cyan]",
            "sort": "[cyan]2/9[/cyan]",
            "clean": "[cyan]3/9[/cyan]",
            "scrape": "[cyan]4/9[/cyan]",
            "cleanup": "[cyan]5/9[/cyan]",
            "enforce": "[cyan]6/9[/cyan]",
            "verify": "[cyan]7/9[/cyan]",
            "trailers": "[cyan]8/9[/cyan]",
            "dispatch": "[cyan]9/9[/cyan]",
        }
        return icons.get(name, "")

    def _with_details_payload(self, name: str, step_report: StepReport) -> StepReport:
        """Attach the typed empty payload expected for a pipeline step."""
        if step_report.details_payload is None:
            payload_type = STEP_REPORT_CONTRACT.get(name)
            if payload_type is not None:
                step_report.details_payload = payload_type()
        return step_report

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
        self._log.info("step_started", step=name)
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
            step_report = self._with_details_payload(name, step_report)
            report.add_step(name, step_report)
        except Exception as exc:
            crashed = True
            self._log.exception("step_fatal", step=name, error=str(exc))
            error_msg = f"{type(exc).__name__}: {exc}"
            step_report = StepReport(
                name=name,
                error_count=1,
                details=[f"Fatal: {error_msg}"],
            )
            step_report = self._with_details_payload(name, step_report)
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
            "step_finished",
            step=name,
            ok=ok,
            skip=skip,
            err=err,
            elapsed_s=round(elapsed, 1),
        )

        if crashed and critical:
            raise _CriticalStepError(f"Critical step '{name}' crashed")

        return extra
