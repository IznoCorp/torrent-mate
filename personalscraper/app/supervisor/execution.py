"""Today's pipeline run and library item rescrape, as callables.

The bodies the ``run`` and ``library-rescrape-item`` commands used to carry, moved here unchanged so
that a caller other than the CLI can run them. The caller owns ``pipeline.lock``: a body here runs
under a lock it was handed, never takes one. A body returns the exit code the command raises; it
imports engine modules only, never ``commands`` nor ``cli_helpers``.
"""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import structlog.contextvars

from personalscraper.acquire.events import WatcherRunTriggered
from personalscraper.app.composition import build_app_context
from personalscraper.app.supervisor.model import (
    RunOptions as RunOptions,
)  # re-exported: the CLI and the tests import it from here
from personalscraper.core.sqlite import SqliteMigrationError
from personalscraper.i18n import t
from personalscraper.indexer import migrations as _migrations_pkg
from personalscraper.indexer.db import (
    IndexerCorruptError,
    IndexerDiskFullError,
    IndexerInvalidPathError,
    apply_migrations,
    ensure_library_schema,
    open_db,
)
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.run_journal import LogTailHandler
from personalscraper.subscribers.debug_log import DebugLogSubscriber
from personalscraper.trailers.state import TrailerStepFailed

if TYPE_CHECKING:
    from rich.console import Console

    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.app_context import AppContext
    from personalscraper.core.event_bus import EventBus
    from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber
    from personalscraper.subscribers.plex import PlexSubscriber
    from personalscraper.subscribers.redis_stream import RedisEventPublisher
    from personalscraper.subscribers.rich_console import RichConsoleSubscriber
    from personalscraper.subscribers.telegram import TelegramSubscriber


def _open_history_writer(config: Config) -> PipelineRunWriter | None:
    """Migrate the library DB, then build the run-history writer over it.

    A fresh environment has no library DB yet (only the indexer used to create and migrate it),
    so the run boot brings it to the current schema before the first history write. A store that
    cannot be opened or migrated (locked past the wait, corrupt, newer than this code, bad path)
    is logged ONCE as an error for the run and the run proceeds without history — never one
    swallowed warning per step.

    Args:
        config: Loaded configuration; ``config.indexer.db_path`` is the environment's library DB.

    Returns:
        The writer, or ``None`` when the store is unavailable.
    """
    try:
        db_path = config.indexer.db_path
        assert db_path is not None, "indexer.db_path must be resolved by the loaded Config"
        # A non-path value (a mocked config) would stringify to a junk filesystem path: never migrate it.
        if isinstance(db_path, Path):
            ensure_library_schema(db_path)
        return PipelineRunWriter(db_path=db_path)
    except Exception as exc:  # noqa: BLE001 — history is optional; the run proceeds without it
        get_logger("pipeline").error("pipeline_history.library_db_unavailable", error=str(exc), exc_info=True)
        return None


class _RescrapeFailed(Exception):
    """A rescrape that failed, raised inside the run-row context so the row is recorded as an error.

    ``cli_run_row`` finalizes a self-owned ``pipeline_run`` row as ``error`` only when an exception
    leaves its context; a plain ``return 1`` there would record ``success``. ``rescrape_item`` raises
    this inside the context and turns it back into the return code outside it. The message is the
    exit code, the text the row has always recorded.

    Attributes:
        exit_code: The code ``rescrape_item`` returns.
    """

    def __init__(self, exit_code: int) -> None:
        """Store the exit code as the message.

        Args:
            exit_code: The code ``rescrape_item`` returns.
        """
        super().__init__(str(exit_code))
        self.exit_code = exit_code


class RunRecorder(Protocol):
    """The part of a run-row recorder a rescrape writes to."""

    def record_counts(self, counts: dict[str, int]) -> None:
        """Persist the run's numeric result on its ``pipeline_run`` row.

        Args:
            counts: The counters to record.
        """


class RunRowFactory(Protocol):
    """Opens the ``pipeline_run`` row of a maintenance command (the CLI's ``cli_run_row``)."""

    def __call__(self, config: Config, command: str) -> AbstractContextManager[RunRecorder | None]:
        """Open the row for *command*.

        Args:
            config: Loaded configuration.
            command: The CLI command name the row is recorded under.

        Returns:
            A context manager yielding the recorder, or ``None`` when recording is unavailable.
        """


class StepBoundary(Protocol):
    """Opens the per-invocation :class:`AppContext` (the CLI's ``per_step_boundary``)."""

    def __call__(self, config: Config, settings: Settings) -> AbstractContextManager[AppContext]:
        """Build and bind the context for one invocation.

        Args:
            config: Loaded configuration.
            settings: Loaded settings.

        Returns:
            A context manager yielding the invocation's :class:`AppContext`.
        """


@dataclass
class _RunSubscribers:
    """The event subscribers one pipeline run wires on its bus, closed together after the run."""

    rich: RichConsoleSubscriber | None = None
    telegram: TelegramSubscriber | None = None
    acquisition_telegram: AcquisitionTelegramSubscriber | None = None
    plex: PlexSubscriber | None = None
    debug: DebugLogSubscriber | None = None
    redis_publisher: RedisEventPublisher | None = None

    def close(self) -> None:
        """Close every subscriber that was built, in the order they were wired."""
        if self.rich is not None:
            self.rich.close()
        if self.telegram is not None:
            self.telegram.close()
        if self.acquisition_telegram is not None:
            self.acquisition_telegram.close()
        if self.plex is not None:
            self.plex.close()
        if self.debug is not None:
            self.debug.close()
        if self.redis_publisher is not None:
            self.redis_publisher.close()


def _build_subscribers(
    event_bus: EventBus,
    config: Config,
    settings: Settings,
    *,
    console: Console | None,
    verbose: bool,
    headless: bool,
    no_console: bool,
    dry_run: bool,
    run_id: str,
) -> _RunSubscribers:
    """Wire the run's subscribers on the shared bus (they self-subscribe in their constructors).

    Args:
        event_bus: The run's bus, which the subscribers join.
        config: Loaded configuration.
        settings: Loaded settings.
        console: Where the run prints; ``None`` builds no Rich subscriber.
        verbose: Build the DEBUG event logger and give the Rich subscriber its details.
        headless: Build no console or Telegram subscriber (silent cron / CI runs).
        no_console: Build no Rich subscriber but keep Telegram (the watcher daemon).
        dry_run: Whether the run is a dry run, shown by the Rich subscriber.
        run_id: The run's id, shown by the Rich subscriber.

    Returns:
        The subscribers that were built, to close once the run ends.
    """
    from personalscraper.api.notify.telegram import TelegramNotifier  # noqa: PLC0415 — patched at source by tests
    from personalscraper.api.transport import HttpTransport  # noqa: PLC0415 — patched at source by tests
    from personalscraper.subscribers.acquire import (  # noqa: PLC0415 — patched at source by tests
        AcquisitionTelegramSubscriber,
    )
    from personalscraper.subscribers.plex import build_plex_subscriber  # noqa: PLC0415 — patched at source by tests
    from personalscraper.subscribers.redis_stream import (  # noqa: PLC0415 — patched at source by tests
        build_redis_publisher,
    )
    from personalscraper.subscribers.rich_console import (  # noqa: PLC0415 — patched at source by tests
        RichConsoleSubscriber,
    )
    from personalscraper.subscribers.telegram import TelegramSubscriber  # noqa: PLC0415 — patched at source by tests

    subs = _RunSubscribers()
    # ``--verbose`` activates the DebugLogSubscriber which logs every
    # emitted event at DEBUG. Registered independently of ``--headless``
    # so verbose log streams work even in cron / CI contexts that
    # suppress Rich / Telegram output.
    # Redis event publisher (gate on web.enabled, fail-soft — Redis down
    # must never block the pipeline boot).
    subs.redis_publisher = build_redis_publisher(event_bus, config.web)
    # Plex refresh trigger (plex-refresh D3), through the single owner
    # shared with the standalone ``personalscraper dispatch`` command so
    # both dispatch entry points behave identically. The token is the
    # gate, deliberately OUTSIDE ``--headless``: this one makes the
    # dispatched media visible in Plex rather than producing operator
    # output, so a cron run needs it exactly as much.
    subs.plex = build_plex_subscriber(event_bus, settings)
    if verbose:
        subs.debug = DebugLogSubscriber(event_bus)
    if not headless:
        if console is not None and not no_console:
            subs.rich = RichConsoleSubscriber(
                event_bus,
                console=console,
                verbose=verbose,
                dry_run=dry_run,
                run_id=run_id,
            )
        if TelegramNotifier.is_configured(settings):
            tg_transport = HttpTransport(
                TelegramNotifier.policy(settings.telegram_bot_token),
                event_bus=event_bus,
            )
            tg_notifier = TelegramNotifier(tg_transport, settings.telegram_chat_id)
            subs.telegram = TelegramSubscriber(event_bus, tg_notifier)
            subs.acquisition_telegram = AcquisitionTelegramSubscriber(
                event_bus,
                notifier=tg_notifier,
                enabled=config.notify.acquire_notify_enabled,
            )
    return subs


def execute_run(
    config: Config,
    settings: Settings,
    options: RunOptions,
    *,
    trigger: str,
    console: Console | None,
    verbose: bool,
    headless: bool = False,
    interactive: bool = False,
    no_console: bool = False,
) -> int:
    """Run every pipeline phase via ``Pipeline.run``, under a ``pipeline.lock`` the caller holds.

    Args:
        config: Loaded configuration.
        settings: Loaded settings.
        options: The run's flags (``item_id`` is unused by a pipeline run).
        trigger: The ``--trigger-reason`` the run was started with; empty for a plain CLI run.
        console: Where the run prints; ``None`` prints nothing and builds no Rich subscriber.
        verbose: Log every emitted event at DEBUG and print the step details.
        headless: Build no subscriber (silent cron / CI runs).
        interactive: Confirm low-confidence matches.
        no_console: Disable the Rich console subscriber but keep Telegram active (the watcher daemon).

    Returns:
        The exit code: 0 on success, 1 when the report holds errors, 2 when the trailers step
        aborted the run.
    """
    from personalscraper.api.notify.healthchecks import HealthcheckClient  # noqa: PLC0415 — patched at source by tests
    from personalscraper.api.transport import HttpTransport  # noqa: PLC0415 — patched at source by tests
    from personalscraper.logger import cleanup_old_logs  # noqa: PLC0415 — patched at source by tests
    from personalscraper.pipeline import Pipeline  # noqa: PLC0415 — patched at source by tests

    dry_run = options.dry_run
    skip_trailers = options.skip_trailers
    continue_on_trailer_error = options.continue_on_trailer_error
    no_post_maintenance = options.no_post_maintenance
    trigger_reason = trigger
    _run_log = get_logger("pipeline")

    # The :class:`AppContext` is built once per invocation, here at the top of the run,
    # via :func:`build_app_context` (Sub-phase 2.4 — boundary-only
    # rule from DESIGN §Architecture, enforced by the AST allowlist landed
    # in Sub-phase 2.6). Constructed early so the healthcheck and Telegram
    # transports built below can plumb ``app_context.event_bus`` into their
    # circuit breakers (Sub-phase 4.1).
    # build_torrent_client=True: the full pipeline includes the ingest step,
    # which consumes ctx.torrent_client, so the client is resolved + validated
    # at boot here (DESIGN D3 fail-fast for the run path).
    app_context = build_app_context(config, settings, build_torrent_client=True)

    # Healthcheck client (None if not configured — pings short-circuit at the call site).
    healthcheck: HealthcheckClient | None = None
    if HealthcheckClient.is_configured(settings):
        hc_transport = HttpTransport(
            HealthcheckClient.policy(settings.healthcheck_url),
            event_bus=app_context.event_bus,
        )
        healthcheck = HealthcheckClient(hc_transport)
        healthcheck.ping_start()

    # Pipeline outcome is set to "success" only on the clean-completion path; any other
    # exit (a non-zero return, TrailerStepFailed, unhandled exception) leaves it None and the
    # finally block fires healthcheck.ping_fail() — preserves the dead-man's-switch
    # contract per DESIGN §7.1.
    pipeline_outcome: str | None = None
    try:
        # Clean old logs and bind run context
        cleanup_old_logs()
        structlog.contextvars.clear_contextvars()
        run_id = datetime.now().isoformat(timespec="seconds")
        structlog.contextvars.bind_contextvars(run_id=run_id)

        _run_log.info("pipeline_started", dry_run=dry_run, run_id=run_id)

        # Resolve flag defaults from config when not explicitly set by the caller.
        effective_skip_trailers = skip_trailers or config.trailers.pipeline.skip
        effective_continue_on_trailer_error = continue_on_trailer_error or config.trailers.pipeline.continue_on_error

        # Build subscribers — both self-subscribe in their constructors via the
        # shared AppContext bus. ``--headless`` skips subscriber construction
        # for silent cron / CI runs.
        #
        # ``--no-console`` (used by the Watcher daemon) disables the Rich
        # console subscriber but keeps Telegram subscribers active.
        # ``--headless`` disables both; if both flags are passed, ``--headless``
        # wins (the outer ``not headless`` gate prevents all subscriber
        # construction).
        subscribers = _build_subscribers(
            app_context.event_bus,
            config,
            settings,
            console=console,
            verbose=verbose,
            headless=headless,
            no_console=no_console,
            dry_run=dry_run,
            run_id=run_id,
        )

        # Emit ``WatcherRunTriggered`` before ``PipelineStarted`` when the
        # run is spawned by the Watcher daemon (``--trigger-reason`` set).
        # Subscribers (Telegram, Rich console) are already wired at this
        # point, so they will observe and forward the event.
        if trigger_reason:
            app_context.event_bus.emit(WatcherRunTriggered(reason=trigger_reason))

        # Build run-history writer (pipe-control sub-phase 1.3b).
        # The writer is an injected dependency — the DB path is
        # the one the loaded ``Config`` resolved.  Fail-soft: if construction fails (missing
        # library.db, permission error, etc.) the pipeline runs without
        # history recording.
        history_writer = _open_history_writer(config)

        # Capture the log tail for the durable run journal (universal run
        # journal, 2026-07-08): every trigger path — cli, web-spawned,
        # safety_net — reaches this function through the ``run`` command, so installing the
        # handler here gives all of them an ``output_tail``.
        tail_handler = LogTailHandler()
        tail_handler.install()

        pipeline = Pipeline(app_context)
        try:
            try:
                report = pipeline.run(
                    dry_run=dry_run,
                    interactive=interactive,
                    verbose=verbose,
                    skip_trailers=effective_skip_trailers,
                    continue_on_trailer_error=effective_continue_on_trailer_error,
                    no_post_maintenance=no_post_maintenance,
                    trigger_reason=trigger_reason or "cli",
                    history_writer=history_writer,
                    output_tail_provider=tail_handler.tail,
                )
            finally:
                tail_handler.uninstall()
                subscribers.close()
        except TrailerStepFailed as exc:
            # Trailers step failed and --continue-on-trailer-error was not set.
            # Exit with code 2 (distinct from generic pipeline error exit 1) so
            # scripts / launchd jobs can handle this case explicitly.
            if console is not None:
                console.print("[red]" + t("cli_core.pipeline.aborted", reason=str(exc)) + "[/red]", highlight=False)
            _run_log.error("pipeline_aborted_trailer_step_failed", reason=str(exc))
            return 2

        dur = report.duration()
        minutes = int(dur.total_seconds()) // 60
        seconds = int(dur.total_seconds()) % 60
        dur_str = f"{minutes}min {seconds:02d}s" if minutes else f"{seconds}s"
        _run_log.info("pipeline_finished", duration=dur_str)

        # Mark outcome BEFORE the return so the finally block pings the right state.
        pipeline_outcome = "fail" if report.has_errors() else "success"
        if report.has_errors():
            return 1
    finally:
        # Dead-man's-switch: ping_fail on any non-clean exit (TrailerStepFailed, unexpected
        # exception, a non-zero return due to report errors). HealthcheckClient is itself fail-soft
        # so an unreachable hc-ping.com will not abort the caller's lock release.
        if healthcheck is not None:
            if pipeline_outcome == "success":
                healthcheck.ping_success()
            else:
                healthcheck.ping_fail()
        # The run context is per invocation: structlog contextvars outlive the command
        # in a long-lived process (a worker, the watcher), so ``run_id`` is taken off
        # here rather than left on every later record. A no-op if it was never bound.
        structlog.contextvars.unbind_contextvars("run_id")
    return 0


def rescrape_item(
    config: Config,
    settings: Settings,
    item_id: int,
    *,
    console: Console,
    run_row: RunRowFactory,
    step_boundary: StepBoundary,
) -> int:
    """Re-scrape exactly one library item via TMDB/TVDB, live, under a ``pipeline.lock`` the caller holds.

    The caller has checked that the indexer DB exists. No dry run, no filter, the needs-rescrape
    predicate bypassed, and no library-wide report written.

    Args:
        config: Loaded configuration.
        settings: Loaded settings.
        item_id: The indexer item to re-scrape.
        console: Where the run prints.
        run_row: Opens the ``pipeline_run`` row of the run (the CLI's ``cli_run_row``), so the engine
            never imports the command layer.
        step_boundary: Opens the per-invocation application context (the CLI's ``per_step_boundary``).

    Returns:
        The exit code: 0 on success, 1 on an unreachable index, a bad combination or an unresolved item.
    """
    from personalscraper.maintenance.rescraper import rescrape_library  # noqa: PLC0415 — patched at source by tests

    command = "library-rescrape-item"
    mode = "[bold green]" + t("cli_library.analyze.mode_live") + "[/bold green]"
    console.print("[bold]" + t("cli_library.analyze.rescraping", mode=mode) + "[/bold]")

    # §1/§2 — the repair run is OBSERVABLE: a pipeline_run row (kind
    # maintenance) carries its numeric result, incl. how many items got
    # their artwork back (« Posters récupérés »).
    try:
        with run_row(config, command) as run_rec, step_boundary(config, settings) as app_context:
            # Open the indexer DB connection so that _collect_rescrape_candidates can look the
            # item up by id.  The connection is closed in the finally block below to avoid leaks.
            conn: sqlite3.Connection | None = None
            db_path = config.indexer.db_path
            assert db_path is not None, "indexer.db_path must be resolved by the loaded Config"
            try:
                conn = open_db(db_path, event_bus=app_context.event_bus)
                apply_migrations(conn, Path(_migrations_pkg.__file__).parent)
            except (
                IndexerCorruptError,
                IndexerInvalidPathError,
                IndexerDiskFullError,
                SqliteMigrationError,  # the base: a failed script or a newer schema
            ) as exc:
                console.print("[red]" + t("cli_library.analyze.open_failed_label") + "[/red] " + str(exc))
                if conn is not None:
                    conn.close()
                raise _RescrapeFailed(1) from exc

            try:
                result = rescrape_library(
                    config,
                    conn=conn,
                    disk_filter=None,
                    category_filter=None,
                    item_id=item_id,
                    only=None,
                    interactive=False,
                    dry_run=False,
                    max_items=None,
                    event_bus=app_context.event_bus,
                    registry=app_context.provider_registry,
                )
            except ValueError as exc:
                # Mutual-exclusion error from _collect_rescrape_candidates
                # (item_id combined with disk/category filter).
                console.print("[red]" + t("cli_library.analyze.invalid_combination_label") + "[/red] " + str(exc))
                raise _RescrapeFailed(1) from exc
            finally:
                if conn is not None:
                    conn.close()

            # Warn clearly only when an explicit item RESOLVED no candidate
            # (item not in DB, dispatch path missing, or directory gone). Gate on
            # candidate_count, NOT on fixed+skipped+error: an item that is found
            # but has nothing to do legitimately produces 0 work and must NOT be
            # reported as not-found.
            if result.candidate_count == 0:
                console.print(
                    t(
                        "cli_library.analyze.item_not_found",
                        label="[yellow]" + t("cli_library.analyze.warning_label") + "[/yellow]",
                        item_id=item_id,
                    )
                )
                raise _RescrapeFailed(1)

            if run_rec is not None:
                artwork_recovered = sum(1 for action in result.items if "artwork_downloaded" in action.actions_taken)
                run_rec.record_counts(
                    {
                        "fixed": result.fixed_count,
                        "skipped": result.skipped_count,
                        "errors": result.error_count,
                        "artwork_recovered": artwork_recovered,
                    }
                )
    except _RescrapeFailed as failure:
        return failure.exit_code

    total = result.fixed_count + result.skipped_count + result.error_count
    summary = t(
        "cli_library.analyze.rescrape_summary",
        fixed_label="[green]" + t("cli_library.analyze.fixed_label") + "[/green]",
        fixed=result.fixed_count,
        skipped_label="[yellow]" + t("cli_library.analyze.skipped_label") + "[/yellow]",
        skipped=result.skipped_count,
        errors_label="[red]" + t("cli_library.analyze.errors_label") + "[/red]",
        errors=result.error_count,
        total=t("cli_library.analyze.total", total=total),
    )
    console.print(summary)
    return 0
