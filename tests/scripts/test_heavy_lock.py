"""Tests for `scripts/heavy.sh`, the machine's budget for heavy runs.

Each test moves the script's home into its own temporary directory
(`HEAVY_HOME`) and fixes every signal it measures — the idle cores, the load,
the memory pressure, the free memory, and the three services that hold a
reserve — so nothing here waits on the machine's real state or touches a run
another session started.

NO REAL LOAD, EVER. The watcher's tests hand it a fake process table
(`HEAVY_PS_TABLE`) that SAYS a run holds browsers or burns cores; the only real
processes started here are `sleep`s.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from pathlib import Path

import pytest

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
        # Never the operator's own log: each test reads its private one.
        "HEAVY_LOG": str(home.parent / "heavy.log"),
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
        held = subprocess.run(
            ["sh", str(SCRIPT), "--held"], env=signals, capture_output=True, text=True, timeout=30, check=False
        )
        # The admitted run's entry was written to `running/*`, the loop variable
        # of the count that ran just before, and the next count removed it.
        assert "first (test, 2 cores)" in held.stdout, held.stdout

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

    Plex holds 1 core per transcoded session and 0.3 per direct play, Parsec 1
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
    assert "plex 1.3 (1 transcoded, 1 direct)" in busy.stdout, busy.stdout
    assert "parsec 1" in busy.stdout, busy.stdout
    assert "qbittorrent 0.5" in busy.stdout, busy.stdout
    assert "free 4.2 of 8" in busy.stdout, busy.stdout
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


def sessions(*transcodes: str, direct: int = 0) -> str:
    """A fake `/status/sessions` answer: one session per transcode, plus direct plays.

    Args:
        *transcodes: The attributes of each session's `<TranscodeSession>`.
        direct: How many sessions play directly.

    Returns:
        The XML Plex would answer.
    """
    videos = [
        f'<Video title="T{index}"><Player state="playing" />'
        f'<TranscodeSession key="/transcode/sessions/{index}" videoDecision="transcode" {attributes} /></Video>'
        for index, attributes in enumerate(transcodes)
    ]
    videos += [f'<Video title="D{index}"><Player state="playing" /></Video>' for index in range(direct)]
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<MediaContainer size="{len(videos)}">\n'
        + "\n".join(videos)
        + "\n</MediaContainer>\n"
    )


# Sessions and speeds → the decision. `suspended` is the run heavy.sh already
# stopped, `latest` the most recent of the runs it admitted that still run.
PLEX_DECISIONS = [
    ("no session", "", "-", "-", "admit"),
    ("a direct play only", sessions(direct=2), "-", "222", "admit"),
    ("a transcode ahead", sessions('speed="2.4" throttled="0"'), "-", "222", "admit"),
    ("a transcode exactly at 1.5", sessions('speed="1.5" throttled="0"'), "-", "222", "admit"),
    ("a transcode under 1.5", sessions('speed="1.3" throttled="0"'), "-", "222", "hold"),
    ("a transcode under 1.5 but braking itself", sessions('speed="1.3" throttled="1"'), "-", "222", "admit"),
    ("a transcode under 1.1", sessions('speed="0.9" throttled="0"'), "-", "222", "suspend 222"),
    ("a transcode under 1.1 and no run of ours", sessions('speed="0.9" throttled="0"'), "-", "-", "hold"),
    ("a transcode under 1.1 but braking itself", sessions('speed="0.9" throttled="1"'), "-", "222", "admit"),
    ("any transcode under 1.5 holds", sessions('speed="3.0"', 'speed="1.2"'), "-", "222", "hold"),
    ("a finished transcode has no speed to keep", sessions('speed="0.0" complete="1"'), "-", "222", "admit"),
    ("a transcode with no speed yet", sessions('throttled="0"'), "-", "222", "admit"),
    ("suspended, still under 1.1", sessions('speed="0.8"'), "111", "222", "hold"),
    ("suspended, back over 1.1 but not 1.5", sessions('speed="1.4"'), "111", "222", "hold"),
    ("suspended, exactly 1.5 is not above", sessions('speed="1.5"'), "111", "222", "hold"),
    ("suspended, above 1.5", sessions('speed="1.6"'), "111", "222", "resume 111"),
    ("suspended, braking itself", sessions('speed="0.8" throttled="1"'), "111", "-", "resume 111"),
    ("suspended, the session ended", "", "111", "-", "resume 111"),
]


@pytest.mark.parametrize(
    ("status", "suspended", "latest", "decision"),
    [case[1:] for case in PLEX_DECISIONS],
    ids=[case[0] for case in PLEX_DECISIONS],
)
def test_plex_decision_follows_the_transcode_speed(status: str, suspended: str, latest: str, decision: str) -> None:
    """A calibrated Plex reserve needed a measurement nobody has time for.

    Plex says itself whether it keeps up: a transcode's `speed` under 1.5 holds
    new runs, under 1.1 stops the most recent of heavy.sh's own runs until the
    speed is back above 1.5; `throttled="1"` means Plex is ahead and brakes.
    """
    result = subprocess.run(
        ["sh", str(SCRIPT), "--plex-decision", suspended, latest],
        input=status,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == decision


def process_state(pid: int) -> str:
    """The process's state letter as `ps` prints it (T when stopped).

    Args:
        pid: The process id.

    Returns:
        The state, empty once the process is gone.
    """
    return subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
    ).stdout.strip()


def test_a_slow_transcode_suspends_the_latest_run_and_resumes_it(tmp_path: Path) -> None:
    """Under 1.1 the most recent run of heavy.sh's own is stopped, above 1.5 continued.

    A process the script did not launch — here a `sleep` written as a newer
    admitted run — is named by the decision but touched by no one.
    """
    home = tmp_path / "home"
    status = tmp_path / "sessions.xml"
    status.write_text(sessions('speed="2.0"'), encoding="utf-8")
    pid_file = tmp_path / "child.pid"
    child_script = f"echo $$ > {pid_file}; exec sleep 60"
    stranger = None
    run = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "test", "ours", "sh", "-c", child_script],
        env=environment(home, capacity="8", HEAVY_PLEX_URL=status.as_uri(), HEAVY_WATCH_SECONDS="1"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert wait_for(pid_file.exists), "the run never started"
        child = int(pid_file.read_text().strip())

        status.write_text(sessions('speed="0.9"'), encoding="utf-8")
        assert wait_for(lambda: process_state(child).startswith("T")), "a slow transcode left our run running"

        status.write_text(sessions('speed="1.3"'), encoding="utf-8")
        time.sleep(3)
        assert process_state(child).startswith("T"), "the run resumed before the speed was back above 1.5"

        status.write_text(sessions('speed="1.6"'), encoding="utf-8")
        assert wait_for(lambda: not process_state(child).startswith("T")), "the run was never resumed"

        stranger = subprocess.Popen(["sleep", "60"])
        running(home, stranger.pid, "stranger", "test", "2")
        (home / "running" / str(stranger.pid)).write_text(f"stranger\ntest\n2\n{int(time.time()) + 100}\n")
        status.write_text(sessions('speed="0.9"'), encoding="utf-8")
        time.sleep(4)
        assert not process_state(stranger.pid).startswith("T"), "heavy.sh stopped a process it did not launch"
        assert not process_state(child).startswith("T"), "the older run was stopped instead of the latest"
    finally:
        run.send_signal(signal.SIGTERM)
        _, errors = run.communicate(timeout=30)
        if stranger is not None:
            stranger.kill()
            stranger.wait()
    assert "suspending ours" in errors, errors
    assert "resuming ours" in errors, errors


def test_a_slow_transcode_holds_new_runs(tmp_path: Path) -> None:
    """While a transcode runs under 1.5, no new heavy run is admitted."""
    status = tmp_path / "sessions.xml"
    status.write_text(sessions('speed="1.3"'), encoding="utf-8")
    run = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "test", "newcomer", "true"],
        env=environment(tmp_path / "home", capacity="8", HEAVY_PLEX_URL=status.as_uri()),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(4)
        assert run.poll() is None, "a run started over a transcode that falls behind"
        status.write_text(sessions('speed="1.3" throttled="1"'), encoding="utf-8")
        _, errors = run.communicate(timeout=30)
    finally:
        if run.poll() is None:
            run.kill()
            run.wait()
    assert run.returncode == 0, errors
    assert "Plex transcodes at 1.3" in errors, errors


# A pid no machine hands out (Linux's ceiling is 4 194 304, macOS's 99 999):
# the fake table's processes can never name a real one.
FAKE_PID = 5_000_000


def alive(pid: int) -> bool:
    """Whether a process still exists (a zombie counts as gone).

    Args:
        pid: The process id.

    Returns:
        True while the process runs or is stopped.
    """
    state = process_state(pid)
    return bool(state) and not state.startswith("Z")


def escaped_sleep(pid_file: Path) -> str:
    """A command whose grandchild leaves the run's process group and is re-parented to 1.

    The intermediate shell exits at once (a double fork) and the `sleep` calls
    `setsid` first, as Playwright starts its browsers (`detached`): a signal to
    the run's group never reaches it.

    Args:
        pid_file: Where the escaped `sleep` writes its pid.

    Returns:
        The shell command.
    """
    escape = "perl -MPOSIX -e 'POSIX::setsid(); print \"$$\\n\"; exec q(sleep), 300'"
    return f"({escape} > {pid_file} 2>/dev/null </dev/null &)"


def test_a_descendant_that_left_the_group_dies_with_the_run(tmp_path: Path) -> None:
    """B-700: heavy.sh signalled its run's process group alone.

    A descendant that left the group — a double fork plus `setsid`, the way
    Playwright detaches its browsers and the way the incident's CPU burners
    re-parented to 1 — outlived the run.
    """
    pid_file = tmp_path / "escaped.pid"
    escaped = 0
    try:
        result = subprocess.run(
            ["sh", str(SCRIPT), "--class", "test", "escaper", "sh", "-c", f"{escaped_sleep(pid_file)}; sleep 1"],
            env=environment(tmp_path / "home"),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert wait_for(lambda: pid_file.exists() and pid_file.read_text().strip() != ""), result.stderr
        escaped = int(pid_file.read_text().strip())
        assert wait_for(lambda: not alive(escaped), seconds=10), "the escaped sleep outlived the run"
    finally:
        if escaped and alive(escaped):
            os.kill(escaped, signal.SIGKILL)


def test_a_descendant_that_left_the_group_dies_when_the_run_is_interrupted(tmp_path: Path) -> None:
    """B-700: an interrupted run left its escaped descendants behind."""
    pid_file = tmp_path / "escaped.pid"
    escaped = 0
    run = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "test", "escaper", "sh", "-c", f"{escaped_sleep(pid_file)}; sleep 60"],
        env=environment(tmp_path / "home"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert wait_for(lambda: pid_file.exists() and pid_file.read_text().strip() != ""), "the run never started"
        escaped = int(pid_file.read_text().strip())
        run.send_signal(signal.SIGTERM)
        run.communicate(timeout=30)
        assert wait_for(lambda: not alive(escaped), seconds=10), "the escaped sleep outlived the interrupted run"
    finally:
        if run.poll() is None:
            run.kill()
            run.wait()
        if escaped and alive(escaped):
            os.kill(escaped, signal.SIGKILL)


def fake_table(path: Path, root: int, rows: list[tuple[int, int, float, str]]) -> None:
    """Writes the process table the watcher reads in place of `ps`.

    Columns as `ps -Ao pid=,ppid=,pgid=,pcpu=,comm=` prints them; the run's own
    process heads the table, at no CPU.

    Args:
        path: The table's file.
        root: The run's real process, the group's leader.
        rows: Its fake descendants, as (pid, parent, % CPU, command).
    """
    lines = [f"{root} 1 {root} 0.0 sh"]
    lines += [f"{pid} {parent} {root} {cpu} {command}" for pid, parent, cpu, command in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def watched_run(tmp_path: Path, run_class: str, **signals: str) -> tuple[subprocess.Popen[str], int, Path]:
    """Starts a `sleep` run under heavy.sh with a fast watcher reading a fake table.

    Args:
        tmp_path: The test's directory.
        run_class: The run's class.
        **signals: More variables for the run's environment.

    Returns:
        The heavy.sh process, its run's pid and the fake table's path.
    """
    pid_file = tmp_path / "child.pid"
    table = tmp_path / "ps.txt"
    run = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", run_class, "watched", "sh", "-c", f"echo $$ > {pid_file}; exec sleep 60"],
        env=environment(
            tmp_path / "home",
            capacity="8",
            HEAVY_PS_TABLE=str(table),
            HEAVY_GUARD_SECONDS="1",
            HEAVY_GUARD_STRIKES="2",
            **signals,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert wait_for(lambda: pid_file.exists() and pid_file.read_text().strip() != ""), "the run never started"
    return run, int(pid_file.read_text().strip()), table


def test_a_run_holding_more_browsers_than_its_class_is_stopped_then_killed(tmp_path: Path) -> None:
    """B-701: heavy.sh admitted ONE browser run, then never looked again.

    The incident's run started eight Playwright browsers under `--class browser`;
    the watcher must see them and stop the run, then kill it.
    """
    run, child, table = watched_run(tmp_path, "browser")
    try:
        browsers = [(FAKE_PID + index, child, 5.0, "/opt/ms-playwright/chromium/Chromium") for index in range(8)]
        fake_table(table, child, browsers)
        _, errors = run.communicate(timeout=30)
    finally:
        if run.poll() is None:
            run.kill()
            run.wait()
            # The run never reached its verdict: its sleep is not left behind.
            if alive(child):
                os.kill(child, signal.SIGKILL)
    assert run.returncode == 75, errors
    assert wait_for(lambda: not alive(child), seconds=10), "the run outlived its verdict"
    assert "8 browsers" in errors, errors
    log = (tmp_path / "heavy.log").read_text(encoding="utf-8")
    assert log.index("STOPPED") < log.index("KILLED"), log


# A real Chrome for Testing as `ps -o comm=` shows it: the main executable, two
# crashpad handlers re-parented to 1 (members through the run's tag), and its
# helpers — renderer, GPU, network — under the main.
CHROME_APP = "/Users/someone/Library/Caches/ms-playwright/chromium-1187/chrome-mac-arm64/Google Chrome for Testing.app"
CHROME_FRAMEWORK = f"{CHROME_APP}/Contents/Frameworks/Google Chrome for Testing Framework.framework/Versions/140"


def real_chrome(first: int, parent: int) -> list[tuple[int, int, float, str]]:
    """One real Chrome for Testing's processes, as a fake table's rows.

    Args:
        first: The main executable's pid; the others follow it.
        parent: The main executable's parent.

    Returns:
        The rows: the main, two crashpad handlers at ppid 1, three helpers under the main.
    """
    helper = f"{CHROME_FRAMEWORK}/Helpers/Google Chrome for Testing Helper"
    return [
        (first, parent, 20.0, f"{CHROME_APP}/Contents/MacOS/Google Chrome for Testing"),
        (first + 1, 1, 0.0, f"{CHROME_FRAMEWORK}/Helpers/chrome_crashpad_handler"),
        (first + 2, 1, 0.0, f"{CHROME_FRAMEWORK}/Helpers/chrome_crashpad_handler"),
        (first + 3, first, 10.0, f"{helper} (Renderer).app/Contents/MacOS/Google Chrome for Testing Helper (Renderer)"),
        (first + 4, first, 5.0, f"{helper} (GPU).app/Contents/MacOS/Google Chrome for Testing Helper (GPU)"),
        (first + 5, first, 1.0, f"{helper}.app/Contents/MacOS/Google Chrome for Testing Helper"),
    ]


@pytest.mark.parametrize("chromes", [1, 4], ids=["one chrome", "four chromes"])
def test_a_browser_is_counted_once_never_its_crashpad_nor_its_helpers(tmp_path: Path, chromes: int) -> None:
    """B-701: a real Chrome counted as three browsers, its two crashpad handlers at ppid 1 counted too.

    Four Chromes within the class's cap of six were twelve, and the run was killed.
    The cap is forced to 0 here so the watcher says the count it made.
    """
    run, child, table = watched_run(tmp_path, "browser", HEAVY_MAX_BROWSERS="0")
    try:
        rows = [row for index in range(chromes) for row in real_chrome(FAKE_PID + 10 * index, child)]
        fake_table(table, child, rows)
        _, errors = run.communicate(timeout=30)
    finally:
        if run.poll() is None:
            run.kill()
            run.wait()
            if alive(child):
                os.kill(child, signal.SIGKILL)
    assert f"— {chromes} browsers, class browser" in errors, errors


def test_a_run_burning_far_more_than_its_cost_is_stopped_then_killed(tmp_path: Path) -> None:
    """B-701: a run declared at 2 cores that burns nine is beyond its class."""
    run, child, table = watched_run(tmp_path, "test")
    try:
        fake_table(table, child, [(FAKE_PID + index, 1, 100.0, "yes") for index in range(9)])
        _, errors = run.communicate(timeout=30)
    finally:
        if run.poll() is None:
            run.kill()
            run.wait()
            # The run never reached its verdict: its sleep is not left behind.
            if alive(child):
                os.kill(child, signal.SIGKILL)
    assert run.returncode == 75, errors
    assert wait_for(lambda: not alive(child), seconds=10), "the run outlived its verdict"
    assert "900% CPU" in errors, errors


def test_a_run_within_its_class_is_left_to_its_end(tmp_path: Path) -> None:
    """The watcher touches nothing while a run holds what its class allows."""
    run, child, table = watched_run(tmp_path, "browser")
    try:
        fake_table(table, child, [(FAKE_PID, child, 120.0, "/opt/ms-playwright/chromium/Chromium")])
        time.sleep(4)
        assert alive(child), "a run within its class was stopped"
        assert not process_state(child).startswith("T"), "a run within its class was suspended"
    finally:
        run.send_signal(signal.SIGTERM)
        _, errors = run.communicate(timeout=30)
    assert "STOPPED" not in errors, errors


def test_a_reused_pids_children_are_not_the_runs(tmp_path: Path) -> None:
    """B-700: the watcher took every RECORDED pid as the run's, alive or not.

    A recorded pid that died and was handed to a stranger pulled the stranger's
    children into the run: weighed, then reaped. Here the recorded pid is a live
    `sleep` the run never started, recorded under a start time it does not have;
    the fake table gives it nine burners, which are not the run's.
    """
    stranger = subprocess.Popen(["sleep", "60"])
    run, child, table = watched_run(tmp_path, "test")
    try:
        tree = tmp_path / "home" / "tree" / str(run.pid)
        assert wait_for(tree.exists), "the run's tree file was never made"
        with tree.open("a", encoding="utf-8") as handle:
            handle.write(f"{stranger.pid} Mon Jan 1 00:00:00 2024\n")
        # The stranger leads its own group: only the recorded pid could pull it in.
        rows = [f"{child} 1 {child} 0.0 sh", f"{stranger.pid} 1 {stranger.pid} 0.0 sleep"]
        rows += [f"{FAKE_PID + index} {stranger.pid} {stranger.pid} 100.0 yes" for index in range(9)]
        table.write_text("\n".join(rows) + "\n", encoding="utf-8")
        time.sleep(4)
        assert run.poll() is None, "a stranger's children were weighed as the run's"
        assert alive(stranger.pid), "a stranger was reaped as the run's"
    finally:
        run.send_signal(signal.SIGTERM)
        _, errors = run.communicate(timeout=30)
        stranger.kill()
        stranger.wait()
    assert "beyond its class" not in errors, errors


def test_every_line_also_goes_to_the_persistent_log(tmp_path: Path) -> None:
    """B-702: heavy.sh logged to its caller's stderr alone, so an audit read nothing."""
    result = subprocess.run(
        ["sh", str(SCRIPT), "--class", "test", "logged", "true"],
        env=environment(tmp_path / "home"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    log = (tmp_path / "heavy.log").read_text(encoding="utf-8").splitlines()
    assert any("wants 2 cores" in line for line in log), log
    assert any("logged starts" in line for line in log), log
    assert any("logged done (exit 0)" in line for line in log), log
    assert all(re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} heavy\[\d+\] ", line) for line in log), log


def test_the_persistent_log_rotates_by_size(tmp_path: Path) -> None:
    """B-702: the persistent log is kept to a size, its previous part beside it."""
    log = tmp_path / "heavy.log"
    log.write_text("old line\n" * 200, encoding="utf-8")
    result = subprocess.run(
        ["sh", str(SCRIPT), "--class", "test", "rotated", "true"],
        env=environment(tmp_path / "home", HEAVY_LOG_MAX_BYTES="1000"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "heavy.log.1").read_text(encoding="utf-8").startswith("old line"), "the old part was not kept"
    assert "old line" not in log.read_text(encoding="utf-8")
    assert "rotated done" in log.read_text(encoding="utf-8")
