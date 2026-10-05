#!/usr/bin/env python3
"""The machine-wide guard: no agent's run may hold IznoServer saturated (B-703).

WHY IT EXISTS. On 2026-10-05 a run started eight browsers and eight CPU burners
and drove the one-minute load to 84 on 8 cores until the operator had it killed.
`scripts/heavy.sh` now owns and watches what it admits, but an agent can skip
`heavy.sh`, and nothing else on the machine watched the load.

WHAT IT DOES. Once a minute it reads the one-minute load. When the load has
stayed above the machine's capacity (its core count) for SUSTAINED_MINUTES
minutes in a row, it logs the heaviest process trees, then kills the trees that
run from an agent's checkout or scratchpad (`~/dev/workspaces/*` and those
checkouts' `/private/tmp/claude-<uid>/-Users-<user>-dev-workspaces-*`, by working
directory only — never the main checkout `~/dev/PersonalScraper`) and burn at
least MIN_TREE_CPU % CPU — stopped first so nothing respawns, terminated, then
killed. Each tree killed leaves a `GUARD KILLED` line in its
log (`~/Library/Logs/machine-guard.log`, `MACHINE_GUARD_LOG`), which the
orchestrator watches.

WHAT IT NEVER TOUCHES. A service: Plex, Parsec, qBittorrent, a PM2-managed app
and anything those start, WindowServer, launchd — and no `claude` process, ever:
a tree is cut at a Claude session, so its shell's command may go, never the
session. Another user's processes are not even read. The guard and its parents
are never chosen.

Allow and deny are decided by pure functions over a process table
(`choose_victims`, `overloaded_minutes`), unit-tested on fake tables in
`tests/scripts/test_machine_guard.py`; only `main` reads the machine.

Usage:
    python3 scripts/machine_guard.py --loop        # the PM2 app: one look a minute
    python3 scripts/machine_guard.py --once --state FILE   # one look, the count kept in FILE
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

# Minutes in a row the load must stay above the capacity before the guard acts.
SUSTAINED_MINUTES = 3
# A tree burning less than this (% of one core) is not what saturates the machine.
MIN_TREE_CPU = 50.0
# Seconds between the TERM and the KILL.
GRACE_SECONDS = 5
# How many trees the log lists when the guard acts.
TOP_TREES = 10
LOG_MAX_BYTES = 1_048_576
LOOK_SECONDS = 60
# `ps` prints a start time in the C locale's words whatever the operator's locale.
PS_ENV = {**os.environ, "LC_ALL": "C"}

# Services, by their executable (never an argument: a prompt or a test path
# names them all the time); their every descendant is theirs, never killed.
SERVICE = re.compile(r"Plex|parsecd|Parsec\.app|qBittorrent|qbittorrent|^PM2 v[\d.]+: God Daemon")
# The system's own processes, by their executable: never killed.
SYSTEM = re.compile(r"WindowServer|loginwindow|launchd|kernel_task")
# Never killed. A `claude` session by its binary's name or its npm package.
CLAUDE = re.compile(r"(?:^|/)claude(?:\s|$)|@anthropic-ai/claude-code|claude-code/cli")


@dataclass(frozen=True)
class Process:
    """One row of the process table.

    Attributes:
        pid: The process id.
        ppid: Its parent's.
        cpu: Its % CPU (100 is one core).
        command: Its command line.
        cwd: Its working directory, empty when unknown.
        executable: What `ps -o comm=` names: the executable, or the title a
            program gave itself (PM2's God Daemon); never its arguments.
        started: When it started (`ps -o lstart=`): with the pid, its identity.
    """

    pid: int
    ppid: int
    cpu: float
    command: str
    cwd: str = ""
    executable: str = ""
    started: str = ""


@dataclass(frozen=True)
class Tree:
    """A process and its descendants, as the guard weighs and kills them.

    Attributes:
        root: The tree's top process.
        pids: Every pid of the tree, the root first.
        cpu: Their summed % CPU.
        command: The root's command line.
    """

    root: int
    pids: tuple[int, ...]
    cpu: float
    command: str


def overloaded_minutes(previous: int, load: float, capacity: float) -> int:
    """Counts the minutes in a row the load has stayed above the capacity.

    Args:
        previous: The count after the previous look.
        load: The one-minute load now.
        capacity: The machine's capacity in cores.

    Returns:
        The count after this look: 0 as soon as the load is at or under the capacity.
    """
    return previous + 1 if load > capacity else 0


def agent_places(home: str) -> re.Pattern[str]:
    """Where an agent's checkouts and their scratchpads live.

    A checkout is under `~/dev/workspaces/`; Claude Code names a session's
    scratchpad after the session's cwd (`/private/tmp/claude-<uid>/-Users-<user>-dev-workspaces-…`).
    The main checkout (`~/dev/PersonalScraper`) and the scratchpads of the
    sessions working there — the orchestrator's, the auditor's — are no agent's place.

    Args:
        home: The operator's home directory.

    Returns:
        The pattern a working directory under an agent's place matches from its start.
    """
    scratchpad = home.replace("/", "-") + "-dev-workspaces-"
    return re.compile(rf"{re.escape(home)}/dev/workspaces/|(?:/private)?/tmp/claude-\d+/{re.escape(scratchpad)}")


def runs_from_agent(process: Process, places: re.Pattern[str]) -> bool:
    """Whether a process runs from an agent's checkout or scratchpad.

    Read on the working directory alone, never on the command line: every
    Claude Code Bash wrapper names `/tmp/claude-XXXX-cwd` in its argv, and an
    argument may name any path.

    Args:
        process: The process.
        places: The agents' places, from `agent_places`.

    Returns:
        True when its working directory is under one.
    """
    return places.match(process.cwd) is not None


def _subtree(root: int, children: dict[int, list[int]], cut: Callable[[int], bool]) -> list[int]:
    """A process and its descendants, a cut process and its own descendants left out.

    Args:
        root: The top process.
        children: Each pid's children.
        cut: Whether a pid is left out with everything under it.

    Returns:
        The pids, the root first.
    """
    found: list[int] = []
    pending = [root]
    while pending:
        pid = pending.pop()
        if cut(pid):
            continue
        found.append(pid)
        pending.extend(children.get(pid, []))
    return found


def _children(table: Iterable[Process]) -> dict[int, list[int]]:
    """Each pid's children in a table.

    Args:
        table: The process table.

    Returns:
        The children, by parent pid.
    """
    children: dict[int, list[int]] = {}
    for process in table:
        children.setdefault(process.ppid, []).append(process.pid)
    return children


def choose_victims(table: list[Process], *, me: int, home: str, min_cpu: float = MIN_TREE_CPU) -> list[Tree]:
    """The trees the guard kills in a process table, the heaviest first.

    A tree's root is the highest process of an agent's run: one that runs from
    an agent's place, whose parent does not (or is a Claude session, launchd,
    or a protected process). Its descendants go with it, whatever they run from,
    save a protected one and everything under it.

    Args:
        table: The process table.
        me: The guard's own pid; it and its ancestors are never chosen.
        home: The operator's home directory.
        min_cpu: The least % CPU a tree must burn to be chosen.

    Returns:
        The trees to kill.
    """
    by_pid = {process.pid: process for process in table}
    children = _children(table)
    places = agent_places(home)

    mine: set[int] = set()
    pid = me
    while pid in by_pid and pid not in mine:
        mine.add(pid)
        pid = by_pid[pid].ppid
    mine.add(me)

    def protected(pid: int) -> bool:
        """Whether a pid is a service, a service's descendant, a Claude session or the guard's own line."""
        if pid <= 1 or pid in mine:
            return True
        seen: set[int] = set()
        current = by_pid.get(pid)
        if current is not None and (SYSTEM.search(current.executable) or CLAUDE.search(current.command)):
            return True
        while current is not None and current.pid not in seen:
            seen.add(current.pid)
            if SERVICE.search(current.executable):
                return True
            current = by_pid.get(current.ppid)
        return False

    def eligible(pid: int) -> bool:
        """Whether a pid belongs to an agent's run and may be killed."""
        process = by_pid.get(pid)
        return process is not None and not protected(pid) and runs_from_agent(process, places)

    roots: set[int] = set()
    for process in table:
        if not eligible(process.pid):
            continue
        root = process.pid
        while eligible(by_pid[root].ppid):
            root = by_pid[root].ppid
        roots.add(root)

    trees = []
    for root in roots:
        pids = _subtree(root, children, protected)
        cpu = sum(by_pid[pid].cpu for pid in pids if pid in by_pid)
        if pids and cpu >= min_cpu:
            trees.append(Tree(root=root, pids=tuple(pids), cpu=cpu, command=by_pid[root].command))
    return sorted(trees, key=lambda tree: tree.cpu, reverse=True)


def top_trees(table: list[Process], count: int = TOP_TREES) -> list[Tree]:
    """The heaviest trees under launchd (or under no process in the table).

    Args:
        table: The process table.
        count: How many to list.

    Returns:
        The heaviest trees, the heaviest first.
    """
    by_pid = {process.pid: process for process in table}
    children = _children(table)
    trees = []
    for process in table:
        if process.pid > 1 and (process.ppid <= 1 or process.ppid not in by_pid):
            pids = _subtree(process.pid, children, lambda pid: False)
            cpu = sum(by_pid[pid].cpu for pid in pids if pid in by_pid)
            trees.append(Tree(root=process.pid, pids=tuple(pids), cpu=cpu, command=process.command))
    return sorted(trees, key=lambda tree: tree.cpu, reverse=True)[:count]


class Log:
    """The guard's log, rotated by size."""

    def __init__(self, path: Path, max_bytes: int = LOG_MAX_BYTES) -> None:
        """Points the log at its file.

        Args:
            path: The log file.
            max_bytes: The size past which it is moved to `<path>.1`.
        """
        self.path = path
        self.max_bytes = max_bytes

    def write(self, line: str) -> None:
        """Appends one dated line.

        Args:
            line: The line.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
            self.path.replace(self.path.with_name(self.path.name + ".1"))
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} machine-guard[{os.getpid()}] {line}\n")


def _describe(tree: Tree) -> str:
    """One tree, as the log says it.

    Args:
        tree: The tree.

    Returns:
        Its root, size, CPU and command.
    """
    return f"pid {tree.root} ({len(tree.pids)} processes, {tree.cpu:.0f}% CPU): {tree.command[:200]}"


def tick(
    minutes: int,
    *,
    load: float,
    capacity: float,
    table: Callable[[], list[Process]],
    started: Callable[[], dict[int, str]],
    send: Callable[[int, int], None],
    log: Log,
    me: int,
    home: str,
    grace_seconds: float = GRACE_SECONDS,
) -> int:
    """One look: counts the overloaded minutes and, once sustained, kills the agents' heavy trees.

    Args:
        minutes: The overloaded minutes counted so far.
        load: The one-minute load now.
        capacity: The machine's capacity in cores.
        table: Reads the process table.
        started: Reads each live pid's start time, the identity a signal is checked against.
        send: Sends a signal to a pid (a pid already gone is no error).
        log: The guard's log.
        me: The guard's own pid.
        home: The operator's home directory.
        grace_seconds: Seconds between the TERM and the KILL.

    Returns:
        The overloaded minutes after this look: 0 once the guard has acted.
    """
    minutes = overloaded_minutes(minutes, load, capacity)
    if minutes == 0:
        return 0
    log.write(f"load {load:.1f} above capacity {capacity:g} — minute {minutes} of {SUSTAINED_MINUTES}")
    if minutes < SUSTAINED_MINUTES:
        return minutes

    snapshot = table()
    log.write("top trees:")
    for tree in top_trees(snapshot):
        log.write(f"  {_describe(tree)}")
    victims = choose_victims(snapshot, me=me, home=home)
    if not victims:
        log.write("no agent tree to kill — the load is someone else's")
        return 0

    # A pid is signalled only while it is the process chosen: same pid, same
    # start time, read again just before each signal — never a pid reused.
    identities = {process.pid: process.started for process in snapshot}

    def same() -> list[list[int]]:
        """Each victim's pids still the processes the snapshot saw, read once."""
        now = started()
        return [[pid for pid in tree.pids if pid in now and now[pid] == identities.get(pid)] for tree in victims]

    for pids in same():
        for pid in pids:
            send(pid, signal.SIGSTOP)
    for pids in same():
        for pid in pids:
            send(pid, signal.SIGTERM)
            send(pid, signal.SIGCONT)
    time.sleep(grace_seconds)
    for tree, pids in zip(victims, same(), strict=True):
        for pid in pids:
            send(pid, signal.SIGKILL)
        log.write(f"GUARD KILLED {_describe(tree)}")
    return 0


def read_table() -> list[Process]:
    """The machine's process table, this user's processes only, with their working directories.

    Returns:
        The processes.
    """
    uid = str(os.getuid())
    listing = subprocess.run(
        ["ps", "-Ao", "pid=,ppid=,uid=,pcpu=,lstart=,command="], capture_output=True, text=True, check=False, env=PS_ENV
    ).stdout
    # `comm` may hold spaces: a listing of its own, the pid first, is unambiguous.
    names = subprocess.run(["ps", "-Ao", "pid=,comm="], capture_output=True, text=True, check=False).stdout
    executables: dict[int, str] = {}
    for line in names.splitlines():
        fields = line.split(None, 1)
        if len(fields) == 2:
            executables[int(fields[0])] = fields[1].strip()
    cwds: dict[int, str] = {}
    files = subprocess.run(
        ["lsof", "-w", "-a", "-u", uid, "-d", "cwd", "-Fpn"], capture_output=True, text=True, check=False
    ).stdout
    current = 0
    for line in files.splitlines():
        if line.startswith("p"):
            current = int(line[1:])
        elif line.startswith("n") and current:
            cwds[current] = line[1:]
    table = []
    for line in listing.splitlines():
        # pid, ppid, uid, % CPU, the start time's five words, the command.
        fields = line.split(None, 9)
        if len(fields) < 10 or fields[2] != uid:
            continue
        pid = int(fields[0])
        table.append(
            Process(
                pid=pid,
                ppid=int(fields[1]),
                cpu=float(fields[3].replace(",", ".")),
                command=fields[9],
                cwd=cwds.get(pid, ""),
                executable=executables.get(pid, ""),
                started=" ".join(fields[4:9]),
            )
        )
    return table


def read_started() -> dict[int, str]:
    """Each live pid's start time, as `read_table` reads it.

    Returns:
        The start times, by pid.
    """
    listing = subprocess.run(
        ["ps", "-Ao", "pid=,lstart="], capture_output=True, text=True, check=False, env=PS_ENV
    ).stdout
    started: dict[int, str] = {}
    for line in listing.splitlines():
        fields = line.split()
        if len(fields) == 6:
            started[int(fields[0])] = " ".join(fields[1:])
    return started


def send_signal(pid: int, number: int) -> None:
    """Sends a signal; a process already gone, or not ours, is no error.

    Args:
        pid: The process.
        number: The signal.
    """
    try:
        os.kill(pid, number)
    except (ProcessLookupError, PermissionError):
        pass


def main(argv: list[str] | None = None) -> int:
    """Runs the guard: a look a minute (`--loop`), or one look (`--once`).

    Args:
        argv: The command line, `sys.argv[1:]` when None.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--loop", action="store_true", help="look once a minute, for ever")
    mode.add_argument("--once", action="store_true", help="look once")
    parser.add_argument("--state", type=Path, help="with --once: the file keeping the overloaded minutes")
    arguments = parser.parse_args(argv)

    log = Log(Path(os.environ.get("MACHINE_GUARD_LOG", Path.home() / "Library" / "Logs" / "machine-guard.log")))
    capacity = float(os.environ.get("MACHINE_GUARD_CAPACITY", os.cpu_count() or 8))
    home = str(Path.home())

    def look(minutes: int) -> int:
        """One look at the machine."""
        return tick(
            minutes,
            load=os.getloadavg()[0],
            capacity=capacity,
            table=read_table,
            started=read_started,
            send=send_signal,
            log=log,
            me=os.getpid(),
            home=home,
        )

    if arguments.once:
        state = arguments.state
        minutes = int(state.read_text().strip() or 0) if state is not None and state.exists() else 0
        minutes = look(minutes)
        if state is not None:
            state.write_text(f"{minutes}\n")
        return 0

    log.write(f"watching: capacity {capacity:g} cores, acts after {SUSTAINED_MINUTES} minutes above it")
    minutes = 0
    while True:
        minutes = look(minutes)
        time.sleep(LOOK_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
