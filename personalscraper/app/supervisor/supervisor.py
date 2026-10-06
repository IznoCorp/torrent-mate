"""The ``Supervisor``: the one process per environment that starts asked runs, under its lease.

One loop, two cadences (:meth:`Supervisor.run`):

- **Admission**, every :data:`ADMISSION_INTERVAL_S` (:meth:`Supervisor.tick_admission`): hold the
  lease (claim it, or renew it); settle the requests whose worker ended (its exit code, for a worker
  this process started), is gone (an adopted worker's pid no longer runs) or went silent (a stale
  heartbeat): the outcome of its ``pipeline_run`` row, else ``interrupted`` — or back to the queue
  for a gone worker that never beat and left no row (it lost ``pipeline.lock``); announce the
  requests seen for the first time; then, when nothing runs, start the head of the queue — unless
  ``pipeline.pause`` is present or ``pipeline.lock`` (or a scrape-resolve lock) is held, the head
  then recording why it waits. The admission is saved BEFORE the worker is started, so a crash in
  between leaves a running request that goes stale, never a worker on a queued one.
- **The watcher**, every ``watch.poll_interval_s`` (:meth:`Supervisor.tick_watcher`): today's poll and
  decision engine, unchanged, behind the :class:`WatcherHalf` port; a ``FIRE_RUN`` becomes an ask of
  the run service instead of a spawned ``run``, and the input's « pipeline lock held » becomes « a
  request is queued or running », so a requeue keeps its meaning. An ask that is not taken (refused,
  or raising) restores the state the decision started from, so the trigger fires again. The lease is
  renewed from a thread while the tick runs (a poll or a cross-seed child can outlast its TTL).

Only the lease's holder admits or watches: a second supervisor idles until the lease lapses, or
until its holder is gone from this machine. Workers are detached and outlive the supervisor; a
restarted one adopts the running requests and judges them by their heartbeat.
"""

from __future__ import annotations

import dataclasses
import errno
import os
import socket
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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
from personalscraper.pipeline_history import PipelineRunWriter

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

#: Seconds between two renewals of the lease while a watcher tick runs: a third of its TTL, so two
#: renewals may fail before it lapses.
LEASE_KEEP_INTERVAL_S: Final = LEASE_TTL_S / 3

#: Consecutive failures of one kind of tick after which the loop stops, so PM2 restarts the
#: process: thirty admission ticks are a minute (one lease TTL) — longer than any transient lock of
#: ``app.db`` (its busy timeout is seconds), short enough that a wedged queue is restarted, not
#: left silent.
MAX_CONSECUTIVE_TICK_FAILURES: Final = 30

#: Attempts to start a request's worker that fail for a transient cause before it is abandoned
#: (about ten seconds of admission ticks: an fd or memory shortage that lasts longer is not brief).
MAX_WORKER_START_ATTEMPTS: Final = 5

#: The ``errno`` of a start failure that may pass (a resource shortage): the head is retried.
_TRANSIENT_START_ERRNOS: Final = frozenset({errno.EMFILE, errno.ENFILE, errno.ENOMEM, errno.EAGAIN})

#: A ``pipeline_run`` outcome that tells how a silent worker's run ended.
_ROW_SETTLEMENTS: Final[dict[str, Settlement]] = {
    "success": Settlement.SUCCESS,
    "error": Settlement.ERROR,
    "killed": Settlement.KILLED,
}


class SupervisorWedged(RuntimeError):
    """A tick failed :data:`MAX_CONSECUTIVE_TICK_FAILURES` times in a row: the process must restart."""


class _LeaseKeeper:
    """A daemon thread renewing the lease every interval while one long tick holds the loop."""

    def __init__(self, renew: Callable[[], bool], interval_s: float) -> None:
        """Prepare the thread; nothing runs until the block is entered.

        Args:
            renew: Renews the lease; ``False`` when it is no longer this supervisor's.
            interval_s: Seconds between two renewals.
        """
        self._renew = renew
        self._interval_s = interval_s
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._keep, name="supervisor-lease-keeper", daemon=True)

    def _keep(self) -> None:
        """Renew each interval until stopped; a lost lease ends the thread, a failed renewal is retried."""
        while not self._stopped.wait(self._interval_s):
            try:
                if not self._renew():
                    # Taken over: the next admission tick's renewal fails too and stops admitting.
                    log.warning("supervisor.lease_keep_lost")
                    return
            except Exception:  # noqa: BLE001 — a missed renewal is retried; two may fail within the TTL
                log.warning("supervisor.lease_keep_failed", exc_info=True)

    @contextmanager
    def running(self) -> Iterator[None]:
        """Renew from the thread for the block's duration, then stop it and wait for it.

        Yields:
            Nothing.
        """
        self._thread.start()
        try:
            yield
        finally:
            self._stopped.set()
            self._thread.join()


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
        self._start_failures: dict[str, int] = {}
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
        process that every run waits on. A kind of tick failing :data:`MAX_CONSECUTIVE_TICK_FAILURES`
        times in a row is no longer transient: the loop stops, so PM2 restarts the process.

        Args:
            should_stop: Asked before each tick.
            sleep: Waits between two ticks.

        Raises:
            SupervisorWedged: When one kind of tick failed that many times in a row.
        """
        next_watch = 0.0
        failures: dict[str, int] = {}
        try:
            while not should_stop():
                self._guarded(self.tick_admission, failures)
                if self._clock() >= next_watch:
                    self._guarded(self.tick_watcher, failures)
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
        """Run one watcher cycle: poll, decide, publish, and act on the decision — the lease kept meanwhile."""
        if not self._holding or self._watcher is None or not self._config.watch.enabled:
            return
        if (self._config.paths.data_dir / "watcher.paused").exists():
            log.debug("supervisor.watcher_paused")
            return
        # A poll or a cross-seed child (up to its 1800 s timeout) can outlast the lease's TTL: renewing
        # between steps would not hold through one long child, so a thread renews for the whole tick.
        keeper = _LeaseKeeper(
            lambda: self._store.lease.renew(self._pid, self._host, self._clock(), LEASE_TTL_S), LEASE_KEEP_INTERVAL_S
        )
        with keeper.running():
            self._watch_cycle(self._watcher)

    def _watch_cycle(self, watcher: WatcherHalf) -> None:
        """Poll, decide, publish, and act on the decision; a FIRE_RUN not taken leaves the state as it was.

        Args:
            watcher: The watcher half.

        Raises:
            Exception: Whatever the ask raised, after the state was restored.
        """
        polled = watcher.poll()
        if polled is None:
            return
        view = self._runs.queue_view()
        busy = view.running is not None or bool(view.queued)
        inp = dataclasses.replace(polled, pipeline_lock_held=busy)
        # ``evaluate`` arms the debounce window and the backoff of the run it fires: an ask that is
        # not taken must not lose the trigger until that window ends.
        before = dataclasses.replace(self.watcher_state)
        out = self._engine.evaluate(inp, self.watcher_state)
        self.watcher_state = out.new_state
        try:
            watcher.publish_pending(
                fires_at=self.watcher_state.debounce_until, active_downloads=inp.downloading_count, now=inp.now
            )
        except Exception:  # noqa: BLE001 — advisory: visibility never breaks the watch
            log.warning("supervisor.pending_run_publish_failed", exc_info=True)
        if out.decision is WatcherDecision.FIRE_RUN:
            try:
                taken = self._ask(out.run_reason)
            except Exception:
                self.watcher_state = before
                raise
            if not taken:
                self.watcher_state = before
        elif out.decision is WatcherDecision.FIRE_CROSS_SEED:
            self.watcher_state = watcher.cross_seed(out, self.watcher_state)
        elif out.decision is WatcherDecision.REQUEUE:
            log.debug("supervisor.watcher_requeue", reason="run_queued")

    def _guarded(self, tick: Callable[[], None], failures: dict[str, int]) -> None:
        """Run one tick; log what it raises instead of stopping the loop, until it keeps failing.

        Args:
            tick: The tick.
            failures: The consecutive failures of each kind of tick, by name; a success resets its count.

        Raises:
            SupervisorWedged: When this kind of tick has now failed :data:`MAX_CONSECUTIVE_TICK_FAILURES`
                times in a row.
        """
        name = getattr(tick, "__name__", "tick")
        try:
            tick()
        except Exception as exc:  # noqa: BLE001 — the loop outlives a failed tick; the next one retries
            count = failures.get(name, 0) + 1
            failures[name] = count
            log.exception("supervisor.tick_failed", tick=name, consecutive=count)
            if count >= MAX_CONSECUTIVE_TICK_FAILURES:
                log.error("supervisor.ticks_failing", tick=name, consecutive=count)
                raise SupervisorWedged(f"{name} failed {count} times in a row") from exc
            return
        failures[name] = 0

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
        """Settle every running request whose worker exited, is gone, or went silent; then reap the children.

        A child's exit code is read again at each tick until its request has left ``running`` (a
        save that raised loses nothing); only then does the reap forget the child.

        Args:
            now: The tick's epoch.
        """
        for request in self._store.runs.running():
            pid = request.worker_pid
            code = None if pid is None else self._launcher.exit_code(pid)
            if code == LOST_LOCK_EXIT:
                self._requeue_lost_lock(request)
            elif code is not None:
                self._settle(request, _settlement_of(code), now, exit_code=code)
            else:
                # Not a child of this process (adopted), or a pid never recorded: its pid tells it is
                # gone at once; its heartbeat tells it went silent.
                gone = pid is not None and not self._pid_alive(pid)
                if gone or request.stale(now):
                    self._settle_silent(request, now, gone=gone)
        self._launcher.reap(
            keep={request.worker_pid for request in self._store.runs.running() if request.worker_pid is not None}
        )

    def _requeue_lost_lock(self, request: RunRequest) -> None:
        """Put back in the queue a request whose worker lost the race for ``pipeline.lock``.

        Args:
            request: The running request.
        """
        request.back_to_queue(WaitReason.PIPELINE_LOCK_HELD)
        if self._store.runs.save(request):
            log.info("supervisor.worker_lost_lock", uid=request.uid, kind=request.kind)

    def _settle_silent(self, request: RunRequest, now: float, *, gone: bool) -> None:
        """Settle a request whose worker is gone or silent, from its ``pipeline_run`` row.

        A gone worker that left no row and never beat its heartbeat ran nothing: it lost the lock
        (exit 3, unseen by a supervisor that is not its parent), so its request is queued again. A
        row that cannot be read now is retried at the next tick, never taken for a missing one.

        Args:
            request: The running request.
            now: The tick's epoch.
            gone: Whether its worker's pid no longer runs (else its heartbeat is stale).
        """
        try:
            outcome = self._row_outcome(request)
        except sqlite3.Error:
            log.warning("supervisor.run_row_unreadable", uid=request.uid, exc_info=True)
            return
        if gone and outcome is None and request.heartbeat_at == request.admitted_at:
            self._requeue_lost_lock(request)
            return
        settlement = (
            Settlement.INTERRUPTED if outcome is None else _ROW_SETTLEMENTS.get(outcome, Settlement.INTERRUPTED)
        )
        self._settle(request, settlement, now, exit_code=None)

    def _row_outcome(self, request: RunRequest) -> str | None:
        """The outcome of *request*'s ``pipeline_run`` row, read through the row's owner.

        Args:
            request: The request; its uid is the row's.

        Returns:
            The row's outcome; ``None`` when there is no row (or no library store).

        Raises:
            sqlite3.Error: If the library store cannot be read now.
        """
        db_path = self._config.indexer.db_path
        if db_path is None:
            return None
        return PipelineRunWriter(Path(db_path)).outcome(request.uid)

    def _settle(self, request: RunRequest, settlement: Settlement, now: float, *, exit_code: int | None) -> None:
        """Settle *request*, publish it, and feed a successful pipeline run to the watcher's safety net.

        Args:
            request: The running request.
            settlement: How it ended.
            now: The tick's epoch.
            exit_code: The worker's exit code; ``None`` when it was judged by its pid or heartbeat.
        """
        request.settle(settlement, now)
        self._save_settled(request, settlement, now, exit_code=exit_code)

    def _save_settled(self, request: RunRequest, settlement: Settlement, now: float, *, exit_code: int | None) -> None:
        """Save a request just settled, publish it, and feed a successful pipeline run to the safety net.

        Args:
            request: The settled request.
            settlement: How it ended (its ``settlement``).
            now: The tick's epoch.
            exit_code: The worker's exit code, if one was read.
        """
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
        self._start_failures = {uid: count for uid, count in self._start_failures.items() if uid in live}

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
        """Admit *request* durably, then start its worker, then record the worker's pid.

        The order is the guarantee: a worker exists only for a request already saved ``running``
        (it refuses any other), so a crash between the two leaves a running request whose
        heartbeat goes stale (``interrupted``), never a queued one started a second time.

        Args:
            request: The head of the queue.
            now: The tick's epoch.

        Returns:
            ``True`` when its worker started.
        """
        request.admit(None, now)
        if not self._store.runs.save(request):
            log.error("supervisor.admit_lost", uid=request.uid)
            return False
        try:
            pid = self._launcher.start(request.uid)
        except Exception as exc:  # noqa: BLE001 — any failure to start is the request's, never the loop's
            self._start_failed(request, now, exc)
            return False
        self._start_failures.pop(request.uid, None)
        request.record_worker(pid)
        if not self._store.runs.save(request):
            log.error("supervisor.worker_pid_lost", uid=request.uid, worker_pid=pid)
        log.info("supervisor.admitted", uid=request.uid, kind=request.kind, worker_pid=pid)
        self._bus.emit(RunAdmitted(uid=request.uid, kind=request.kind))
        return True

    def _start_failed(self, request: RunRequest, now: float, exc: Exception) -> None:
        """Undo the admission of a request whose worker did not start: retry a transient cause, else abandon.

        Args:
            request: The request, saved ``running`` with no worker.
            now: The tick's epoch.
            exc: Why the start failed.
        """
        transient = isinstance(exc, OSError) and exc.errno in _TRANSIENT_START_ERRNOS
        attempt = self._start_failures.get(request.uid, 0) + 1
        log.error(
            "supervisor.worker_start_failed",
            uid=request.uid,
            kind=request.kind,
            error=str(exc) or type(exc).__name__,
            attempt=attempt,
            transient=transient,
        )
        request.back_to_queue(WaitReason.WORKER_START_FAILED)
        if transient and attempt < MAX_WORKER_START_ATTEMPTS:
            self._start_failures[request.uid] = attempt
            self._store.runs.save(request)
            return
        self._start_failures.pop(request.uid, None)
        request.abandon(now)
        self._save_settled(request, Settlement.ABANDONED, now, exit_code=None)

    def _ask(self, reason: str) -> bool:
        """Ask the run a ``FIRE_RUN`` decided, as the system actor; a manual poke consumes its sentinel.

        Args:
            reason: The decision's reason (``completion``, ``safety_net`` or ``manual``).

        Returns:
            ``True`` when the ask was taken (queued or joined); ``False`` when it was refused.
        """
        try:
            trigger = RunTrigger(reason)
        except ValueError:
            log.error("supervisor.watcher_reason_unknown", reason=reason)
            return False
        try:
            asked = self._runs.ask_run(self._system_actor(), trigger=trigger, options=RunOptions())
        except AppForbidden as exc:
            log.warning("supervisor.watcher_ask_refused", trigger=trigger, code=exc.code)
            return False
        log.info("supervisor.watcher_asked", uid=asked.uid, trigger=trigger, joined=asked.joined)
        # Only an operator poke (``watch-now``) eats the sentinel, as the watch daemon always did.
        if trigger is RunTrigger.MANUAL:
            (self._config.paths.data_dir / "watch.trigger").unlink(missing_ok=True)
        return True
