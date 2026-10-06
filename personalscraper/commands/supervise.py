"""Supervisor command — ``personalscraper supervise``.

Builds the :class:`~personalscraper.app.supervisor.supervisor.Supervisor` over the environment's
services and runs its loop until SIGTERM/SIGINT; a clean stop releases the lease. The workers it
starts are detached and outlive it.

This module is the composition root of the watcher half: :class:`WatchHelpers` implements the
supervisor's :class:`~personalscraper.app.supervisor.supervisor.WatcherHalf` port over
``personalscraper watch``'s own poll, cross-seed and state helpers, called as they are (that
command stays, unchanged, as the rollback path). The application layer never imports them.
"""

from __future__ import annotations

import os
import signal
from typing import TYPE_CHECKING

import typer

from personalscraper import cli_helpers
from personalscraper.app.composition import build_app_context, build_app_services
from personalscraper.app.supervisor.launcher import ProcessWorkerLauncher
from personalscraper.app.supervisor.supervisor import Supervisor, SupervisorWedged
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.commands import watch as watch_command
from personalscraper.conf.isolation import assert_isolated
from personalscraper.i18n import t
from personalscraper.logger import get_logger
from personalscraper.subscribers.redis_stream import build_redis_publisher

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.watcher import WatcherInput, WatcherOutput, WatcherState
    from personalscraper.api.torrent._contracts import TorrentLister
    from personalscraper.conf.models.config import Config

log = get_logger(__name__)

# Set by the SIGTERM/SIGINT handler; the loop checks it before each tick.
_stop_requested = False


def _on_signal(signum: int, _frame: object) -> None:
    """Ask the loop to stop after the current tick; the workers are never signalled.

    The watch module's own flag is raised too: a cross-seed list in flight stops at its next hash,
    exactly as it does under ``personalscraper watch``.

    Args:
        signum: The signal received.
        _frame: The interrupted frame (unused).
    """
    global _stop_requested
    _stop_requested = True
    watch_command._shutdown_requested = True
    log.info("supervisor.signal_received", signum=signum)


class WatchHelpers:
    """The supervisor's watcher half, over ``personalscraper watch``'s helpers (the K6 cross-seed seam).

    It carries, between cycles, what the watch loop carried in its locals: the deferral probe
    directories (resolved once), the last deferred snapshot and the per-hash cross-seed failures.
    """

    def __init__(self, config: Config, torrent_client: TorrentLister, store: AcquireStore | None) -> None:
        """Resolve what the watch loop resolved once at boot.

        Args:
            config: Loaded configuration.
            torrent_client: The active torrent client.
            store: The acquisition store, or ``None`` when acquisition is absent.
        """
        self._config = config
        self._client = torrent_client
        self._store = store
        self._deferral_dirs, self._deferral_ingest_dir = watch_command._resolve_deferral_dirs(config)
        self._last_deferred: dict[str, str] = {}
        self._cross_seed_failures: dict[str, int] = {}

    def restore(self, state: WatcherState) -> None:
        """Restore the last successful run from the acquire store (fail-soft).

        Args:
            state: The fresh state, mutated in place.
        """
        watch_command._restore_last_successful_run(self._store, state)

    def poll(self) -> WatcherInput | None:
        """Run the watch poll, carrying its deferral snapshot to the next cycle.

        Returns:
            The cycle's input, or ``None`` when the cycle is skipped.
        """
        inp, self._last_deferred = watch_command._poll(
            self._client,
            self._config,
            self._config.paths.data_dir,
            self._deferral_dirs,
            self._deferral_ingest_dir,
            self._last_deferred,
        )
        return inp

    def cross_seed(self, out: WatcherOutput, state: WatcherState) -> WatcherState:
        """Run the cross-seed children of a decision, sequentially, as the watch daemon does.

        Args:
            out: The ``FIRE_CROSS_SEED`` decision.
            state: The current state.

        Returns:
            The state after the cross-seeds.
        """
        return watch_command._trigger_cross_seed(out, state, self._config, self._cross_seed_failures)

    def publish_pending(self, fires_at: float | None, active_downloads: int, now: float) -> None:
        """Write the pending run for the web to read; nothing without an acquire store.

        Args:
            fires_at: When the debounced run fires, if armed.
            active_downloads: How many downloads still run.
            now: The cycle's epoch.
        """
        if self._store is not None:
            self._store.watch.set_pending_run(fires_at=fires_at, active_downloads=active_downloads, now=now)

    def record_success(self, now: float) -> None:
        """Store a successful run's epoch; nothing without an acquire store.

        Args:
            now: The epoch.
        """
        if self._store is not None:
            self._store.watch.set_last_successful_run_at(now)


@command_with_telemetry("supervise", help=t("cli_core.supervise.help"))
@handle_cli_errors
def supervise(ctx: typer.Context) -> None:
    """Start the supervisor and run it until SIGTERM/SIGINT."""
    config: Config = ctx.obj.config
    assert config is not None
    # The config was guarded when it loaded; guard again before the store is opened, so no
    # other path into this command can put the lease in another environment's data directory.
    assert_isolated(config)
    settings = cli_helpers.get_settings()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    # The torrent client serves only the watcher: a disabled watcher never contacts it.
    app_context = build_app_context(config, settings, build_torrent_client=config.watch.enabled)
    services = build_app_services(config, settings, event_bus=app_context.event_bus)
    # The supervisor's events reach the stream like the watcher's did (fail-soft: Redis down never
    # blocks the boot). The workers' runs wire their own publisher.
    redis_publisher = None
    try:
        redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
    except Exception:  # noqa: BLE001 — visibility only
        log.warning("redis_publisher_init_failed", exc_info=True)

    acquire = app_context.acquire
    watcher = None
    if config.watch.enabled:
        if app_context.torrent_client is None:
            typer.echo(t("cli_core.supervise.no_client"), err=True)
        else:
            watcher = WatchHelpers(config, app_context.torrent_client, acquire.store if acquire is not None else None)

    supervisor = Supervisor.from_services(services, config, ProcessWorkerLauncher(), watcher=watcher)
    typer.echo(t("cli_core.supervise.started", pid=os.getpid()))
    try:
        supervisor.run(lambda: _stop_requested)
    except SupervisorWedged:
        # Logged by the loop (``supervisor.ticks_failing``); a non-zero exit makes PM2 restart it.
        raise typer.Exit(1) from None
    finally:
        if redis_publisher is not None:
            redis_publisher.close()
        services.close()
        app_context.provider_registry.close()
        if acquire is not None:
            acquire.close()
        log.info("supervisor.shutdown_complete")
    typer.echo(t("cli_core.supervise.stopped"))
