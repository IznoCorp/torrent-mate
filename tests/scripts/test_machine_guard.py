"""Tests for `scripts/machine_guard.py`, the machine-wide guard against a saturating run.

B-703: an agent can skip `heavy.sh`, and nothing else on the machine watched the
load. Every decision is made by pure functions over a FAKE process table: no test
starts a load, reads the machine's load or signals a real process.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "machine_guard.py"
HOME = "/Users/someone"
CHECKOUT = f"{HOME}/dev/workspaces/PersonalScraper/some-lot"
# A checkout's scratchpad: Claude Code names it after the session's cwd.
SCRATCHPAD = "/private/tmp/claude-501/-Users-someone-dev-workspaces-PersonalScraper-some-lot/0a1b2c/scratchpad"
# The main checkout and its sessions (the orchestrator's, the auditor's): no agent's place.
MAIN_CHECKOUT = f"{HOME}/dev/PersonalScraper"
MAIN_SCRATCHPAD = "/private/tmp/claude-501/-Users-someone-dev-PersonalScraper/9f8e7d/scratchpad"


def bash_wrapper(command: str) -> str:
    """The command line Claude Code's Bash tool gives every command, in every session.

    Args:
        command: The command the session ran.

    Returns:
        The wrapper's argv, as `ps` shows it: it names `/tmp/claude-XXXX-cwd` whatever the cwd.
    """
    return (
        "/bin/zsh -c source /Users/someone/.claude/shell-snapshots/snapshot-zsh-1791232073361-za4zfz.sh"
        " 2>/dev/null || true && setopt NO_EXTENDED_GLOB NO_BARE_GLOB_QUAL 2>/dev/null || true"
        f" && eval '{command}' < /dev/null && pwd -P >| /tmp/claude-78f6-cwd"
    )


def load_guard() -> ModuleType:
    """Imports the guard script as a module.

    Returns:
        The module.
    """
    spec = importlib.util.spec_from_file_location("machine_guard", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["machine_guard"] = module
    spec.loader.exec_module(module)
    return module


guard = load_guard()


def proc(pid: int, ppid: int, cpu: float, command: str, cwd: str = "/", executable: str | None = None) -> object:
    """One row of a fake process table.

    Args:
        pid: The process id.
        ppid: Its parent.
        cpu: Its % CPU.
        command: Its command line.
        cwd: Its working directory.
        executable: What `ps -o comm=` names; the command's first word when None.

    Returns:
        The guard's process record.
    """
    if executable is None:
        executable = command.split(" ")[0]
    return guard.Process(pid=pid, ppid=ppid, cpu=cpu, command=command, cwd=cwd, executable=executable)


def killed(table: list[object], me: int = 9999) -> set[int]:
    """The pids the guard would kill in a table.

    Args:
        table: The fake process table.
        me: The guard's own pid.

    Returns:
        Every pid of every tree chosen.
    """
    return {pid for tree in guard.choose_victims(table, me=me, home=HOME) for pid in tree.pids}


# The incident: a Claude session's shell ran a script from its checkout that
# started burners re-parented to 1 and a browser tree.
INCIDENT = [
    proc(1, 0, 0.0, "/sbin/launchd"),
    proc(100, 1, 3.0, "claude", CHECKOUT),
    proc(101, 100, 0.0, "/bin/zsh -c sh repro.sh", CHECKOUT),
    proc(102, 101, 0.5, "sh repro.sh", CHECKOUT),
    proc(103, 102, 30.0, "node playwright/cli.js run-driver", CHECKOUT),
    proc(104, 103, 90.0, "/Users/someone/Library/Caches/ms-playwright/chromium/Chromium", CHECKOUT),
    proc(105, 104, 60.0, "/Users/someone/Library/Caches/ms-playwright/chromium/Chromium Helper (Renderer)", CHECKOUT),
    proc(200, 1, 99.0, "yes", CHECKOUT),
    proc(201, 1, 98.0, "yes", SCRATCHPAD),
    proc(300, 100, 0.1, "node /opt/homebrew/bin/some-mcp-server", CHECKOUT),
]


def test_the_incident_trees_are_killed_and_the_session_is_not() -> None:
    """B-703: the burners and the browser tree go; the Claude session and its idle MCP stay."""
    victims = killed(INCIDENT)

    assert {101, 102, 103, 104, 105, 200, 201} <= victims
    assert 100 not in victims, "a Claude session was chosen"
    assert 300 not in victims, "an idle tree was chosen"
    assert 1 not in victims


PLEX_TRANSCODER = "/Applications/Plex Media Server.app/Contents/MacOS/Plex Transcoder"
PM2_DAEMON = "PM2 v6.0.8: God Daemon (/Users/someone/.pm2)"


@pytest.mark.parametrize(
    "service",
    [
        proc(400, 1, 300.0, f"{PLEX_TRANSCODER} -i movie.mkv", CHECKOUT, PLEX_TRANSCODER),
        proc(400, 1, 300.0, "/Applications/Parsec.app/Contents/MacOS/parsecd", CHECKOUT),
        proc(400, 1, 300.0, "/Applications/qBittorrent.app/Contents/MacOS/qbittorrent", CHECKOUT),
        proc(400, 1, 300.0, "/System/Library/PrivateFrameworks/SkyLight.framework/Resources/WindowServer", CHECKOUT),
        proc(400, 1, 300.0, "/Users/someone/.local/bin/claude --resume", CHECKOUT),
        proc(400, 1, 300.0, "node /Users/someone/.npm/lib/node_modules/@anthropic-ai/claude-code/cli.js", CHECKOUT),
    ],
    ids=["plex", "parsec", "qbittorrent", "windowserver", "claude", "claude-node"],
)
def test_a_service_is_never_killed_even_from_a_checkout(service: object) -> None:
    """B-703: Plex, Parsec, qBittorrent, WindowServer and Claude itself are never chosen."""
    assert killed([proc(1, 0, 0.0, "/sbin/launchd"), service]) == set()


def test_what_a_pm2_app_runs_is_never_killed() -> None:
    """B-703: a PM2-managed app, and anything it starts, is a service."""
    table = [
        proc(1, 0, 0.0, "/sbin/launchd"),
        proc(500, 1, 1.0, PM2_DAEMON, executable=PM2_DAEMON),
        proc(501, 500, 250.0, "python -m personalscraper serve", CHECKOUT),
        proc(502, 501, 250.0, "ffprobe movie.mkv", CHECKOUT),
    ]

    assert killed(table) == set()


def test_what_plex_starts_is_never_killed() -> None:
    """B-703: a service is known by its executable, and everything under it is its own."""
    table = [
        proc(1, 0, 0.0, "/sbin/launchd"),
        proc(510, 1, 5.0, f"{PLEX_TRANSCODER} -i movie.mkv", CHECKOUT, PLEX_TRANSCODER),
        proc(511, 510, 300.0, "/usr/local/bin/ffmpeg -i movie.mkv", CHECKOUT),
    ]

    assert killed(table) == set()


def test_a_prompt_naming_a_service_does_not_immunise_the_tree() -> None:
    """B-703: a service was sought in every ancestor's argv, and a session's prompt names anything."""
    table = [
        proc(1, 0, 0.0, "/sbin/launchd"),
        proc(520, 1, 3.0, "/opt/homebrew/bin/claude fix the Plex scan and the PM2 v6 God Daemon", CHECKOUT),
        proc(521, 520, 0.0, bash_wrapper("python3 burn.py"), CHECKOUT),
        proc(522, 521, 99.0, "python3 burn.py", CHECKOUT),
    ]

    assert killed(table) == {521, 522}


def test_a_test_path_naming_a_service_does_not_protect_the_run() -> None:
    """B-703: `pytest tests/…/test_qbittorrent_client.py` is an agent's run, not qBittorrent."""
    table = [
        proc(1, 0, 0.0, "/sbin/launchd"),
        proc(530, 1, 600.0, "python -m pytest tests/clients/test_qbittorrent_client.py -k Plex", CHECKOUT),
    ]

    assert killed(table) == {530}


def test_a_heavy_tree_outside_any_checkout_is_left_alone() -> None:
    """B-703: only what runs from an agent checkout or scratchpad is chosen."""
    table = [
        proc(1, 0, 0.0, "/sbin/launchd"),
        proc(600, 1, 400.0, "/usr/bin/some-operator-tool", f"{HOME}/Documents"),
    ]

    assert killed(table) == set()


def test_the_guard_never_chooses_itself_nor_its_parents() -> None:
    """B-703: the guard and what started it are not victims, wherever they run from."""
    table = [
        proc(1, 0, 0.0, "/sbin/launchd"),
        proc(700, 1, 0.0, "sh -c loop", CHECKOUT),
        proc(701, 700, 150.0, "python scripts/machine_guard.py --loop", CHECKOUT),
    ]

    assert killed(table, me=701) == set()


def test_a_checkout_path_in_the_command_does_not_mark_the_tree() -> None:
    """B-703: a place is read on the cwd alone — an argument names anything, a prompt, a path."""
    table = [
        proc(1, 0, 0.0, "/sbin/launchd"),
        proc(800, 1, 150.0, f"python {CHECKOUT}/burn.py --scratch {SCRATCHPAD}", "/"),
    ]

    assert killed(table) == set()


def test_the_orchestrators_bash_wrapper_in_the_main_checkout_is_never_chosen() -> None:
    """B-703: every Bash wrapper's argv names `/tmp/claude-XXXX-cwd`, so every session's command was an agent's.

    The orchestrator's `ci-watch.sh` runs from the main checkout, which is no
    agent's place, nor is its session's scratchpad.
    """
    table = [
        proc(1, 0, 0.0, "/sbin/launchd"),
        proc(900, 1, 3.0, "/opt/homebrew/bin/claude", MAIN_CHECKOUT),
        proc(901, 900, 0.0, bash_wrapper("bash ~/.claude/plugins/orchestrator/scripts/ci-watch.sh 815"), MAIN_CHECKOUT),
        proc(902, 901, 120.0, "bash ~/.claude/plugins/orchestrator/scripts/ci-watch.sh 815", MAIN_CHECKOUT),
        proc(903, 900, 0.0, bash_wrapper("python3 report.py"), MAIN_SCRATCHPAD),
        proc(904, 903, 120.0, "python3 report.py", MAIN_SCRATCHPAD),
    ]

    assert killed(table) == set()


def test_a_burner_under_a_bash_wrapper_in_a_workspace_is_chosen() -> None:
    """B-703: an agent's command runs from its checkout or its scratchpad, and goes, wrapper included."""
    table = [
        proc(1, 0, 0.0, "/sbin/launchd"),
        proc(910, 1, 3.0, "/opt/homebrew/bin/claude", CHECKOUT),
        proc(911, 910, 0.0, bash_wrapper("python3 burn.py"), CHECKOUT),
        proc(912, 911, 99.0, "python3 burn.py", CHECKOUT),
        proc(913, 910, 0.0, bash_wrapper("python3 burn.py"), SCRATCHPAD),
        proc(914, 913, 99.0, "python3 burn.py", SCRATCHPAD),
    ]

    assert killed(table) == {911, 912, 913, 914}


@pytest.mark.parametrize(
    ("loads", "acts"),
    [
        ([9.0, 9.0], False),
        ([9.0, 9.0, 9.0], True),
        ([9.0, 7.0, 9.0], False),
        ([8.0, 8.0, 8.0], False),
    ],
    ids=["two minutes", "three minutes", "interrupted", "at capacity is not above"],
)
def test_the_guard_acts_after_three_minutes_above_capacity(loads: list[float], acts: bool) -> None:
    """B-703: load1 above the capacity for three consecutive minutes, and only then."""
    minutes = 0
    for load in loads:
        minutes = guard.overloaded_minutes(minutes, load, capacity=8)

    assert (minutes >= guard.SUSTAINED_MINUTES) is acts


# The incident, with a Claude session started INSIDE the agent's tree (a
# `claude -p` the script ran) and that session's idle MCP server.
TICK_TABLE = [
    *INCIDENT,
    proc(106, 102, 1.0, "/opt/homebrew/bin/claude -p summarise", CHECKOUT),
    proc(107, 106, 0.0, "node /opt/homebrew/bin/some-mcp-server", CHECKOUT),
]
STOP, TERM, CONT, KILL = guard.signal.SIGSTOP, guard.signal.SIGTERM, guard.signal.SIGCONT, guard.signal.SIGKILL


def test_a_tick_stops_terminates_then_kills_each_chosen_process_and_nothing_else(tmp_path: Path) -> None:
    """B-703: the action stops, terminates, continues then KILLS each process of each tree chosen.

    Nothing is read nor signalled at minutes 1 and 2; a `claude` inside an
    agent's tree, and what it runs, are never signalled; the log keeps the top
    trees and a `GUARD KILLED` line.
    """
    log = tmp_path / "guard.log"
    reads: list[int] = []
    signalled: dict[int, list[int]] = {}

    def table() -> list[object]:
        reads.append(1)
        return TICK_TABLE

    minutes = 0
    for minute in range(1, guard.SUSTAINED_MINUTES + 1):
        minutes = guard.tick(
            minutes,
            load=40.0,
            capacity=8,
            table=table,
            send=lambda pid, number: signalled.setdefault(pid, []).append(number),
            log=guard.Log(log),
            me=9999,
            home=HOME,
            grace_seconds=0,
        )
        if minute < guard.SUSTAINED_MINUTES:
            assert (reads, signalled) == ([], {}), f"the guard acted at minute {minute}"

    text = log.read_text(encoding="utf-8")
    assert minutes == 0, "the count did not restart after the action"
    assert "top trees" in text, text
    assert "GUARD KILLED" in text, text
    assert signalled == {pid: [STOP, TERM, CONT, KILL] for pid in (101, 102, 103, 104, 105, 200, 201)}, signalled


def test_the_guard_runs_from_a_stdlib_copy_declared_in_no_ecosystem() -> None:
    """B-703: the guard's PM2 entry ran from the prod clone, which holds no guard before v1.

    It runs from a copy in `~/.local/bin` (docs/production/maintenance.md), so it
    may import the standard library only, and `ecosystem.config.js` declares it nowhere.
    """
    imported: set[str] = set()
    for node in ast.walk(ast.parse(SCRIPT.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])

    assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)
    assert "machine_guard" not in (ROOT / "ecosystem.config.js").read_text(encoding="utf-8")
