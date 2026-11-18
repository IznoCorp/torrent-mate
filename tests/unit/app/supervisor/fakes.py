"""Test doubles of the supervisor's ports: the worker launcher and the watcher half.

Nothing here starts a process or reads a torrent client: the fake launcher hands out process ids
and exit codes the test chooses, the fake watcher half returns the inputs the test queues.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Collection

from personalscraper.acquire.watcher import WatcherInput, WatcherOutput, WatcherState
from personalscraper.app.supervisor.ids import RunUid


class FakeWorkerLauncher:
    """A launcher that starts nothing: it records the uids asked and serves the exit codes set by the test.

    Attributes:
        started: The uids started, in order.
        fail_with: When set, ``start`` raises it (no worker ever ran).
        fail_times: How many starts raise ``fail_with``; ``None`` for every one.
        on_start: Called with the uid at each start, before a process id is handed out (the
            moment ``Popen`` would run), so a test can read the store then.
        reaped: The ``keep`` sets each ``reap`` was handed.
    """

    def __init__(self, first_pid: int = 4000) -> None:
        """Start with no worker.

        Args:
            first_pid: The process id the first started worker gets; the next ones count up.
        """
        self.started: list[RunUid] = []
        self.fail_with: BaseException | None = None
        self.fail_times: int | None = None
        self.on_start: Callable[[RunUid], None] | None = None
        self.reaped: list[set[int]] = []
        self._next_pid = first_pid
        self._exits: dict[int, int] = {}
        self._pids: dict[RunUid, int] = {}

    def start(self, uid: RunUid) -> int:
        """Record the start of *uid*'s worker.

        Args:
            uid: The request.

        Returns:
            The fake process id.

        Raises:
            BaseException: ``fail_with``, while it is set and ``fail_times`` is not spent.
        """
        if self.fail_with is not None and (self.fail_times is None or self.fail_times > 0):
            if self.fail_times is not None:
                self.fail_times -= 1
            raise self.fail_with
        if self.on_start is not None:
            self.on_start(uid)
        pid = self._next_pid
        self._next_pid += 1
        self.started.append(uid)
        self._pids[uid] = pid
        return pid

    def exit_code(self, pid: int) -> int | None:
        """The exit code the test set for *pid*.

        Args:
            pid: The worker's process id.

        Returns:
            The code, or ``None`` while the test has not ended it.
        """
        return self._exits.get(pid)

    def reap(self, keep: Collection[int]) -> None:
        """Record the process ids the supervisor still wants.

        Args:
            keep: The workers of the requests still running.
        """
        self.reaped.append(set(keep))

    def pid_of(self, uid: RunUid) -> int:
        """The process id *uid*'s worker was given.

        Args:
            uid: The request.

        Returns:
            Its process id.
        """
        return self._pids[uid]

    def exit(self, uid: RunUid, code: int) -> None:
        """End *uid*'s worker with *code*.

        Args:
            uid: The request.
            code: Its exit code (negative: killed by that signal).
        """
        self._exits[self._pids[uid]] = code


class FakeWatcherHalf:
    """A watcher half serving queued inputs; it records what the supervisor asked of it.

    Attributes:
        inputs: The inputs the next polls return, in order; an empty list polls ``None``.
        polls: How many times it was polled.
        cross_seeded: The hash lists handed to ``cross_seed``.
        pending: The ``(fires_at, active_downloads, now)`` published.
        successes: The epochs recorded as a successful run.
        restored_at: What ``restore`` writes into the state's ``last_successful_run_at``.
    """

    def __init__(self, restored_at: float | None = None) -> None:
        """Start with nothing queued.

        Args:
            restored_at: The last successful run the restore reads back.
        """
        self.inputs: list[WatcherInput] = []
        self.polls = 0
        self.cross_seeded: list[list[str]] = []
        self.pending: list[tuple[float | None, int, float]] = []
        self.successes: list[float] = []
        self.restored_at = restored_at

    def restore(self, state: WatcherState) -> None:
        """Write the stored last successful run into *state*.

        Args:
            state: The state, mutated in place.
        """
        state.last_successful_run_at = self.restored_at

    def poll(self) -> WatcherInput | None:
        """Serve the next queued input.

        Returns:
            The input, or ``None`` when none is queued.
        """
        self.polls += 1
        return self.inputs.pop(0) if self.inputs else None

    def cross_seed(self, out: WatcherOutput, state: WatcherState) -> WatcherState:
        """Record the hashes handed over.

        Args:
            out: The decision.
            state: The state.

        Returns:
            The state, unchanged.
        """
        self.cross_seeded.append(list(out.cross_seed_hashes))
        return dataclasses.replace(state)

    def publish_pending(self, fires_at: float | None, active_downloads: int, now: float) -> None:
        """Record the pending run published.

        Args:
            fires_at: When the debounced run fires.
            active_downloads: How many downloads still run.
            now: The cycle's epoch.
        """
        self.pending.append((fires_at, active_downloads, now))

    def record_success(self, now: float) -> None:
        """Record a successful run.

        Args:
            now: Its epoch.
        """
        self.successes.append(now)
