"""Tests for `scripts/heavy.sh`, the machine's budget for heavy runs.

Each test moves the script's home into its own temporary directory
(`HEAVY_HOME`) and fixes every signal it measures — the idle cores, the load,
the memory pressure, the free memory, and the three services that hold a
reserve — so nothing here waits on the machine's real state or touches a run
another session started.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "heavy.sh"

# A Plex answer with two sessions: one transcoding its video, one direct play.
PLEX_TWO_SESSIONS = """<?xml version="1.0" encoding="UTF-8"?>
<MediaContainer size="2">
<Video title="A"><Player state="playing" /><Session id="a" />
<TranscodeSession key="/transcode/sessions/a" videoDecision="transcode" audioDecision="copy" /></Video>
<Video title="B"><Player state="playing" /><Session id="b" /></Video>
</MediaContainer>
"""


def environment(home: Path, capacity: str = "100", **signals: str) -> dict[str, str]:
    """The environment that points the script at a private home and fixes its signals.

    Args:
        home: The script's private home directory.
        capacity: The machine's capacity in cores.
        **signals: Overrides of the fixed signals, by variable name.

    Returns:
        The process environment.
    """
    return {
        **os.environ,
        "HEAVY_HOME": str(home),
        "HEAVY_CAPACITY_CORES": capacity,
        "HEAVY_IDLE_CORES": capacity,
        "HEAVY_LOAD": "0",
        "HEAVY_PRESSURE": "normal",
        "HEAVY_FREE_MB": "100000",
        "HEAVY_PLEX_URL": "http://127.0.0.1:9/never",
        "HEAVY_PARSEC": "0",
        "HEAVY_QBIT": "0",
        **signals,
    }


def running(home: Path, pid: int, who: str, run_class: str, cost: str) -> None:
    """Writes a running entry as an admitted run writes it.

    Args:
        home: The script's home directory.
        pid: The run's process id.
        who: The run's name.
        run_class: Its class.
        cost: Its declared cost in cores.
    """
    entries = home / "running"
    entries.mkdir(parents=True, exist_ok=True)
    (entries / str(pid)).write_text(f"{who}\n{run_class}\n{cost}\n", encoding="utf-8")


def wait_for(condition, seconds: float = 20) -> bool:
    """Polls a condition until it holds or the time runs out.

    Args:
        condition: A callable answering True once the awaited state is reached.
        seconds: How long to wait.

    Returns:
        Whether the condition came to hold.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.2)
    return False


def test_the_start_says_when_and_how_long_it_waited(tmp_path: Path) -> None:
    """B-495: how long a wrapped run waited was unmeasurable afterwards.

    « holding off » was printed once and « starts » with no time, so a log could
    not say whether a run held for a minute or an hour.
    """
    result = subprocess.run(
        ["sh", str(SCRIPT), "tester", "true"],
        env=environment(tmp_path / "home"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    start = next(line for line in result.stderr.splitlines() if "tester starts" in line)
    assert re.match(r"heavy: \d{2}:\d{2}:\d{2} ", start), start
    assert re.search(r"after \d+ s waiting", start), start


def test_two_runs_that_fit_the_budget_run_together(tmp_path: Path) -> None:
    """One lock ran one heavy run at a time, whatever the machine had left.

    With room for both, the second must start while the first still runs.
    """
    home = tmp_path / "home"
    signals = environment(home, capacity="8")
    first = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "test", "first", "sleep", "30"],
        env=signals,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert wait_for(lambda: any((home / "running").glob("*"))), "the first run was never admitted"

        second = subprocess.run(
            ["sh", str(SCRIPT), "--class", "test", "second", "true"],
            env=signals,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert second.returncode == 0, second.stderr
        assert "second starts" in second.stderr
        assert first.poll() is None, "the second run waited for the first to end"
    finally:
        first.kill()
        first.wait()


def test_a_run_the_budget_cannot_hold_waits_and_says_why(tmp_path: Path) -> None:
    """Capacity 4, macOS 1, a test run 2: a second test run (2) does not fit."""
    home = tmp_path / "home"
    holder = subprocess.Popen(["sleep", "60"])
    newcomer = None
    try:
        running(home, holder.pid, "holder", "test", "2")
        newcomer = subprocess.Popen(
            ["sh", str(SCRIPT), "--class", "test", "newcomer", "true"],
            env=environment(home, capacity="4"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(4)
        assert newcomer.poll() is None, "the newcomer ran over a full budget"

        holder.kill()
        holder.wait()
        _, errors = newcomer.communicate(timeout=30)

        assert newcomer.returncode == 0, errors
        holding = next(line for line in errors.splitlines() if "holding off" in line)
        assert "1 of 4 cores free" in holding, holding
        assert "newcomer starts" in errors
    finally:
        for process in (holder, newcomer):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()


def test_two_harness_runs_never_share_the_served_copy(tmp_path: Path) -> None:
    """One served copy per machine: a second harness run waits, whatever the budget."""
    home = tmp_path / "home"
    holder = subprocess.Popen(["sleep", "60"])
    try:
        running(home, holder.pid, "holder", "rule", "1.5")
        newcomer = subprocess.Popen(
            ["sh", str(SCRIPT), "--class", "rule", "newcomer", "true"],
            env=environment(home),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(4)
        assert newcomer.poll() is None, "two harness runs held the served copy at once"
    finally:
        holder.kill()
        holder.wait()
    _, errors = newcomer.communicate(timeout=30)
    assert newcomer.returncode == 0, errors


def test_an_older_waiter_goes_before_a_newer_one(tmp_path: Path) -> None:
    """B-472: a polled `mkdir` gave an old demander no precedence over a new one.

    With the budget full and an older waiter queued, the newcomer must not start
    when room frees while the older waiter is still there, and must start once
    the older one has gone.
    """
    home = tmp_path / "home"
    holder = subprocess.Popen(["sleep", "60"])
    older = subprocess.Popen(["sleep", "60"])
    newcomer = None
    try:
        running(home, holder.pid, "holder", "test", "2")
        queue = home / "queue"
        queue.mkdir(parents=True)
        (queue / f"{1:012d}.{older.pid:08d}").write_text("older\n", encoding="utf-8")
        newcomer = subprocess.Popen(
            ["sh", str(SCRIPT), "--class", "test", "newcomer", "true"],
            env=environment(home, capacity="4"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(2)
        holder.kill()
        holder.wait()
        time.sleep(6)

        assert newcomer.poll() is None, "the newcomer ran before the older waiter"

        older.kill()
        older.wait()
        _, errors = newcomer.communicate(timeout=30)
        assert newcomer.returncode == 0, errors
        assert "newcomer starts" in errors
    finally:
        for process in (holder, older, newcomer):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()


def test_a_reserve_counts_only_while_its_service_serves(tmp_path: Path) -> None:
    """A fixed ceiling reserved Plex's share even with nobody watching.

    Plex holds 2 cores per transcoded session and 0.3 per direct play, Parsec 1
    while a session is open, qBittorrent 0.5 while it downloads, macOS 1 always.
    """
    status = tmp_path / "sessions.xml"
    status.write_text(PLEX_TWO_SESSIONS, encoding="utf-8")

    busy = subprocess.run(
        ["sh", str(SCRIPT), "--budget"],
        env=environment(
            tmp_path / "home", capacity="8", HEAVY_PLEX_URL=status.as_uri(), HEAVY_PARSEC="1", HEAVY_QBIT="1"
        ),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    quiet = subprocess.run(
        ["sh", str(SCRIPT), "--budget"],
        env=environment(tmp_path / "home", capacity="8"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert busy.returncode == 0, busy.stderr
    assert "plex 2.3 (1 transcoded, 1 direct)" in busy.stdout, busy.stdout
    assert "parsec 1" in busy.stdout, busy.stdout
    assert "qbittorrent 0.5" in busy.stdout, busy.stdout
    assert "free 3.2 of 8" in busy.stdout, busy.stdout
    assert "plex 0 (" in quiet.stdout, quiet.stdout
    assert "free 7 of 8" in quiet.stdout, quiet.stdout


def test_the_plex_token_is_never_on_a_command_line_a_file_or_a_log(tmp_path: Path) -> None:
    """The token opens the operator's Plex account to whoever reads it.

    A fake `defaults` hands out a known token and a fake `curl` records its own
    command line: the token must reach curl by its standard input only, and
    appear in nothing the script prints or writes.
    """
    token = "SECRET-PLEX-TOKEN-0123"
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "defaults").write_text(f"#!/bin/sh\necho {token}\n", encoding="utf-8")
    seen = tmp_path / "seen"
    (tools / "curl").write_text(
        f"#!/bin/sh\n"
        f'echo "$@" > {seen}/argv\n'
        f"cat > {seen}/stdin\n"
        'echo "<MediaContainer size=\\"0\\"></MediaContainer>"\n',
        encoding="utf-8",
    )
    for tool in tools.iterdir():
        tool.chmod(0o755)
    seen.mkdir()
    home = tmp_path / "home"
    signals = environment(home, capacity="8", HEAVY_PLEX_URL="http://127.0.0.1:32400/status/sessions")
    signals["PATH"] = f"{tools}:{signals['PATH']}"

    result = subprocess.run(
        ["sh", str(SCRIPT), "--budget"],
        env=signals,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert token in (seen / "stdin").read_text(encoding="utf-8"), "the token never reached curl"
    assert token not in (seen / "argv").read_text(encoding="utf-8")
    assert token not in result.stdout + result.stderr
    written = [path for path in home.rglob("*") if path.is_file() and token in path.read_text(errors="ignore")]
    assert written == []


def test_memory_pressure_above_normal_holds_every_run(tmp_path: Path) -> None:
    """One more run on a machine already compressing memory is one too many."""
    result = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "test", "tester", "true"],
        env=environment(tmp_path / "home", HEAVY_PRESSURE="warn"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(4)
        assert result.poll() is None, "a run started under memory pressure"
    finally:
        result.kill()
        _, errors = result.communicate(timeout=10)
    assert "memory pressure warn" in errors, errors


def test_a_run_under_the_previous_script_is_counted(tmp_path: Path) -> None:
    """A checkout older than the budget still takes the old lock directory.

    The budget must see that run, or it admits a second harness run beside it.
    """
    home = tmp_path / "home"
    holder = subprocess.Popen(["sleep", "60"])
    try:
        legacy = home / "holder"
        legacy.mkdir(parents=True)
        (legacy / "who").write_text("older checkout\n", encoding="utf-8")
        (legacy / "pid").write_text(f"{holder.pid}\n", encoding="utf-8")
        newcomer = subprocess.Popen(
            ["sh", str(SCRIPT), "--class", "rule", "newcomer", "true"],
            env=environment(home),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(4)
        assert newcomer.poll() is None, "a harness run started beside the previous script's"
    finally:
        holder.kill()
        holder.wait()
    _, errors = newcomer.communicate(timeout=30)
    assert newcomer.returncode == 0, errors
    assert "the served copy is older checkout's" in errors
