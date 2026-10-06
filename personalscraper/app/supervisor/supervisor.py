"""The ``Supervisor``: the one process per environment that starts asked runs, under its lease.

One loop, two cadences (:meth:`Supervisor.run`):

- **Admission**, every :data:`ADMISSION_INTERVAL_S` (:meth:`Supervisor.tick_admission`): hold the
  lease (claim it, or renew it); settle the requests whose worker ended (its exit code, for a worker
  this process started) or went silent (a stale heartbeat: the outcome of its ``pipeline_run`` row,
  else ``interrupted``); announce the requests seen for the first time; then, when nothing runs,
  start the head of the queue — unless ``pipeline.pause`` is present or ``pipeline.lock`` (or a
  scrape-resolve lock) is held, the head then recording why it waits.
- **The watcher**, every ``watch.poll_interval_s`` (:meth:`Supervisor.tick_watcher`): today's poll and
  decision engine, unchanged, behind the :class:`WatcherHalf` port; a ``FIRE_RUN`` becomes an ask of
  the run service instead of a spawned ``run``, and the input's « pipeline lock held » becomes « a
  request is queued or running », so a requeue keeps its meaning.

Only the lease's holder admits or watches: a second supervisor idles until the lease lapses, or
until its holder is gone from this machine. Workers are detached and outlive the supervisor; a
restarted one adopts the running requests and judges them by their heartbeat.
"""

from __future__ import annotations

import dataclasses
import os
import socket
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

from personalscraper.acquire.watcher import WatcherDecision, WatcherInput, WatcherOutput, WatcherService, WatcherState
from personalscraper.app.errors import AppForbidden
from personalscraper.app.supervisor.events import RunAdmitted, RunQueued, RunSettled
from personalscraper.app.supervisor.launcher import LOST_LOCK_EXIT, WorkerLauncher
from personalscraper.app.supervisor.model import (
    LEASE_TTL_S,
    RunKind,
    RunOptions,
    RunRequest,
    RunTrigger,
    Settlement,
    WaitReason,
)
from personalscraper.lock import any_scrape_resolve_active, is_lock_held, scrape_locks_dir_for
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.services import AppServices
    from personalscraper.app.store.store import AppStore
    from personalscraper.app.supervisor.service import RunService
    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus

log = get_logger("app.supervisor.supervisor")

#: Seconds between two admission ticks.
ADMISSION_INTERVAL_S: Final = 2.0

#: The process id recorded on a request whose worker never started: it names no process.
_NO_WORKER: Final = 0

#: A ``pipeline_run`` outcome that tells how a silent worker's run ended.
_ROW_SETTLEMENTS: Final[dict[str, Settlement]] = {
    "success": Settlement.SUCCESS,
    "error": Settlement.ERROR,
    "killed": Settlement.KILLED,
}


class WatcherHalf(Protocol):
    """What the supervisor asks of today's watcher: its poll, its cross-seed and its persisted state.

    Implemented by the CLI over ``personalscraper watch``'s own helpers, untouched (they stay the
    rollback path), so the supervisor never imports the command layer. ``cross_seed`` is the seam
    where the cross-seed leaves the watcher for its own queue.
    """

    def restore(self, state: WatcherState) -> None:
        """Write the stored last successful run into a fresh state.

        Args:
            state: The state, mutated in place.
        """
        ...

    def poll(self) -> WatcherInput | None:
        """Gather one cycle's input from the disk and the torrent client.

        Returns:
            The input, or ``None`` when the cycle must be skipped (unreadable tracker, client error).
        """
        ...

    def cross_seed(self, out: WatcherOutput, state: WatcherState) -> WatcherState:
        """Run the cross-seed of each hash of a ``FIRE_CROSS_SEED`` decision.

        Args:
            out: The decision.
            state: The current state.

        Returns:
            The state after the cross-seeds.
        """
        ...

    def publish_pending(self, fires_at: float | None, active_downloads: int, now: float) -> None:
        """Write down what the watcher waits for, for the web to read.

        Args:
            fires_at: When a debounced run fires, if one is armed.
            active_downloads: How many downloads still run.
            now: The cycle's epoch.
        """
        ...

    def record_success(self, now: float) -> None:
        """Store the epoch of a successful run (the safety net paces on it).

        Args:
            now: The epoch.
        """
        ...


class DecisionEngine(Protocol):
    """The watcher's decision engine (:class:`WatcherService`)."""

    def evaluate(self, inp: WatcherInput, state: WatcherState) -> WatcherOutput:
        """Decide one cycle.

        Args:
            inp: The cycle's input.
            state: The state carried forward.

        Returns:
            The decision and the new state.
        """
        ...


def pid_alive(pid: int) -> bool:
    """Whether a process id names a live process of this machine.

    Args:
        pid: The process id.

    Returns:
        ``False`` only when no process has that id; a process of another user (``PermissionError``)
        is alive.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _settlement_of(code: int) -> Settlement:
    """How a worker's exit code settles its request (``LOST_LOCK_EXIT`` excepted: it is re-queued).

    Args:
        code: The exit code; negative when a signal killed the worker.

    Returns:
        ``success`` for 0, ``killed`` for a signal, ``error`` otherwise (1, and 2: the trailers abort).
    """
    if code == 0:
        return Settlement.SUCCESS
    if code < 0:
        return Settlement.KILLED
    return Settlement.ERROR


class Supervisor:
    """Holds the lease, admits the queue one request at a time, settles its workers, and watches."""

    def __init__(
        self,
        *,
        store: AppStore,
        runs: RunService,
        system_actor: Callable[[], Actor],
        event_bus: EventBus,
        config: Config,
        launcher: WorkerLauncher,
        watcher: WatcherHalf | None = None,
        watcher_service: DecisionEngine | None = None,
        clock: Callable[[], float] = time.time,
        pid: int | None = None,
        host: str | None = None,
        pid_alive: Callable[[int], bool] = pid_alive,
    ) -> None:
        """Build the supervisor; nothing is claimed until the first tick.

        Args:
            store: The environment's ``app.db``.
            runs: The run service the watcher asks through.
            system_actor: The actor the watcher's asks are made as.
            event_bus: Where the supervisor's events are published.
            config: Loaded configuration (data directory, library store, watch settings).
            launcher: Starts the workers.
            watcher: The watcher half; ``None`` when there is no torrent client (admission alone).
            watcher_service: The decision engine; :class:`WatcherService` over ``config.watch`` when ``None``.
            clock: The epoch clock.
            pid: This process's id, the lease's holder; ``os.getpid()`` when ``None``.
            host: This machine; ``socket.gethostname()`` when ``None``.
            pid_alive: Whether a process id names a live process of this machine.
        """
        self._store = store
        self._runs = runs
        self._system_actor = system_actor
        self._bus = event_bus
        self._config = config
        self._launcher = launcher
        self._watcher = watcher
        self._engine: DecisionEngine = watcher_service if watcher_service is not None else WatcherService(config.watch)
        self._clock = clock
        self._pid = pid if pid is not None else os.getpid()
        self._host = host if host is not None else socket.gethostname()
        self._pid_alive = pid_alive
        self._holding = False
        self._held_logged = False
        self._seen: set[str] = set()
        self.watcher_state = WatcherState()
        if watcher is not None:
            watcher.restore(self.watcher_state)

    @classmethod
    def from_services(
        cls, services: AppServices, config: Config, launcher: WorkerLauncher, *, watcher: WatcherHalf | None
    ) -> Supervisor:
        """Build the supervisor over a process's application services.

        Args:
            services: The process's services (its ``app.db``, run service, credentials and bus).
            config: Loaded configuration.
            launcher: Starts the workers.
            watcher: The watcher half, or ``None``.

        Returns:
            The supervisor.
        """
        return cls(
            store=services.app_store,
            runs=services.runs,
            system_actor=services.credentials.system_actor,
            event_bus=services.event_bus,
            config=config,
            launcher=launcher,
            watcher=watcher,
        )

    @property
    def holds_lease(self) -> bool:
        """Whether this supervisor held the lease at its last tick."""
        return self._holding

    def run(self, should_stop: Callable[[], bool], sleep: Callable[[float], None] = time.sleep) -> None:
        """Tick until *should_stop* answers ``True``, then release the lease.

        A tick that raises is logged and the loop goes on: a transient store error must not stop the
        process that every run waits on.

        Args:
            should_stop: Asked before each tick.
            sleep: Waits between two ticks.
        """
        next_watch = 0.0
        try:
            while not should_stop():
                self._guarded(self.tick_admission)
                if self._clock() >= next_watch:
                    self._guarded(self.tick_watcher)
                    next_watch = self._clock() + self._config.watch.poll_interval_s
                sleep(ADMISSION_INTERVAL_S)
        finally:
            self.stop()

    def stop(self) -> None:
        """Release the lease at once (a clean stop), so a successor need not wait out its TTL."""
        if not self._holding:
            return
        self._holding = False
        if self._store.lease.release(self._pid, self._host):
            log.info("supervisor.lease_released", pid=self._pid, host=self._host)

    def tick_admission(self) -> None:
        """Hold the lease, settle the ended, announce the new, and start the head when it may."""
        now = self._clock()
        if not self._hold_lease(now):
            return
        self._settle_ended(now)
        self._announce()
        self._admit(now)

    def tick_watcher(self) -> None:
        """Run one watcher cycle: poll, decide, publish, and act on the decision."""
        if not self._holding or self._watcher is None or not self._config.watch.enabled:
            return
        if (self._config.paths.data_dir / "watcher.paused").exists():
            log.debug("supervisor.watcher_paused")
            return
        polled = self._watcher.poll()
        if polled is None:
            return
        view = self._runs.queue_view()
        busy = view.running is not None or bool(view.queued)
        inp = dataclasses.replace(polled, pipeline_lock_held=busy)
        out = self._engine.evaluate(inp, self.watcher_state)
        self.watcher_state = out.new_state
        try:
            self._watcher.publish_pending(
                fires_at=self.watcher_state.debounce_until, active_downloads=inp.downloading_count, now=inp.now
            )
        except Exception:  # noqa: BLE001 — advisory: visibility never breaks the watch
            log.warning("supervisor.pending_run_publish_failed", exc_info=True)
        if out.decision is WatcherDecision.FIRE_RUN:
            self._ask(out.run_reason)
        elif out.decision is WatcherDecision.FIRE_CROSS_SEED:
            self.watcher_state = self._watcher.cross_seed(out, self.watcher_state)
        elif out.decision is WatcherDecision.REQUEUE:
            log.debug("supervisor.watcher_requeue", reason="run_queued")

    def _guarded(self, tick: Callable[[], None]) -> None:
        """Run one tick; log what it raises instead of stopping the loop.

        Args:
            tick: The tick.
        """
        try:
            tick()
        except Exception:  # noqa: BLE001 — the loop outlives a failed tick; the next one retries
            log.exception("supervisor.tick_failed", tick=getattr(tick, "__name__", "tick"))

    def _hold_lease(self, now: float) -> bool:
        """Renew the lease this supervisor holds, or claim it; log the transitions.

        Args:
            now: The tick's epoch.

        Returns:
            ``True`` when this supervisor holds the lease for this tick.
        """
        leases = self._store.lease
        if self._holding:
            if leases.renew(self._pid, self._host, now, LEASE_TTL_S):
                return True
            self._holding = False
            log.warning("supervisor.lease_renew_failed", pid=self._pid, host=self._host)
            return False
        claimed = leases.claim(self._pid, self._host, now, LEASE_TTL_S, self._pid_alive)
        if claimed is None:
            if not self._held_logged:
                held = leases.read()
                log.info(
                    "supervisor.lease_held",
                    holder_pid=None if held is None else held.holder_pid,
                    holder_host=None if held is None else held.holder_host,
                )
                self._held_logged = True
            return False
        self._holding = True
        self._held_logged = False
        log.info("supervisor.lease_taken", pid=self._pid, host=self._host, expires_at=claimed.expires_at)
        for request in self._store.runs.running():
            log.info(
                "supervisor.adopted", uid=request.uid, worker_pid=request.worker_pid, heartbeat_at=request.heartbeat_at
            )
        return True

    def _settle_ended(self, now: float) -> None:
        """Settle every running request whose worker exited, or went silent.

        Args:
            now: The tick's epoch.
        """
        for request in self._store.runs.running():
            code = None if request.worker_pid is None else self._launcher.exit_code(request.worker_pid)
            if code == LOST_LOCK_EXIT:
                request.back_to_queue(WaitReason.PIPELINE_LOCK_HELD)
                if self._store.runs.save(request):
                    log.info("supervisor.worker_lost_lock", uid=request.uid, kind=request.kind)
            elif code is not None:
                self._settle(request, _settlement_of(code), now, exit_code=code)
            elif request.stale(now):
                self._settle(request, self._settlement_from_row(request), now, exit_code=None)

    def _settlement_from_row(self, request: RunRequest) -> Settlement:
        """How a silent worker's run ended, read from its ``pipeline_run`` row.

        Args:
            request: The stale request; its uid is the row's.

        Returns:
            The row's outcome when it is final; ``interrupted`` when the row is missing, still
            ``running``, or unreadable.
        """
        db_path = self._config.indexer.db_path
        if db_path is None:
            return Settlement.INTERRUPTED
        try:
            conn = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
            try:
                row = conn.execute("SELECT outcome FROM pipeline_run WHERE run_uid = ?", (request.uid,)).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            log.warning("supervisor.run_row_unreadable", uid=request.uid, exc_info=True)
            return Settlement.INTERRUPTED
        outcome = None if row is None else row[0]
        return _ROW_SETTLEMENTS.get(str(outcome), Settlement.INTERRUPTED)

    def _settle(self, request: RunRequest, settlement: Settlement, now: float, *, exit_code: int | None) -> None:
        """Settle *request*, publish it, and feed a successful pipeline run to the watcher's safety net.

        Args:
            request: The running request.
            settlement: How it ended.
            now: The tick's epoch.
            exit_code: The worker's exit code; ``None`` when it was judged by its heartbeat.
        """
        request.settle(settlement, now)
        if not self._store.runs.save(request):
            return
        log.info("supervisor.settled", uid=request.uid, kind=request.kind, settlement=settlement, exit_code=exit_code)
        self._bus.emit(RunSettled(uid=request.uid, kind=request.kind, settlement=settlement))
        if (
            settlement is Settlement.SUCCESS
            and request.kind is RunKind.PIPELINE
            and not request.options.dry_run
            and self._watcher is not None
        ):
            self.watcher_state = dataclasses.replace(self.watcher_state, last_successful_run_at=now)
            try:
                self._watcher.record_success(now)
            except Exception:  # noqa: BLE001 — the in-memory state still paces this process
                log.warning("supervisor.success_persist_failed", exc_info=True)

    def _announce(self) -> None:
        """Publish ``RunQueued`` for each queued request this process sees for the first time."""
        queued = self._store.runs.queued()
        for request in queued:
            if request.uid in self._seen:
                continue
            self._seen.add(request.uid)
            self._bus.emit(RunQueued(uid=request.uid, kind=request.kind, trigger=request.trigger, joined=False))
        # Forget what left the queue for good, so the set does not grow with the history.
        live = {request.uid for request in queued} | {request.uid for request in self._store.runs.running()}
        self._seen &= live

    def _admit(self, now: float) -> None:
        """Start the head of the queue when nothing runs and nothing blocks it; else record why it waits.

        Args:
            now: The tick's epoch.
        """
        runs = self._store.runs
        head = runs.first_queued()
        if head is None:
            return
        if not runs.running():
            blocker = self._blocker()
            if blocker is not None:
                self._wait(head, blocker)
                return
            if not self._start(head, now):
                return
            head = runs.first_queued()
            if head is None:
                return
        self._wait(head, WaitReason.BEHIND_RUN)

    def _blocker(self) -> WaitReason | None:
        """Why the head may not start now, if anything stops it.

        Returns:
            ``paused`` when ``pipeline.pause`` is present; ``pipeline_lock_held`` when
            ``pipeline.lock`` or a scrape-resolve lock is held (the worker would lose the race);
            ``None`` otherwise.
        """
        data_dir = self._config.paths.data_dir
        if (data_dir / "pipeline.pause").exists():
            return WaitReason.PAUSED
        if is_lock_held(data_dir / "pipeline.lock") or any_scrape_resolve_active(scrape_locks_dir_for(data_dir)):
            return WaitReason.PIPELINE_LOCK_HELD
        return None

    def _wait(self, request: RunRequest, reason: WaitReason) -> None:
        """Record why *request* waits, when that changed.

        Args:
            request: The queued request.
            reason: Why it waits.
        """
        if request.wait_reason is reason:
            return
        request.wait(reason)
        self._store.runs.save(request)

    def _start(self, request: RunRequest, now: float) -> bool:
        """Start *request*'s worker and admit it; a start that fails settles it ``abandoned``.

        Args:
            request: The head of the queue.
            now: The tick's epoch.

        Returns:
            ``True`` when its worker started.
        """
        try:
            pid = self._launcher.start(request.uid)
        except OSError as exc:
            log.error("supervisor.worker_start_failed", uid=request.uid, kind=request.kind, error=str(exc))
            # No worker ever ran. The model settles only a running request, so it passes through
            # running under a process id that names no process, and is settled in the same write.
            request.admit(_NO_WORKER, now)
            self._settle(request, Settlement.ABANDONED, now, exit_code=None)
            return False
        request.admit(pid, now)
        if not self._store.runs.save(request):
            log.error("supervisor.admit_lost", uid=request.uid, worker_pid=pid)
            return False
        log.info("supervisor.admitted", uid=request.uid, kind=request.kind, worker_pid=pid)
        self._bus.emit(RunAdmitted(uid=request.uid, kind=request.kind))
        return True

    def _ask(self, reason: str) -> None:
        """Ask the run a ``FIRE_RUN`` decided, as the system actor; a manual poke consumes its sentinel.

        Args:
            reason: The decision's reason (``completion``, ``safety_net`` or ``manual``).
        """
        try:
            trigger = RunTrigger(reason)
        except ValueError:
            log.error("supervisor.watcher_reason_unknown", reason=reason)
            return
        try:
            asked = self._runs.ask_run(self._system_actor(), trigger=trigger, options=RunOptions())
        except AppForbidden as exc:
            log.warning("supervisor.watcher_ask_refused", trigger=trigger, code=exc.code)
            return
        log.info("supervisor.watcher_asked", uid=asked.uid, trigger=trigger, joined=asked.joined)
        # Only an operator poke (``watch-now``) eats the sentinel, as the watch daemon always did.
        if trigger is RunTrigger.MANUAL:
            (self._config.paths.data_dir / "watch.trigger").unlink(missing_ok=True)
