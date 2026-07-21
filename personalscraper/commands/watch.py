"""Watch daemon command — ``personalscraper watch``.

Spawns ``personalscraper run --no-console --trigger-reason <reason>`` and
``personalscraper cross-seed --hash <H>`` as subprocesses (W5).  The daemon
itself holds no ``pipeline.lock`` — only its spawned children acquire it.

Runs until SIGTERM/SIGINT.  Designed to be managed by PM2 via
``ecosystem.config.js``.

The daemon is a thin orchestrating loop (:func:`watch`) over three phases,
each extracted into module-level, independently testable units:

- **poll** — :func:`_poll` (tracker read → torrent listing → deferrals →
  :class:`~personalscraper.acquire.watcher.WatcherInput` snapshot).
- **decide** — a single call into
  :meth:`~personalscraper.acquire.watcher.WatcherService.evaluate`.
- **trigger** — :func:`_trigger` (dispatch the decision: spawn run /
  cross-seed / debounce / requeue / idle) then :func:`_reap_tracked_run`
  (poll the tracked run handle and persist last-successful-run state).
"""

from __future__ import annotations

import dataclasses
import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from personalscraper import cli_helpers
from personalscraper.acquire.watcher import (
    WatcherDecision,
    WatcherInput,
    WatcherOutput,
    WatcherService,
    WatcherState,
)
from personalscraper.api.torrent._errors import TORRENT_LISTING_ERRORS
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import _build_app_context, handle_cli_errors
from personalscraper.core.tags import SEED_PURE
from personalscraper.ingest.deferral import classify_deferrals, deferral_probe_dirs
from personalscraper.ingest.tracker import IngestTracker
from personalscraper.lock import is_lock_held
from personalscraper.logger import get_logger
from personalscraper.subscribers.redis_stream import build_redis_publisher

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.api.torrent._contracts import TorrentLister
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


def _run_disabled_idle_loop(config: Config) -> None:
    """Idle-sleep loop for a daemon whose config disables the watcher.

    Under PM2 ``autorestart: true`` an instant exit crash-loops the daemon
    (start → exit → restart every ``restart_delay``).  Instead of returning
    immediately the daemon idles — stays alive, does no work (no app context,
    no torrent poll), and honours SIGTERM/SIGINT so ``pm2 stop``/``restart``
    (e.g. after re-enabling in config) shuts down gracefully.

    Args:
        config: The typed configuration; only ``watch.poll_interval_s`` is
            read to pace the idle sleep.
    """
    typer.echo("Watch daemon is disabled (config.watch.enabled=false).")
    log.info("watcher_disabled")
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    while not _shutdown_requested:
        _interruptible_sleep(config.watch.poll_interval_s)
    log.info("watcher_disabled_shutdown")


def _restore_last_successful_run(store: AcquireStore | None, state: WatcherState) -> None:
    """Restore ``last_successful_run_at`` from acquire.db into ``state`` in place.

    Fail-soft: a store read error must never block daemon boot — the field
    simply stays ``None`` and the safety-net pacing owns the first run.

    Args:
        store: The acquisition store, or ``None`` when acquire is absent.
        state: The freshly constructed watcher state, mutated in place.
    """
    if store is not None:
        try:
            state.last_successful_run_at = store.watch.get_last_successful_run_at()
        except Exception:
            log.warning("watcher_state_restore_failed", exc_info=True)


def _resolve_deferral_dirs(config: Config) -> tuple[list[Path], Path | None]:
    """Resolve the transient-skip deferral probe dirs once for the daemon lifetime.

    Fail-soft: deferral is an optimisation (fewer empty runs), never a boot
    blocker — an unresolvable staging layout simply disables it.

    Args:
        config: The typed configuration.

    Returns:
        A ``(probe_dirs, ingest_dir)`` tuple.  ``ingest_dir`` is ``None`` (and
        ``probe_dirs`` empty) when the staging layout cannot be resolved.
    """
    try:
        deferral_dirs = deferral_probe_dirs(config)
        return deferral_dirs, deferral_dirs[-1]
    except Exception:
        log.warning("watcher_deferral_dirs_unavailable", exc_info=True)
        return [], None


def _read_ingested_hashes(tracker_path: Path) -> frozenset[str] | None:
    """Validate the ingest tracker file and return the ingested hash set.

    ``IngestTracker.load()`` degrades to ``{}`` on any read/parse error.  A
    degraded load would make the watcher treat the library as fresh — mass
    cross-seed dispatch + run trigger.  This guard validates the raw JSON on
    disk BEFORE calling ``load()`` and signals a cycle skip on any anomaly.

    Args:
        tracker_path: Path to ``ingested_torrents.json``.

    Returns:
        The frozenset of ingested info-hashes, or ``None`` when the file
        exists but is unreadable / whitespace-only / invalid JSON / non-dict
        — meaning the caller must skip this cycle.
    """
    if tracker_path.exists():
        # (a) Read raw text.  OSError / UnicodeDecodeError → unreadable, skip.
        try:
            raw = tracker_path.read_text(encoding="utf-8")
        except OSError:
            log.warning("watcher_tracker_unreadable", path=str(tracker_path), cause="io_error")
            return None
        except UnicodeDecodeError:
            log.warning("watcher_tracker_unreadable", path=str(tracker_path), cause="undecodable")
            return None

        # (b) Whitespace-only file (truncated write) — st_size > 0 but no
        #     content.  load() would degrade to {} which means mass dispatch.
        if raw.strip() == "":
            try:
                st_size = tracker_path.stat().st_size
            except OSError:
                st_size = 0
            if st_size > 0:
                log.warning("watcher_tracker_unreadable", path=str(tracker_path), cause="empty")
                return None

        # (c) Invalid JSON (corrupt content).  load() would degrade to {}.
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("watcher_tracker_unreadable", path=str(tracker_path), cause="invalid_json")
            return None

        # (d) Non-dict JSON (e.g. a list).  load() would return the parsed
        #     value and .keys() below would raise AttributeError → crash loop.
        if not isinstance(parsed, dict):
            log.warning("watcher_tracker_unreadable", path=str(tracker_path), cause="not_a_dict")
            return None

    # Safe to call load() — the file is either absent (fresh library) or a
    # validated JSON dict.
    tracker = IngestTracker(tracker_path=tracker_path)
    ingested_data = tracker.load()
    return frozenset(ingested_data.keys())


def _poll_completed(torrent_client: TorrentLister) -> list[TorrentItem] | None:
    """List completed torrents, guarding against transient client errors.

    W1: log, skip the cycle, never crash the daemon.

    Args:
        torrent_client: The active torrent client.

    Returns:
        The completed torrents, or ``None`` when the client raised a
        recoverable listing error — meaning the caller must skip this cycle.
    """
    try:
        return torrent_client.get_completed()
    except TORRENT_LISTING_ERRORS:
        log.warning("watcher_poll_error", exc_info=True)
        return None


def _poll_deferrals(
    completed: list[TorrentItem],
    exclude_hashes: frozenset[str],
    config: Config,
    deferral_dirs: list[Path],
    deferral_ingest_dir: Path | None,
    last_deferred: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Classify torrents ingest would re-skip this cycle (ratio / content / space).

    Re-evaluated live every cycle — self-healing, nothing persisted, nothing
    marked done.  Fail-soft: a probe error must never kill the daemon cycle.
    Change-only logging: emit ``watcher_deferred_changed`` only when the set
    differs from the previous cycle.

    Args:
        completed: Completed torrents from the poll.
        exclude_hashes: Hashes to exclude from deferral (ingested ∪ seed-pure).
        config: The typed configuration (ratio / free-space thresholds).
        deferral_dirs: Staging probe dirs.
        deferral_ingest_dir: The ingest dir, or ``None`` when deferral is off.
        last_deferred: The previous cycle's deferred snapshot.

    Returns:
        A ``(deferred, last_deferred)`` tuple: the current deferred mapping
        (hash → reason) and the snapshot to carry into the next cycle.
    """
    deferred: dict[str, str] = {}
    if deferral_ingest_dir is not None:
        try:
            deferred = classify_deferrals(
                completed,
                min_ratio=config.ingest.min_ratio,
                ingest_dir=deferral_ingest_dir,
                min_free_gb=config.thresholds.min_free_space_staging_gb,
                staging_probe_dirs=deferral_dirs,
                exclude_hashes=exclude_hashes,
            )
        except Exception:
            log.warning("watcher_deferral_probe_failed", exc_info=True)
            deferred = {}
    if deferred != last_deferred:
        log.info(
            "watcher_deferred_changed",
            count=len(deferred),
            reasons={h[:12]: r for h, r in sorted(deferred.items())},
        )
        last_deferred = deferred
    return deferred, last_deferred


def _poll(
    torrent_client: TorrentLister,
    config: Config,
    data_dir: Path,
    deferral_dirs: list[Path],
    deferral_ingest_dir: Path | None,
    last_deferred: dict[str, str],
) -> tuple[WatcherInput | None, dict[str, str]]:
    """Gather one cycle's decision input from disk + torrent client.

    Chains the poll-phase units: tracker read (:func:`_read_ingested_hashes`),
    torrent listing (:func:`_poll_completed`), hash-set derivation, deferral
    classification (:func:`_poll_deferrals`), and finally the immutable
    :class:`~personalscraper.acquire.watcher.WatcherInput` snapshot.

    Args:
        torrent_client: The active torrent client.
        config: The typed configuration.
        data_dir: The daemon data dir (holds the tracker, sentinel, lock).
        deferral_dirs: Staging probe dirs.
        deferral_ingest_dir: The ingest dir, or ``None`` when deferral is off.
        last_deferred: The previous cycle's deferred snapshot.

    Returns:
        A ``(inp, last_deferred)`` tuple.  ``inp`` is ``None`` when the tracker
        is unreadable or the torrent listing failed — the caller must skip the
        cycle.  ``last_deferred`` is the snapshot to carry into the next cycle.
    """
    # 1. Fresh ingested set — re-read every cycle (spawned runs mutate
    #    ingested_torrents.json).  A None result means skip the cycle.
    ingested_hashes = _read_ingested_hashes(data_dir / "ingested_torrents.json")
    if ingested_hashes is None:
        return None, last_deferred

    # 2. Completed torrents with error guard (W1).
    completed = _poll_completed(torrent_client)
    if completed is None:
        return None, last_deferred

    # 3. Hash sets for the decision engine.
    completed_hashes = frozenset(t.hash for t in completed)
    seed_pure_hashes = frozenset(t.hash for t in completed if SEED_PURE in (t.tags or []))

    # 3b. Transient-skip deferrals (live, self-healing, nothing persisted).
    deferred, last_deferred = _poll_deferrals(
        completed,
        ingested_hashes | seed_pure_hashes,
        config,
        deferral_dirs,
        deferral_ingest_dir,
        last_deferred,
    )

    # 4. Build input snapshot.
    now = time.time()
    inp = WatcherInput(
        completed_hashes=completed_hashes,
        ingested_hashes=ingested_hashes,
        seed_pure_hashes=seed_pure_hashes,
        sentinel_present=(data_dir / "watch.trigger").exists(),
        pipeline_lock_held=is_lock_held(data_dir / "pipeline.lock"),
        now=now,
        deferred_hashes=frozenset(deferred),
    )
    return inp, last_deferred


def _trigger_run(
    out: WatcherOutput,
    tracked_run: subprocess.Popen[bytes] | None,
    data_dir: Path,
) -> subprocess.Popen[bytes] | None:
    """Spawn ``personalscraper run --no-console`` (async, tracked) for FIRE_RUN.

    If a tracked run is still active the spawn is skipped (single-flight).  The
    manual-trigger sentinel is consumed ONLY for an operator poke (reason
    ``manual``) so an automated reason never eats a pending manual request.

    Args:
        out: The FIRE_RUN decision (carries ``run_reason``).
        tracked_run: The currently tracked child, or ``None``.
        data_dir: The daemon data dir (holds the ``watch.trigger`` sentinel).

    Returns:
        The tracked child to carry forward — the existing one when a run is
        still active, otherwise the freshly spawned child.
    """
    if tracked_run is not None and tracked_run.poll() is None:
        log.info("watcher_run_still_active", pid=tracked_run.pid)
        return tracked_run

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
    log.info("watcher_spawning_run", reason=out.run_reason, pid=tracked_run.pid)
    # Consume sentinel ONLY for manual trigger (operator poke via
    # ``personalscraper watch-now``).
    if out.run_reason == "manual":
        (data_dir / "watch.trigger").unlink(missing_ok=True)
    return tracked_run


def _trigger_cross_seed(
    out: WatcherOutput,
    state: WatcherState,
    config: Config,
    cross_seed_failures: dict[str, int],
) -> WatcherState:
    """Spawn ``personalscraper cross-seed --hash <H>`` sequentially for each hash.

    Children run synchronously (``subprocess.run``) one at a time.  A shutdown
    signal mid-list removes the unspawned tail from ``cross_seed_dispatched``
    so the next daemon boot retries them.  A failed / timed-out child is
    removed from ``cross_seed_dispatched`` to retry next cycle, until the
    per-hash counter reaches 3 consecutive failures — then the hash is left in
    the dispatched set (no more retries this daemon lifetime).

    Args:
        out: The FIRE_CROSS_SEED decision (carries ``cross_seed_hashes``).
        state: The current watcher state.
        config: The typed configuration (``cross_seed.verify_timeout_s``).
        cross_seed_failures: Per-hash failure counter, mutated in place.

    Returns:
        The updated watcher state.
    """
    # Child timeout must leave room for up to two sequential verify polls per
    # cross-seed check (each up to verify_timeout_s) plus a 300 s margin for
    # I/O and subprocess startup/shutdown.
    child_timeout = max(1800, 2 * config.cross_seed.verify_timeout_s + 300)
    for idx, h in enumerate(out.cross_seed_hashes):
        if _shutdown_requested:
            # Unspawned hashes: remove from dispatched so the next daemon boot
            # retries them.
            remaining = frozenset(out.cross_seed_hashes[idx:])
            state = dataclasses.replace(
                state,
                cross_seed_dispatched=state.cross_seed_dispatched - remaining,
            )
            log.info("watcher_cross_seed_shutdown_interrupt", unspawned=len(remaining))
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
                stderr_tail = result.stderr.decode("utf-8", errors="replace")[-500:] if result.stderr else ""
                log.warning(
                    "watcher_cross_seed_failed",
                    info_hash=h,
                    returncode=result.returncode,
                    stderr_tail=stderr_tail,
                )

        if failed:
            failures = cross_seed_failures.get(h, 0) + 1
            cross_seed_failures[h] = failures
            if failures >= 3:
                log.warning("watcher_cross_seed_gave_up", info_hash=h, attempts=3)
                # Leave in dispatched — no more retries this daemon lifetime.
            else:
                # Remove from dispatched so it retries next cycle (acquire.db
                # exclude-recent guard prevents hammering).
                state = dataclasses.replace(
                    state,
                    cross_seed_dispatched=state.cross_seed_dispatched - {h},
                )
    return state


def _trigger(
    out: WatcherOutput,
    state: WatcherState,
    tracked_run: subprocess.Popen[bytes] | None,
    config: Config,
    data_dir: Path,
    cross_seed_failures: dict[str, int],
) -> tuple[WatcherState, subprocess.Popen[bytes] | None]:
    """Execute the decision engine's verdict for this cycle.

    Dispatches on ``out.decision``: spawn a run (:func:`_trigger_run`), spawn
    cross-seeds (:func:`_trigger_cross_seed`), or log the passive outcomes
    (START_DEBOUNCE / REQUEUE / IDLE).

    Args:
        out: The evaluated decision.
        state: The current watcher state.
        tracked_run: The currently tracked run child, or ``None``.
        config: The typed configuration.
        data_dir: The daemon data dir.
        cross_seed_failures: Per-hash failure counter, mutated in place.

    Returns:
        A ``(state, tracked_run)`` tuple carrying the updated state and run
        handle forward.
    """
    if out.decision == WatcherDecision.FIRE_RUN:
        tracked_run = _trigger_run(out, tracked_run, data_dir)
    elif out.decision == WatcherDecision.FIRE_CROSS_SEED:
        state = _trigger_cross_seed(out, state, config, cross_seed_failures)
    elif out.decision == WatcherDecision.START_DEBOUNCE:
        log.debug("watcher_debounce_started", until=state.debounce_until)
    elif out.decision == WatcherDecision.REQUEUE:
        log.debug("watcher_requeue", reason="pipeline_lock_held")
    elif out.decision == WatcherDecision.IDLE:
        log.debug("watcher_idle")
    return state, tracked_run


def _reap_tracked_run(
    tracked_run: subprocess.Popen[bytes] | None,
    state: WatcherState,
    store: AcquireStore | None,
    now: float,
) -> tuple[WatcherState, subprocess.Popen[bytes] | None]:
    """Poll the tracked run handle and persist last-successful-run state.

    On a clean exit (returncode 0) the successful-run timestamp is persisted
    (fail-soft) and mirrored into ``state``.  The machine owns debounce/backoff
    resets — the loop must NOT clear them (W7 anti-storm).  A still-running or
    absent child is a no-op.

    Args:
        tracked_run: The tracked run child, or ``None``.
        state: The current watcher state.
        store: The acquisition store for persistence, or ``None``.
        now: This cycle's ``time.time()`` snapshot (the run's success epoch).

    Returns:
        A ``(state, tracked_run)`` tuple: ``tracked_run`` is cleared to
        ``None`` once the child has exited, otherwise carried forward.
    """
    if tracked_run is None:
        return state, tracked_run
    returncode = tracked_run.poll()
    if returncode is None:
        return state, tracked_run
    if returncode == 0:
        # Persist the successful run timestamp (fail-soft).
        if store is not None:
            try:
                store.watch.set_last_successful_run_at(now)
            except Exception:
                log.warning("watcher_state_persist_failed", exc_info=True)
        state = dataclasses.replace(state, last_successful_run_at=now)
        log.info("watcher_run_succeeded")
    else:
        log.warning("watcher_run_failed", returncode=returncode)
    return state, None


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
        # Do NOT return immediately: under PM2 `autorestart: true` an instant
        # exit crash-loops the daemon.  Idle instead (see helper).
        _run_disabled_idle_loop(config)
        return

    settings = cli_helpers.get_settings()
    data_dir = config.paths.data_dir

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    # Build the AppContext once for daemon lifetime — torrent client, provider
    # registry, and acquire store are shared across every poll cycle.
    app_context = _build_app_context(config, settings, build_torrent_client=True)

    # Redis event publisher for the watcher's own bus events (fail-soft —
    # Redis down must never block the daemon boot).  Pipeline runs spawned
    # as subprocesses wire their own publisher via pipeline.py.
    redis_publisher = None
    try:
        redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
    except Exception:
        log.warning("redis_publisher_init_failed", exc_info=True)

    torrent_client = app_context.torrent_client
    if torrent_client is None:
        typer.echo("No active torrent client configured (config.torrent.active is empty).", err=True)
        raise typer.Exit(code=1)

    svc = WatcherService(config.watch)
    state = WatcherState()

    # Restore last_successful_run_at from acquire.db (fail-soft).
    acquire = app_context.acquire
    store = acquire.store if acquire is not None else None
    _restore_last_successful_run(store, state)

    tracked_run: subprocess.Popen[bytes] | None = None
    # Per-hash failure counter — in-memory (resets on daemon restart).  After 3
    # consecutive failures/timeouts for the same hash, it is left in
    # cross_seed_dispatched (no more retries this daemon lifetime).
    cross_seed_failures: dict[str, int] = {}

    # Transient-skip deferral inputs (computed once — config is immutable for
    # the daemon lifetime) + last snapshot for change-only logging.
    deferral_dirs, deferral_ingest_dir = _resolve_deferral_dirs(config)
    last_deferred: dict[str, str] = {}

    try:
        while not _shutdown_requested:
            # Web pause lever: POST /api/pipeline/watcher {enabled:false} writes
            # the watcher.paused sentinel.  While it exists, skip polling,
            # evaluation, and any FIRE_RUN/FIRE_CROSS_SEED dispatch.  This does
            # NOT touch an already-running tracked child (pausing only prevents
            # the daemon from auto-starting NEW runs; pipe-control DESIGN §pause).
            if (data_dir / "watcher.paused").exists():
                log.debug("watcher_paused_skipping_cycle")
                _interruptible_sleep(config.watch.poll_interval_s)
                continue

            # POLL — gather this cycle's decision input (None → skip cycle).
            inp, last_deferred = _poll(
                torrent_client,
                config,
                data_dir,
                deferral_dirs,
                deferral_ingest_dir,
                last_deferred,
            )
            if inp is None:
                _interruptible_sleep(config.watch.poll_interval_s)
                continue

            # DECIDE — consult the (pure) decision engine.
            out = svc.evaluate(inp, state)
            state = out.new_state

            # TRIGGER — execute the decision, then reap the tracked run handle.
            state, tracked_run = _trigger(out, state, tracked_run, config, data_dir, cross_seed_failures)
            state, tracked_run = _reap_tracked_run(tracked_run, state, store, inp.now)

            # Sleep for the configured poll interval (interruptible).
            _interruptible_sleep(config.watch.poll_interval_s)

    finally:
        if tracked_run is not None:
            log.info("watcher_leaving_tracked_run", pid=tracked_run.pid)
        if redis_publisher is not None:
            redis_publisher.close()
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
