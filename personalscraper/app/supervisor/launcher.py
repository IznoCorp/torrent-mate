"""The port the supervisor starts a worker through, and its process implementation.

A worker is one detached process running one request (``python -m
personalscraper.app.supervisor.worker``): it is started in a session of its own, so it outlives the
supervisor that started it (a PM2 restart never kills a run), and it learns WHICH request from its
environment only (:data:`RUN_UID_ENV`): its argv carries no option.

The launcher also reports the exit code of a worker it started itself, for as long as the
supervisor wants it (:meth:`WorkerLauncher.reap` forgets it once its request is no longer
running, so a save that failed can read the code again); a worker adopted from a previous
supervisor is not its child, and the supervisor judges it by its pid and its heartbeat instead.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Collection
from typing import Final, Protocol

from personalscraper.app.supervisor.ids import RunUid

#: The environment variable a worker reads its request's uid from.
RUN_UID_ENV: Final = "PERSONALSCRAPER_RUN_UID"

#: The exit code of a worker that lost the race for ``pipeline.lock``: nothing ran, nothing was
#: written, and the supervisor puts its request back in the queue.
LOST_LOCK_EXIT: Final = 3

#: The worker's module, run with ``python -m``.
WORKER_MODULE: Final = "personalscraper.app.supervisor.worker"


class WorkerLauncher(Protocol):
    """Starts the worker of one request and reports how its own workers ended."""

    def start(self, uid: RunUid) -> int:
        """Start the worker of request *uid*, detached.

        Args:
            uid: The request the worker runs.

        Returns:
            The worker's process id.

        Raises:
            Exception: If no worker could be started (an ``OSError`` from the system, mostly).
        """
        ...

    def exit_code(self, pid: int) -> int | None:
        """The exit code of a worker this launcher started, once it has exited; reading it forgets nothing.

        Args:
            pid: The worker's process id.

        Returns:
            Its exit code (negative: the signal that killed it); ``None`` while it runs, or when
            this launcher did not start it (or reaped it).
        """
        ...

    def reap(self, keep: Collection[int]) -> None:
        """Forget every exited worker but those in *keep*.

        Args:
            keep: The process ids of the workers whose requests still run (their codes are still wanted).
        """
        ...


class ProcessWorkerLauncher:
    """Starts each worker as a detached ``python -m`` child, in a session of its own."""

    def __init__(self) -> None:
        """Start with no child."""
        self._children: dict[int, subprocess.Popen[bytes]] = {}

    def start(self, uid: RunUid) -> int:
        """Start the worker of request *uid*, detached (new session, the uid in its environment only).

        Args:
            uid: The request the worker runs.

        Returns:
            The worker's process id.

        Raises:
            OSError: If the process could not be started.
        """
        child = subprocess.Popen(  # fixed argv: this interpreter and the worker module
            [sys.executable, "-m", WORKER_MODULE],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            env={**os.environ, RUN_UID_ENV: uid},
        )
        self._children[child.pid] = child
        return child.pid

    def exit_code(self, pid: int) -> int | None:
        """The exit code of a child started here, once it has exited; it stays known until reaped.

        Args:
            pid: The worker's process id.

        Returns:
            Its exit code; ``None`` while it runs, or when it is not a child of this launcher.
        """
        child = self._children.get(pid)
        return None if child is None else child.poll()

    def reap(self, keep: Collection[int]) -> None:
        """Forget every exited child but those in *keep*; a child still running stays tracked.

        A child whose pid was never recorded on its request (the supervisor died, or its save
        failed) is not in *keep*, and is forgotten only once it has exited.

        Args:
            keep: The process ids of the workers whose requests still run.
        """
        for pid in [pid for pid, child in self._children.items() if pid not in keep and child.poll() is not None]:
            del self._children[pid]
