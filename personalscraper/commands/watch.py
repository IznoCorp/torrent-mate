"""Watch daemon command — ``personalscraper watch``.

Spawns ``personalscraper run --no-console --trigger-reason <reason>`` and
``personalscraper cross-seed --hash <H>`` as subprocesses (W5).  The daemon
itself holds no ``pipeline.lock`` — only its spawned children acquire it.

Runs until SIGTERM/SIGINT.  Designed to be managed by PM2 via
``ecosystem.config.js``.
"""

from __future__ import annotations

import dataclasses
import json
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import typer

from personalscraper import cli as cli_compat
from personalscraper.acquire.watcher import (
    WatcherDecision,
    WatcherInput,
    WatcherService,
    WatcherState,
)
from personalscraper.api.torrent._errors import TORRENT_LISTING_ERRORS
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import _build_app_context, handle_cli_errors
from personalscraper.core.tags import SEED_PURE
from personalscraper.ingest.tracker import IngestTracker
from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger(__name__)

# Set by SIGTERM/SIGINT handler — the loop checks this at the top of each cycle.
_shutdown_requested = False


def _on_signal(signum: int, _frame: object) -> None:
    """Set the shutdown flag so the current cycle finishes cleanly.

    Spawned subprocess children are NEVER killed — they outlive the daemon.
    """
    global _shutdown_requested
    _shutdown_requested = True
    log.info("watcher_signal_received", signum=signum)


def _interruptible_sleep(seconds: float) -> None:
    """Sleep in 1 s slices, polling :data:`_shutdown_requested` between slices.

    Python 3.5+ (PEP 475) automatically retries C-level ``sleep()`` when a
    signal handler runs, so a ``time.sleep(60)`` after SIGTERM continues
    sleeping the full duration without the loop ever seeing the flag.  Slicing
    into 1 s chunks guarantees a signal received during the sleep phase
    reaches the ``while`` condition within at most 1 s, allowing the daemon's
    ``finally`` block (context close, shutdown log) to execute before PM2
    escalates to SIGKILL.

    Args:
        seconds: Total sleep duration in seconds.  Stops early when
            :data:`_shutdown_requested` becomes ``True``.

    Note:
        While the sleep itself is interruptible, a running subprocess child
        (cross-seed ``subprocess.run``) blocks SIGTERM for up to the child
        timeout (``max(1800, 2×verify_timeout_s + 300)``).  This is
        design-inherent — W5 serial spawns cannot interrupt a mid-flight
        child.
    """
    remaining = seconds
    while remaining > 0 and not _shutdown_requested:
        chunk = min(remaining, 1.0)
        time.sleep(chunk)
        remaining -= chunk


@command_with_telemetry("watch")
@handle_cli_errors
def watch(ctx: typer.Context) -> None:
    """Start the watcher daemon (single-process scheduler).

    Polls the configured torrent client each cycle, consults the
    :class:`~personalscraper.acquire.watcher.WatcherService` decision engine,
    and spawns ``personalscraper run --no-console`` (async, tracked) or
    ``personalscraper cross-seed --hash <H>`` (sync, sequential) as
    subprocesses.  The daemon itself does NOT acquire ``pipeline.lock``
    (W6) — only its spawned children do.

    Runs until SIGTERM, SIGINT, or a fatal error.
    """
    config: Config = ctx.obj.config
    assert config is not None

    if not config.watch.enabled:
        typer.echo("Watch daemon is disabled (config.watch.enabled=false).")
        log.info("watcher_disabled")
        return

    settings = cli_compat.get_settings()
    data_dir = config.paths.data_dir

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    # Build the AppContext once for daemon lifetime — torrent client, provider
    # registry, and acquire store are shared across every poll cycle.
    app_context = _build_app_context(config, settings, build_torrent_client=True)

    if app_context.torrent_client is None:
        typer.echo("No active torrent client configured (config.torrent.active is empty).", err=True)
        raise typer.Exit(code=1)

    svc = WatcherService(config.watch)
    state = WatcherState()

    # Restore last_successful_run_at from acquire.db (fail-soft).
    acquire = app_context.acquire
    store = acquire.store if acquire is not None else None
    if store is not None:
        try:
            state.last_successful_run_at = store.watch.get_last_successful_run_at()
        except Exception:
            log.warning("watcher_state_restore_failed", exc_info=True)

    tracked_run: subprocess.Popen[bytes] | None = None
    # Per-hash failure counter — in-memory (resets on daemon restart).
    # After 3 consecutive failures or timeouts for the same hash, the
    # hash is left in cross_seed_dispatched (no more retries this
    # daemon lifetime).
    _cross_seed_failures: dict[str, int] = {}

    try:
        while not _shutdown_requested:
            # 1. Fresh ingested set — re-read every cycle (spawned runs mutate
            #    ingested_torrents.json).
            tracker_path = data_dir / "ingested_torrents.json"

            # Cycle guard: validate the tracker file BEFORE calling
            # IngestTracker.load(), which degrades to {} on errors.  A
            # degraded load would cause the watcher to treat the library as
            # fresh — mass cross-seed dispatch + run trigger.
            if tracker_path.exists():
                # (a) Read raw text.  OSError → unreadable, skip the cycle.
                try:
                    raw = tracker_path.read_text(encoding="utf-8")
                except OSError:
                    log.warning(
                        "watcher_tracker_unreadable",
                        path=str(tracker_path),
                        cause="io_error",
                    )
                    _interruptible_sleep(config.watch.poll_interval_s)
                    continue

                # (b) Whitespace-only file (truncated write) — st_size > 0
                #     but no content.  load() would degrade to {} which means
                #     mass dispatch.
                if raw.strip() == "":
                    try:
                        st_size = tracker_path.stat().st_size
                    except OSError:
                        st_size = 0
                    if st_size > 0:
                        log.warning(
                            "watcher_tracker_unreadable",
                            path=str(tracker_path),
                            cause="empty",
                        )
                        _interruptible_sleep(config.watch.poll_interval_s)
                        continue

                # (c) Invalid JSON (corrupt content).  load() would degrade
                #     to {} → mass dispatch.
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning(
                        "watcher_tracker_unreadable",
                        path=str(tracker_path),
                        cause="invalid_json",
                    )
                    _interruptible_sleep(config.watch.poll_interval_s)
                    continue

                # (d) Non-dict JSON (e.g. a list).  load() would return the
                #     parsed value and .keys() below would raise
                #     AttributeError → daemon crash loop.
                if not isinstance(parsed, dict):
                    log.warning(
                        "watcher_tracker_unreadable",
                        path=str(tracker_path),
                        cause="not_a_dict",
                    )
                    _interruptible_sleep(config.watch.poll_interval_s)
                    continue

            # Safe to call load() — the file is either absent (fresh library)
            # or a validated JSON dict.
            tracker = IngestTracker(tracker_path=tracker_path)
            ingested_data = tracker.load()
            ingested_hashes = frozenset(ingested_data.keys())

            # 2. Completed torrents with error guard (W1: log, skip cycle,
            #    never crash).
            try:
                completed = app_context.torrent_client.get_completed()
            except TORRENT_LISTING_ERRORS:
                log.warning("watcher_poll_error", exc_info=True)
                _interruptible_sleep(config.watch.poll_interval_s)
                continue

            # 3. Hash sets for the decision engine.
            completed_hashes = frozenset(t.hash for t in completed)
            seed_pure_hashes = frozenset(t.hash for t in completed if SEED_PURE in (t.tags or []))

            # 4. Build input snapshot.
            now = time.time()
            inp = WatcherInput(
                completed_hashes=completed_hashes,
                ingested_hashes=ingested_hashes,
                seed_pure_hashes=seed_pure_hashes,
                sentinel_present=(data_dir / "watch.trigger").exists(),
                pipeline_lock_held=is_lock_held(data_dir / "pipeline.lock"),
                now=now,
            )

            # 5. Evaluate.
            out = svc.evaluate(inp, state)
            state = out.new_state

            # 6. Execute decision.
            if out.decision == WatcherDecision.FIRE_RUN:
                if tracked_run is not None and tracked_run.poll() is None:
                    log.info("watcher_run_still_active", pid=tracked_run.pid)
                else:
                    tracked_run = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "personalscraper",
                            "run",
                            "--no-console",
                            "--trigger-reason",
                            out.run_reason,
                        ],
                    )
                    log.info(
                        "watcher_spawning_run",
                        reason=out.run_reason,
                        pid=tracked_run.pid,
                    )
                    # Consume sentinel ONLY for manual trigger (operator poke via
                    # ``personalscraper watch-now``).
                    if out.run_reason == "manual":
                        (data_dir / "watch.trigger").unlink(missing_ok=True)

            elif out.decision == WatcherDecision.FIRE_CROSS_SEED:
                # Child timeout must leave room for up to two sequential
                # verify polls per cross-seed check (each up to
                # verify_timeout_s) plus a 300 s margin for I/O and
                # subprocess startup/shutdown.
                child_timeout = max(1800, 2 * config.cross_seed.verify_timeout_s + 300)
                for idx, h in enumerate(out.cross_seed_hashes):
                    if _shutdown_requested:
                        # Unspawned hashes: remove from dispatched so the
                        # next daemon boot retries them.
                        remaining = frozenset(out.cross_seed_hashes[idx:])
                        state = dataclasses.replace(
                            state,
                            cross_seed_dispatched=state.cross_seed_dispatched - remaining,
                        )
                        log.info(
                            "watcher_cross_seed_shutdown_interrupt",
                            unspawned=len(remaining),
                        )
                        break
                    try:
                        result = subprocess.run(
                            [
                                sys.executable,
                                "-m",
                                "personalscraper",
                                "cross-seed",
                                "--hash",
                                h,
                            ],
                            capture_output=True,
                            timeout=child_timeout,
                        )
                    except subprocess.TimeoutExpired as exc:
                        stderr_tail = ""
                        if exc.stderr:
                            stderr_tail = exc.stderr.decode("utf-8", errors="replace")[-500:]
                        log.warning(
                            "watcher_cross_seed_timeout",
                            info_hash=h,
                            stderr_tail=stderr_tail,
                            note=("stranded injection possible — SIGKILL may have landed mid-verify"),
                        )
                        failed = True
                    else:
                        failed = result.returncode != 0
                        if failed:
                            stderr_tail = (
                                result.stderr.decode("utf-8", errors="replace")[-500:] if result.stderr else ""
                            )
                            log.warning(
                                "watcher_cross_seed_failed",
                                info_hash=h,
                                returncode=result.returncode,
                                stderr_tail=stderr_tail,
                            )

                    if failed:
                        failures = _cross_seed_failures.get(h, 0) + 1
                        _cross_seed_failures[h] = failures
                        if failures >= 3:
                            log.warning(
                                "watcher_cross_seed_gave_up",
                                info_hash=h,
                                attempts=3,
                            )
                            # Leave in dispatched — no more retries this
                            # daemon lifetime.
                        else:
                            # Remove from dispatched so it retries next
                            # cycle (acquire.db exclude-recent guard
                            # prevents hammering).
                            state = dataclasses.replace(
                                state,
                                cross_seed_dispatched=state.cross_seed_dispatched - {h},
                            )

            elif out.decision == WatcherDecision.START_DEBOUNCE:
                log.debug("watcher_debounce_started", until=state.debounce_until)

            elif out.decision == WatcherDecision.REQUEUE:
                log.debug("watcher_requeue", reason="pipeline_lock_held")

            elif out.decision == WatcherDecision.IDLE:
                log.debug("watcher_idle")

            # 7. Poll tracked run handle.
            if tracked_run is not None:
                returncode = tracked_run.poll()
                if returncode is not None:
                    if returncode == 0:
                        # Persist the successful run timestamp (fail-soft).
                        # The machine owns debounce/backoff resets — the loop
                        # must NOT clear them (W7 anti-storm).  Branch 4
                        # clears completion windows when work vanishes and
                        # keeps safety-net pacing when it does not.
                        if store is not None:
                            try:
                                store.watch.set_last_successful_run_at(now)
                            except Exception:
                                log.warning("watcher_state_persist_failed", exc_info=True)
                        state = dataclasses.replace(
                            state,
                            last_successful_run_at=now,
                        )
                        log.info("watcher_run_succeeded")
                    else:
                        log.warning("watcher_run_failed", returncode=returncode)
                    tracked_run = None

            # 8. Sleep for the configured poll interval (interruptible).
            _interruptible_sleep(config.watch.poll_interval_s)

    finally:
        if tracked_run is not None:
            log.info("watcher_leaving_tracked_run", pid=tracked_run.pid)
        app_context.provider_registry.close()
        if acquire is not None:
            acquire.close()
        log.info("watcher_shutdown_complete")


@command_with_telemetry("watch-now")
@handle_cli_errors
def watch_now(ctx: typer.Context) -> None:
    """Write the sentinel file that the watcher daemon consumes next cycle.

    No IPC, no daemon dependency — if the daemon is down, the sentinel is
    consumed at next boot.  Same channel as the future Web UI (W4).

    The running ``personalscraper watch`` daemon detects this file at the
    next poll cycle and fires a pipeline run with ``reason=manual``.
    """
    config: Config = ctx.obj.config
    assert config is not None

    sentinel = config.paths.data_dir / "watch.trigger"
    sentinel.write_text("")
    log.info("watch_now_sentinel_written", path=str(sentinel))
    typer.echo(f"Sentinel written: {sentinel}")
    typer.echo(
        "Consumed by the watch daemon next cycle "
        "-> pipeline run with reason=manual; "
        "if the daemon is down the sentinel persists until next boot."
    )
