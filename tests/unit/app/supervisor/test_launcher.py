"""Unit tests for ``ProcessWorkerLauncher``: a worker starts detached, its uid in its environment only.

No engine runs: ``Popen`` is replaced, or the child is a stub body that only exits.
"""

from __future__ import annotations

import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.launcher import RUN_UID_ENV, WORKER_MODULE, ProcessWorkerLauncher

_UID = RunUid("a" * 32)


class TestStart:
    """What a start asks of the operating system."""

    def test_the_worker_runs_detached_with_its_uid_in_the_environment(self) -> None:
        """The child is the worker module in a new session; the uid is in its env, never in its argv."""
        child = MagicMock(pid=4321)
        with patch("personalscraper.app.supervisor.launcher.subprocess.Popen", return_value=child) as popen:
            pid = ProcessWorkerLauncher().start(_UID)

        assert pid == 4321
        argv = popen.call_args.args[0]
        kwargs = popen.call_args.kwargs
        assert argv == [sys.executable, "-m", WORKER_MODULE]
        assert _UID not in argv
        assert kwargs["start_new_session"] is True
        assert kwargs["env"][RUN_UID_ENV] == _UID

    def test_a_failed_start_raises(self) -> None:
        """An ``OSError`` from the system reaches the supervisor (it settles the request ``abandoned``)."""
        with patch("personalscraper.app.supervisor.launcher.subprocess.Popen", side_effect=OSError("no fork")):
            try:
                ProcessWorkerLauncher().start(_UID)
            except OSError:
                return
        raise AssertionError("the start failure was swallowed")


class TestExitCode:
    """How the launcher reports a child's end."""

    def test_a_child_is_reported_until_it_is_reaped(self) -> None:
        """A stub child exiting 7 is read as 7 at every peek; only a reap that no longer wants it forgets it."""
        launcher = ProcessWorkerLauncher()
        stub = subprocess.Popen([sys.executable, "-c", "raise SystemExit(7)"])  # noqa: S603 — a stub body
        launcher._children[stub.pid] = stub
        deadline = time.monotonic() + 10
        code = launcher.exit_code(stub.pid)
        while code is None and time.monotonic() < deadline:
            time.sleep(0.05)
            code = launcher.exit_code(stub.pid)

        assert code == 7
        assert launcher.exit_code(stub.pid) == 7, "a peek forgot the code before the supervisor saved it"
        launcher.reap(keep={stub.pid})
        assert launcher.exit_code(stub.pid) == 7, "a child still wanted was reaped"
        launcher.reap(keep=set())
        assert launcher.exit_code(stub.pid) is None

    def test_reap_keeps_a_child_that_still_runs(self) -> None:
        """A child that has not exited stays tracked even when no request names it (its pid was never recorded)."""
        launcher = ProcessWorkerLauncher()
        running = MagicMock(pid=4321)
        running.poll.return_value = None
        launcher._children[4321] = running

        launcher.reap(keep=set())

        assert 4321 in launcher._children

    def test_a_process_it_did_not_start_is_unknown(self) -> None:
        """An adopted worker is not a child: no exit code, the supervisor judges it by its heartbeat."""
        assert ProcessWorkerLauncher().exit_code(1) is None
