"""Sequential exhaustive pipeline orchestrator.

Executes 7 phases producing 9 StepReports:
INGEST → SORT → (gate: ingest dir empty) → PROCESS (clean, scrape, cleanup)
→ ENFORCE → VERIFY → TRAILERS → DISPATCH.

Each phase must complete fully before the next one starts. The dispatch
phase only runs if verified items exist. Phase 3 (PROCESS) runs 3
independent sub-steps, each with its own error isolation.
"""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import ensure_staging_tree, find_ingest_dir, staging_path
from personalscraper.config import Settings
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import current_correlation_id
from personalscraper.logger import get_logger
from personalscraper.models import PipelineReport, StepReport
from personalscraper.pause import PauseController
from personalscraper.pipeline_events import (
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepErrored,
    StepStarted,
)
from personalscraper.pipeline_protocol import StepContext
from personalscraper.pipeline_steps import DEFAULT_STEPS, STEP_SPECS, apply_step_overrides
from personalscraper.reports import STEP_REPORT_CONTRACT

if TYPE_CHECKING:
    from personalscraper.pipeline_history import PipelineRunWriter


class _CriticalStepError(Exception):
    """Raised internally when a critical pipeline step crashes.

    Used to abort the pipeline early when ingest or sort fail fatally,
    since downstream steps depend on their output.
    """


class _PipelineInterrupted(Exception):
    """Raised internally when the operator requested graceful shutdown.

    Honored at step boundaries only — the current step's atomic unit
    finishes before the pipeline aborts. ``PipelineEnded`` is emitted
    by the normal finally path so subscribers always see a clean
    lifecycle pair.
    """


class Pipeline:
    """Sequential exhaustive pipeline orchestrator.

    Executes 7 phases producing 9 StepReports. Each phase must
    complete fully before the next one starts. The dispatch phase
    only runs if verified items exist.

    ``Pipeline.__init__`` accepts ONLY an :class:`AppContext`. All
    run-scope flags (``dry_run``, ``interactive``, ``verbose``), the step
    overrides, and the trailer-step toggles are keyword-only parameters
    on :meth:`run`. Each call to ``run`` generates a fresh ``run_id`` and
    binds ``current_correlation_id`` to it for the lifetime of the call.

    Attributes:
        config: Shortcut for ``self._app.config`` (read-only property).
        settings: Shortcut for ``self._app.settings`` (read-only property).
    """

    def __init__(self, app: AppContext) -> None:
        """Initialize the pipeline.

        Args:
            app: Process-scoped service bundle (``config``, ``settings``,
                ``event_bus``, ``provider_registry``). All other knobs are
                run-scope and live on :meth:`run` as keyword-only
                parameters.
        """
        self._app: AppContext = app
        self._log = get_logger("pipeline")

        # Provider registry: instantiated once per process at boot
        # (DESIGN §6.1) by ``_build_app_context``. The pipeline reads it
        # from the bundle rather than constructing its own — feat/registry
        # §5.2 / sub-phase 3.1.
        self._registry = app.provider_registry
        # Run-scope state below is (re)assigned at the start of every
        # ``run`` call so existing helper methods can read it via ``self``.
        # Defaults are conservative no-op values used only if a helper
        # somehow reads them before ``run`` is invoked.
        self.dry_run: bool = False
        self.interactive: bool = False
        self.verbose: bool = False
        self._steps = DEFAULT_STEPS
        self.skip_trailers: bool = False
        self.continue_on_trailer_error: bool = False
        self._pause: PauseController | None = None
        # Run-history writer state (pipe-control sub-phase 1.3b).
        # Initialized in ``run()`` when a ``history_writer`` is injected;
        # read by ``_run_step`` for per-step timing records.
        self._run_uid: str | None = None
        self._history_writer: PipelineRunWriter | None = None
        # Zero-arg callable returning the captured log tail for the
        # ``output_tail`` column; injected per-run alongside the writer.
        self._output_tail_provider: Callable[[], str | None] | None = None
        # Per-run UUID, regenerated at the start of every ``run`` call.
        self._run_id: UUID = uuid4()
        # SIGINT / programmatic shutdown signal — checked at each step
        # boundary in :meth:`_run_step`. Reset at the top of every run.
        self._shutdown_requested: bool = False
        self._shutdown_reason: str | None = None

    @property
    def config(self) -> Config:
        """Return the typed JSON5 configuration bundled in ``app``."""
        return self._app.config

    @property
    def settings(self) -> Settings:
        """Return the Pydantic env-var settings bundled in ``app``."""
        return self._app.settings

    def request_shutdown(self, reason: str = "external_request") -> None:
        """Signal the pipeline to abort at the next step boundary.

        Non-blocking: the current step (if any) keeps running until its
        atomic unit completes; the abort happens before the next step
        starts via :meth:`_check_shutdown_requested`.

        Args:
            reason: Free-form label preserved in the structured log
                emitted when the shutdown is honored. Defaults to
                ``"external_request"``; the SIGINT handler installed by
                :meth:`run` passes ``"signal_SIGINT"``.
        """
        self._shutdown_requested = True
        self._shutdown_reason = reason

    def _check_shutdown_requested(self, boundary: str) -> None:
        """Raise :class:`_PipelineInterrupted` if a shutdown was signalled.

        Args:
            boundary: Identifier of the boundary being checked
                (e.g. ``"before_sort"``). Logged at the abort point.

        Raises:
            _PipelineInterrupted: When :attr:`_shutdown_requested` is
                ``True``. The exception travels up to :meth:`run`'s
                try-block and is caught there for clean PipelineEnded
                emission via the existing finally path.
        """
        if not self._shutdown_requested:
            return
        self._log.warning(
            "pipeline_shutdown_honored",
            boundary=boundary,
            reason=self._shutdown_reason,
        )
        raise _PipelineInterrupted(self._shutdown_reason or "shutdown_requested")

    def _install_sigint_handler(self) -> Any:
        """Install a SIGINT handler that calls :meth:`request_shutdown`.

        Returns:
            The previous handler (so :meth:`run`'s finally can restore
            it), or ``None`` when signal installation is not possible
            (non-main thread, embedded interpreter, etc.). The pipeline
            still works in that case — :meth:`request_shutdown` can be
            invoked programmatically.
        """

        def _handler(signum: int, _frame: FrameType | None) -> None:
            self.request_shutdown(reason=f"signal_{signal.Signals(signum).name}")

        try:
            return signal.signal(signal.SIGINT, _handler)
        except (ValueError, OSError):
            return None

    def _restore_sigint_handler(self, previous: Any) -> None:
        """Restore a previously captured SIGINT handler. Best-effort."""
        if previous is None:
            return
        try:
            signal.signal(signal.SIGINT, previous)
        except (ValueError, OSError):
            pass

    def _recover_from_previous_run(
        self,
        lockout_path: Path | None = None,
    ) -> int:
        """Clean up artifacts from a previous interrupted pipeline run.

        Runs ONCE at pipeline startup (before INGEST) as the single owner of
        crash-recovery orphan cleanup (PIPELINE-CORE-07). Delegates to
        :func:`personalscraper.dispatch.crash_recovery.sweep_orphans` over the
        union of roots:

        1. Every storage disk AND the staging tree — ``_tmp_dispatch_*`` staging
           dirs and ``.merge_backup/`` restore snapshots.
        2. The ingest directory — ``.ingest_tmp_*`` copy stages.
        3. The stale qBit auth-lockout file (>1 hour).

        Because boot owns the sweep, the ingest and dispatch steps pass
        ``recover_orphans=False`` during a full run, so no sweep runs twice.

        Args:
            lockout_path: Override lockout file path (for testing).
                Defaults to ~/.cache/personalscraper/qbit_auth_lockout.

        Returns:
            Number of artifacts cleaned.
        """
        from personalscraper.dispatch.crash_recovery import (
            DryRunPolicy,
            RootKind,
            SweepRoot,
            sweep_orphans,
        )

        if lockout_path is None:
            lockout_path = Path.home() / ".cache" / "personalscraper" / "qbit_auth_lockout"

        roots: list[SweepRoot] = [
            SweepRoot(disk_config.path, RootKind.MEDIA_TREE, DryRunPolicy.REPORT) for disk_config in self.config.disks
        ]
        roots.append(SweepRoot(self.config.paths.staging_dir, RootKind.MEDIA_TREE, DryRunPolicy.SKIP))
        roots.append(SweepRoot(staging_path(self.config, find_ingest_dir(self.config)), RootKind.INGEST_DIR))
        roots.append(SweepRoot(lockout_path, RootKind.LOCKOUT_FILE))

        # Boot recovery always applies real cleanup (guarded to non-dry-run runs
        # by the caller); dry_run=False.
        cleaned = sweep_orphans(roots, dry_run=False)
        if cleaned:
            self._log.info("crash_recovery_done", cleaned=cleaned)
        return cleaned

    def run(
        self,
        *,
        dry_run: bool = False,
        interactive: bool = False,
        verbose: bool = False,
        step_overrides: Mapping[str, Callable[..., Any]] | None = None,
        skip_trailers: bool = False,
        continue_on_trailer_error: bool = False,
        no_post_maintenance: bool = False,
        trigger_reason: str = "cli",
        history_writer: PipelineRunWriter | None = None,
        output_tail_provider: Callable[[], str | None] | None = None,
    ) -> PipelineReport:
        """Execute all pipeline phases sequentially with gates.

        Phase 1: INGEST — complete/ → {ingest_dir}/
        Phase 2: SORT — {ingest_dir}/ → {movies_dir}/, {tvshows_dir}/
        Gate: assert ingest dir empty
        Phase 3: PROCESS — re-clean + dedup + scrape + cleanup
        Phase 4: ENFORCE — validate and correct conventions
        Phase 5: VERIFY — coherence check
        Phase 6: TRAILERS — download trailers (non-blocking by default)
        Phase 7: DISPATCH — only if verified items exist

        Args:
            dry_run: If True, preview operations without modifying files.
            interactive: If True, prompt for ambiguous matches.
            verbose: If True, show per-item details.
            step_overrides: Optional mapping of step name to replacement
                callable. Used by tests to inject fakes.
            skip_trailers: If True, skip the trailers download step.
            continue_on_trailer_error: When True, log the trailers step
                error and proceed to dispatch; when False (the default),
                abort dispatch on a trailers step error.
            no_post_maintenance: When True, skip post-dispatch index
                maintenance (scan/relink/fix) even when the config toggle
                is enabled. Defaults to ``False``.
            trigger_reason: How this run was triggered (``'cli'``,
                ``'web'``, ``'cron'``). Stored in the ``pipeline_run``
                history row. Defaults to ``'cli'``.
            history_writer: Optional :class:`PipelineRunWriter` for
                recording per-step timings and run outcome into the
                ``pipeline_run`` table. When ``None`` (the default), run
                history is not written. This is an injected dependency —
                the caller (CLI / web handler) owns the DB path.
            output_tail_provider: Optional zero-arg callable returning the
                captured log tail (last 64 KiB) to persist as
                ``pipeline_run.output_tail`` at finalize time. The CLI
                installs a :class:`~personalscraper.run_journal.LogTailHandler`
                and passes its ``tail`` method here, so every trigger path
                (cli / web / safety_net) gets a durable journal. Fail-soft:
                a provider error is logged and the row is finalized without
                a tail.

        Returns:
            PipelineReport with 9 StepReports (ingest, sort, clean,
            scrape, cleanup, enforce, verify, trailers, dispatch).
        """
        from datetime import datetime

        # Promote run-scope kwargs to instance state so helper methods can
        # read them via ``self``. Each call to ``run`` overwrites the
        # previous values — the Pipeline is not concurrent-safe by design.
        self.dry_run = dry_run
        self.interactive = interactive
        self.verbose = verbose
        self._steps = apply_step_overrides(DEFAULT_STEPS, step_overrides)
        self.skip_trailers = skip_trailers
        self.continue_on_trailer_error = continue_on_trailer_error

        # Fresh per-run UUID; bind it inside the ``try`` block so the
        # ``finally`` reset is reached even if pre-emit setup raises
        # (``ensure_staging_tree``, ``PipelineReport()`` construction, the
        # ``PipelineStarted`` emit). Setting the ContextVar before ``try:``
        # would leak the binding into the calling task on any of those
        # exception paths.
        _env_uid = os.environ.get("PERSONALSCRAPER_RUN_UID")
        if _env_uid:
            try:
                self._run_id = UUID(hex=_env_uid)
            except (ValueError, TypeError):
                self._log.debug("run_id_env_parse_failed", env_value=_env_uid)
                self._run_id = uuid4()
        else:
            self._run_id = uuid4()
        # Reset shutdown signal at the top of every run; dry-runs are
        # observational and intentionally skip the SIGINT install so
        # they never alter process-wide signal state.
        self._shutdown_requested = False
        self._shutdown_reason = None
        # Wire the pause controller's shutdown gate to the pipeline's own
        # ``_check_shutdown_requested`` so that a SIGINT / programmatic
        # shutdown during a pause raises ``_PipelineInterrupted`` and the
        # run's ``finally`` block can emit ``PipelineEnded`` cleanly.
        self._pause = PauseController(
            pause_file=self.config.paths.data_dir / "pipeline.pause",
            event_bus=self._app.event_bus,
            shutdown_check=lambda: self._check_shutdown_requested(
                boundary="during_pause",
            ),
        )
        previous_sigint = None if self.dry_run else self._install_sigint_handler()
        report = PipelineReport(started_at=datetime.now())
        extras: dict[str, Any] = {
            "skip_trailers": self.skip_trailers,
            "no_post_maintenance": no_post_maintenance,
            # Step adapters that need the registry (currently ``ScrapeStep``)
            # pick it up via ``ctx.extras["registry"]``. Keeping it here avoids
            # widening ``AppContext`` (boundary-only rule, DESIGN §Architecture).
            "registry": self._registry,
        }

        token = current_correlation_id.set(str(self._run_id))
        run_outcome = "success"  # pipe-control sub-phase 1.3b
        try:
            # Bootstrap staging tree on first run (idempotent, no-op if already exists)
            ensure_staging_tree(self.config)

            self._app.event_bus.emit(PipelineStarted(report=report))

            # Run-history insert (pipe-control sub-phase 1.3b):
            # record the run start in ``pipeline_run`` before any step
            # work begins.  The writer is injected by the caller (CLI /
            # web handler) — the pipeline never resolves a DB path itself.
            self._run_uid = self._run_id.hex
            self._history_writer = history_writer
            self._output_tail_provider = output_tail_provider
            if self._history_writer is not None:
                self._history_writer.insert(
                    self._run_uid,
                    trigger_reason,
                    dry_run,
                    os.getpid(),
                )

            # Recover from previous interrupted run (best-effort, never blocks pipeline)
            if not self.dry_run:
                try:
                    self._recover_from_previous_run()
                except Exception as exc:
                    self._log.error(
                        "crash_recovery_failed",
                        error=str(exc),
                        message="Pipeline continues",
                        exc_info=True,
                    )
            else:
                self._log.info("crash_recovery_skipped", reason="dry_run")

            # Phases 1-7 execute in STEP_SPECS order (INGEST → SORT → CLEAN →
            # SCRAPE → CLEANUP → ENFORCE → VERIFY → TRAILERS → DISPATCH). Each
            # step is driven entirely by its spec — no per-step branching in the
            # orchestrator: ``critical`` aborts the run on a fatal crash (sort/
            # process depend on ingest's and sort's output); ``extras_key``
            # publishes a step's extra return to the shared ``extras`` (verify
            # exposes its verified-path list); ``skip_when`` synthesises a
            # symmetric skip report through the normal ``_run_step`` path
            # (dispatch skips when nothing passed verify). Three between-step
            # actions that are NOT per-step policy stay explicit: the post-sort
            # empty-ingest gate, the post-scrape reclean-revert (F3 parity with
            # the CLI ``run_process`` path), and the post-trailers error gate.
            for spec in STEP_SPECS:
                ctx = self._step_context(report, extras)
                skip_when = partial(spec.skip_when, ctx) if spec.skip_when is not None else None
                skip_reason = getattr(spec.skip_when, "reason", None)
                try:
                    extra = self._run_step(
                        spec.name,
                        partial(self._steps[spec.name], ctx),
                        report,
                        critical=spec.critical,
                        skip_when=skip_when,
                        skip_reason=skip_reason,
                    )
                except _CriticalStepError:
                    self._log.error("pipeline_aborted", step=spec.name, reason="fatal_crash")
                    report.finished_at = datetime.now()
                    return report

                if spec.extras_key is not None:
                    extras[spec.extras_key] = extra or []

                if spec.name == "sort":
                    # GATE: ingest dir must be empty after sort (warn-only).
                    self._check_temp_empty_gate()
                elif spec.name == "scrape":
                    # F3 parity: revert reclean renames the scraper could not
                    # match so the folders keep their original torrent name and
                    # stay rescrape-eligible — the same point (after scrape,
                    # before cleanup) the CLI ``run_process`` path reverts.
                    self._revert_unmatched_recleans(report)
                elif spec.name == "trailers":
                    # Abort before dispatch on a trailers error unless opted out.
                    self._handle_trailers_error(report)

        except _PipelineInterrupted as exc:
            # Operator-requested shutdown honored at a step boundary.
            # The remaining steps are skipped; the finally below still
            # emits ``PipelineEnded`` so subscribers see a clean pair.
            run_outcome = "killed"
            self._log.warning(
                "pipeline_interrupted",
                reason=str(exc),
                completed_steps=list(report.steps.keys()),
            )
        except Exception:
            # Unhandled exception during pipeline body — record error
            # outcome so the finally block's history writer sees it.
            run_outcome = "error"
            raise
        finally:
            if report.finished_at is None:
                report.finished_at = datetime.now()
            # Defensive try/except + nested finally so ``reset(token)`` runs
            # even if the warning logger itself raises. The bus already
            # isolates subscriber faults per-callback; only event construction
            # itself (e.g. a malformed report) can land in the except branch.
            try:
                try:
                    self._app.event_bus.emit(PipelineEnded(report=report))
                except Exception:
                    # WARNING because the pipeline body completed —
                    # failure to emit the lifecycle event is observability
                    # rot, not a run-level failure.
                    self._log.warning("pipeline_ended_emit_failed", exc_info=True)
                # Run-history finalize (pipe-control sub-phase 1.3b):
                # record the run outcome after ``PipelineEnded`` so
                # subscribers see a complete lifecycle before the DB row
                # is finalized.
                if self._history_writer is not None:
                    assert self._run_uid is not None  # set at top of run()
                    output_tail: str | None = None
                    if self._output_tail_provider is not None:
                        try:
                            output_tail = self._output_tail_provider()
                        except Exception:
                            # Fail-soft: a tail-capture error must never
                            # prevent the row from being finalized.
                            self._log.warning("output_tail_provider_failed", exc_info=True)
                    self._history_writer.finalize(self._run_uid, run_outcome, output_tail=output_tail)
            finally:
                current_correlation_id.reset(token)
                self._restore_sigint_handler(previous_sigint)
            # Cleanup provider registry resources (best-effort, never blocks
            # the pipeline report from being returned). Must run AFTER the
            # PipelineEnded emit so subscribers can still introspect the
            # registry during the event.
            try:
                self._registry.close()
            except Exception:
                self._log.warning("registry_close_failed", exc_info=True)

        return report

    def _step_context(self, report: PipelineReport, extras: dict[str, Any]) -> StepContext:
        """Build a StepContext for the current pipeline state."""
        # config + settings are derived from app via __post_init__
        # (sub-phase 2.2a) — they are NOT constructor args anymore.
        return StepContext(
            app=self._app,
            run_id=self._run_id,
            dry_run=self.dry_run,
            interactive=self.interactive,
            verbose=self.verbose,
            upstream=report.steps,
            extras=extras,
        )

    def _handle_trailers_error(self, report: PipelineReport) -> None:
        """Abort before dispatch when the trailers step errored, unless opted out.

        Extracted from the inline post-trailers branch so the spec loop stays
        declarative. When the trailers step reports ``status == "error"`` and
        ``continue_on_trailer_error`` is False, raises
        :class:`~personalscraper.trailers.state.TrailerStepFailed` so a broken
        trailer acquisition never lets corrupted or missing state reach the
        library (the CLI maps it to exit code 2, distinct from a generic
        pipeline error at exit 1). Otherwise logs and returns so dispatch
        proceeds.

        Args:
            report: The run's report; the trailers ``StepReport`` is read back
                by name (``_run_step`` already appended it).

        Raises:
            TrailerStepFailed: When trailers errored and the caller did not opt
                into ignoring it.
        """
        trailers_step = report.steps.get("trailers")
        if trailers_step is None or trailers_step.status != "error":
            return
        if not self.continue_on_trailer_error:
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

    def _revert_unmatched_recleans(self, report: PipelineReport) -> None:
        """Revert reclean renames the scraper could not match (F3, CLI parity).

        Runs between the ``scrape`` and ``cleanup`` steps — the same point the
        CLI :func:`personalscraper.process.run.run_process` path reverts.
        Delegates to the single shared owner
        :func:`personalscraper.process.run.revert_unmatched_recleans`, threading
        the reclean rename map (from the ``clean`` step report) and the scraper's
        unmatched folder set (from the ``scrape`` step report) — both already
        live in ``report.steps``. The shared owner takes ``Config`` (not
        ``AppContext``), so this respects the ``process/`` boundary rule.

        A no-op when either step is absent from the report (e.g. a
        crash-synthesised report never registered) or when reclean renamed
        nothing.

        Args:
            report: The in-flight :class:`PipelineReport`; its ``clean`` and
                ``scrape`` step reports carry the rename map and unmatched set.
        """
        from personalscraper.process.run import revert_unmatched_recleans  # noqa: PLC0415

        clean_report = report.steps.get("clean")
        scrape_report = report.steps.get("scrape")
        if clean_report is None or scrape_report is None:
            return
        revert_unmatched_recleans(
            self.config,
            clean_report,
            scrape_report,
            dry_run=self.dry_run,
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

    def _with_details_payload(self, name: str, step_report: StepReport) -> StepReport:
        """Validate and normalise ``details_payload`` against ``STEP_REPORT_CONTRACT``.

        Delegates to :func:`personalscraper.reports._validate.validate_details_payload`.

        Raises:
            StepReportContractError: If the step is under contract and produced a
                payload whose type/shape does not match the declared dataclass.
        """
        from personalscraper.reports._validate import validate_details_payload

        return validate_details_payload(name, step_report, STEP_REPORT_CONTRACT)

    def _emit_skipped_step(self, name: str, report: PipelineReport, reason: str) -> None:
        """Synthesise and emit a symmetric skip report for a spec-skipped step.

        Emits the same ``StepStarted``/``StepCompleted`` pair a real step would,
        attaches the honest empty typed payload (contract-shaped via
        :meth:`_with_details_payload`), and records the skip in run-history with
        status ``"skipped"``. This is the single owner of the "skip a step but
        keep the lifecycle symmetric" behaviour — it replaces the old inline
        no-verified-items dispatch synthesis. Callers (``_run_step``) must have
        already cleared the shutdown/pause boundary checks.

        Args:
            name: Step name (e.g. ``"dispatch"``).
            report: The run's report; the skip report is appended in place.
            reason: Operator-facing reason recorded as ``"Skipped: {reason}"``.
        """
        self._log.warning("step_skipped", step=name, reason=reason)
        self._app.event_bus.emit(StepStarted(step=name))
        step_report = StepReport(name=name, skip_count=1, details=[f"Skipped: {reason}"])
        step_report = self._with_details_payload(name, step_report)
        report.add_step(name, step_report)
        self._app.event_bus.emit(StepCompleted(step=name, report=step_report, elapsed_s=0.0))
        # Run-history: record the synthesized (skipped) step so history keeps all
        # nine steps (pipe-control sub-phase 1.3b). Status ``"skipped"`` is pinned
        # by tests/pipeline/test_run_history_wiring.py.
        if self._history_writer is not None and self._run_uid is not None:
            skip_ts = time.time()
            self._history_writer.update_step(
                self._run_uid,
                name,
                skip_ts,
                skip_ts,
                "skipped",
                success_count=step_report.success_count,
                skip_count=step_report.skip_count,
                error_count=step_report.error_count,
                unmatched_count=len(step_report.unmatched_paths),
                counts=dict(step_report.counts),
            )

    def _run_step(
        self,
        name: str,
        fn: Callable[[], Any],
        report: PipelineReport,
        *,
        critical: bool = False,
        skip_when: Callable[[], bool] | None = None,
        skip_reason: str | None = None,
    ) -> Any:
        """Execute a pipeline step with logging, timing, and bus emit.

        Emits :class:`StepStarted` at entry, :class:`StepCompleted` on success,
        and :class:`StepErrored` on exception via ``self._app.event_bus``.

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
            skip_when: Optional zero-arg predicate (the spec's ``skip_when``
                pre-bound to this step's context). When it returns True, the
                step is skipped: a symmetric skip report is synthesised via
                :meth:`_emit_skipped_step` instead of invoking ``fn``, and the
                extra return is ``None``.
            skip_reason: Operator-facing reason for the synthesised skip report;
                falls back to a generic phrase when the predicate carries none.

        Returns:
            Extra data from fn (e.g. verified list), or None (also for a skip).

        Raises:
            _CriticalStepError: If ``critical=True`` and fn raises.
            _PipelineInterrupted: If the operator signalled shutdown
                (SIGINT or :meth:`request_shutdown`) before this step
                started. The check happens before any emit so the
                interrupted step never appears in the bus history.
        """
        # Step-boundary shutdown check (sub-phase 4.2): honored BEFORE
        # any emit or work so the interrupted step never produces an
        # asymmetric StepStarted/StepCompleted pair.
        self._check_shutdown_requested(boundary=f"before_{name}")

        # Pause checkpoint (pipe-control sub-phase 1.2): if the
        # ``pipeline.pause`` sentinel exists, block until it is cleared
        # or a shutdown is signalled. MUST run BEFORE ``StepStarted`` so
        # a paused step never appears in the bus history as "started".
        if self._pause is not None:
            self._pause.checkpoint()

        # Declarative skip (spec ``skip_when``): synthesise a symmetric skip
        # report through the SAME lifecycle a real step emits. Runs AFTER the
        # shutdown/pause boundary checks so a skipped step honours a pending
        # shutdown exactly like a real one.
        if skip_when is not None and skip_when():
            self._emit_skipped_step(name, report, skip_reason or "skip condition met")
            return None

        # Bus is the sole emit path (Phase 3.7b).
        # No companion ``log.info("step_started", step=name)`` — the
        # StepStarted event carries the same ``step`` discriminator; per
        # Sub-phase 3.8 audit, emit sites do not double-log.
        self._app.event_bus.emit(StepStarted(step=name))

        t0 = time.monotonic()
        # Epoch clock for persisted step timestamps (R12): steps_json readers
        # (GET /history/{run_uid}) render with datetime.fromtimestamp, so the
        # stored values MUST be time.time(). t0 stays monotonic for elapsed.
        step_started_at = time.time()
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
            # The event carries the exception class + message; the structlog
            # call carries the traceback via ``exc_info`` (DESIGN §Logging
            # convention — distinct info, NOT duplicated info, see 3.8 audit).
            self._log.exception("step_fatal", step=name, error=str(exc))
            self._app.event_bus.emit(
                StepErrored(
                    step=name,
                    error_class=type(exc).__name__,
                    error_message=str(exc),
                ),
            )
            # Run-history step record (pipe-control sub-phase 1.3b):
            # capture the step failure with elapsed wall-clock time.
            if self._history_writer is not None:
                assert self._run_uid is not None  # set at top of run()
                # webui-ux Phase 2.2: a crashed step contributes one error to
                # the persisted summary so the last-run report reflects it.
                self._history_writer.update_step(
                    self._run_uid,
                    name,
                    step_started_at,
                    step_started_at + (time.monotonic() - t0),
                    "error",
                    success_count=0,
                    skip_count=0,
                    error_count=1,
                    unmatched_count=0,
                )
            error_msg = f"{type(exc).__name__}: {exc}"
            step_report = StepReport(
                name=name,
                error_count=1,
                details=[f"Fatal: {error_msg}"],
            )
            step_report = self._with_details_payload(name, step_report)
            report.add_step(name, step_report)

        elapsed = time.monotonic() - t0

        if not crashed:
            self._app.event_bus.emit(
                StepCompleted(step=name, report=step_report, elapsed_s=elapsed),
            )
            # Run-history step record (pipe-control sub-phase 1.3b):
            # capture the step completion with elapsed wall-clock time.
            # webui-ux Phase 2.2: also persist the StepReport summary counts so
            # the interpreted last-run report survives past the live WS stream.
            if self._history_writer is not None:
                assert self._run_uid is not None  # set at top of run()
                # Persist the skip/defer/error reasons (§8): StepReport.warnings
                # (e.g. orphan tracker entry, insufficient disk space) + .details
                # (e.g. "Aborted: N consecutive failures", "No torrent client
                # configured") otherwise died with the process and history showed
                # only bare counts. Warnings first — they are the per-item "why".
                reasons = [*step_report.warnings, *step_report.details]
                self._history_writer.update_step(
                    self._run_uid,
                    name,
                    step_started_at,
                    step_started_at + elapsed,
                    "success",
                    success_count=step_report.success_count,
                    skip_count=step_report.skip_count,
                    error_count=step_report.error_count,
                    unmatched_count=len(step_report.unmatched_paths),
                    counts=dict(step_report.counts),
                    reasons=reasons or None,
                )

        ok = step_report.success_count
        skip = step_report.skip_count
        err = step_report.error_count

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
