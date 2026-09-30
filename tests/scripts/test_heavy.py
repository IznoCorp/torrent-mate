"""The machine-wide lock for heavy runs, exercised on its own paths.

WHY THESE EXIST. `scripts/heavy.sh` is the wrapper the frontend steward's office
is REQUIRED to put in front of every build, browser and parallel test run, after
the operator twice had to intervene over a machine brought to its knees. A rule
that mandatory has to be measured rather than described, and the office once
published four figures about this script's behaviour taken on throwaway copies
that no longer existed the next day — a number with no command behind it, which
is the defect the office's own step 6 is written against.

Every test drives the script through `HEAVY_LOCK`, so none of them touches the
lock the machine is actually using while they run.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "heavy.sh"

# The real thresholds wait for a quiet machine, which a test must never do: it
# would pass or fail on what else is running. These say « start at once ».
PERMISSIVE = {"HEAVY_FREE_FLOOR_MB": "1", "HEAVY_LOAD_CEILING": "9999"}


def run(lock: Path, *command: str, timeout: float = 30, **environment: str):
    """Run the script with its lock moved and its thresholds made permissive."""
    env = {**os.environ, "HEAVY_LOCK": str(lock), **PERMISSIVE, **environment}
    return subprocess.run(
        ["sh", str(SCRIPT), "tester", *command],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def test_the_script_is_syntactically_sound() -> None:
    """A wrapper nobody can parse stops every run that depends on it."""
    assert subprocess.run(["sh", "-n", str(SCRIPT)]).returncode == 0


def test_a_command_runs_and_its_exit_code_survives(tmp_path: Path) -> None:
    """The wrapper is transparent: what it wraps decides the verdict."""
    assert run(tmp_path / "holder", "true").returncode == 0
    assert run(tmp_path / "holder", "sh", "-c", "exit 7").returncode == 7


def test_the_lock_is_released_afterwards(tmp_path: Path) -> None:
    """A lock left behind is the stall the next run cannot explain."""
    lock = tmp_path / "holder"
    run(lock, "true")
    assert not lock.exists()


def test_a_missing_parent_does_not_hang(tmp_path: Path) -> None:
    """THE DEFECT THIS FILE WAS WRITTEN FOR.

    `/private/tmp` is purged at boot and this host reboots weekly, so the lock's
    parent is absent on the first heavy run of every week. A bare `mkdir` failed
    `ENOENT` on every pass while the stale-lock breaker tested a path that did
    not exist, and the script span forever announcing a holder nobody held.
    """
    started = time.monotonic()
    result = run(tmp_path / "absent" / "parent" / "holder", "true", timeout=20)
    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started < 15, "the wrapper hung on an absent parent"


def test_an_unusable_parent_runs_unlocked_rather_than_waiting(tmp_path: Path) -> None:
    """A lock that cannot be taken must not become a lock that never ends.

    Another user may own the lock's home, and the sticky bit on `/private/tmp`
    stops us deleting what they left. Refusing to run would stop the office; the
    honest fallback is to run and say so.
    """
    home = tmp_path / "theirs"
    home.mkdir(mode=0o500)
    try:
        result = run(home / "holder", "sh", "-c", "echo ran", timeout=20)
        assert "ran" in result.stdout
        assert "running unlocked" in result.stderr
    finally:
        home.chmod(0o700)


def test_the_lock_excludes_a_second_holder(tmp_path: Path) -> None:
    """Two sessions each believing they are alone is the whole reason it exists."""
    lock = tmp_path / "holder"
    env = {**os.environ, "HEAVY_LOCK": str(lock), **PERMISSIVE}
    first = subprocess.Popen(
        ["sh", str(SCRIPT), "first", "sleep", "6"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        time.sleep(1.5)
        started = time.monotonic()
        second = run(lock, "true", timeout=40)
        waited = time.monotonic() - started
        assert second.returncode == 0
        assert waited >= 2, "the second run did not wait for the first"
        assert waited < 20, "the second run waited far past the first's end"
    finally:
        first.wait(timeout=30)


def test_an_instant_command_is_not_taxed(tmp_path: Path) -> None:
    """A wrapper that made every quick command wait is a wrapper someone bypasses.

    The watchdog samples memory every fifteen seconds; it must still notice the
    child finishing within about a second, or the tax gets the rule dropped.
    """
    started = time.monotonic()
    run(tmp_path / "holder", "true")
    assert time.monotonic() - started < 6


def test_a_short_command_takes_its_own_time_and_no_more(tmp_path: Path) -> None:
    """The wrapper adds a second, not the watchdog's sampling interval."""
    started = time.monotonic()
    run(tmp_path / "holder", "sleep", "3")
    elapsed = time.monotonic() - started
    assert 3 <= elapsed < 9, f"a three-second command took {elapsed:.1f}s"


def test_a_stale_lock_is_broken_rather_than_waited_on(tmp_path: Path) -> None:
    """A session that dies holding the lock must not stop the machine for good."""
    lock = tmp_path / "holder"
    lock.mkdir()
    (lock / "who").write_text("a session that died\n")
    old = time.time() - 60 * 60
    os.utime(lock, (old, old))
    result = run(lock, "sh", "-c", "echo ran", timeout=30)
    assert "ran" in result.stdout
    assert "breaking a stale lock" in result.stderr


def test_an_interrupted_run_releases_the_lock(tmp_path: Path) -> None:
    """Released on exit, on an interrupt and on a kill — or the next run stalls."""
    lock = tmp_path / "holder"
    env = {**os.environ, "HEAVY_LOCK": str(lock), **PERMISSIVE}
    held = subprocess.Popen(
        ["sh", str(SCRIPT), "interrupted", "sleep", "30"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    time.sleep(2)
    assert lock.exists(), "the lock was never taken"
    held.terminate()
    held.wait(timeout=20)
    for _ in range(40):
        if not lock.exists():
            break
        time.sleep(0.25)
    assert not lock.exists(), "an interrupted run kept the lock"


def test_held_names_the_holder_and_says_free_otherwise(tmp_path: Path) -> None:
    """`--held` reads `who`, which only a holder writes — never the directory as a file.

    B-326: `cat .../holder` reads a directory, fails, and prints nothing whether the
    lock is held or free, so two sessions read « free » from it on one night, one
    of them over a lock that WAS held. The probe has to read a fact only a holder
    produces, and exit differently on each answer so a script can branch on it.
    """
    lock = tmp_path / "holder"
    env = {**os.environ, "HEAVY_LOCK": str(lock), **PERMISSIVE}
    free = subprocess.run(
        ["sh", str(SCRIPT), "--held"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert free.returncode == 1 and free.stdout.strip() == "free"
    holder = subprocess.Popen(
        ["sh", str(SCRIPT), "the-holder", "sleep", "4"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        deadline = time.time() + 5
        while not (lock / "who").exists() and time.time() < deadline:
            time.sleep(0.05)
        held = subprocess.run(
            ["sh", str(SCRIPT), "--held"],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert held.returncode == 0 and held.stdout.strip() == "the-holder"
        # And the probe that cannot fail, for the record: it reads nothing either way.
        blind = subprocess.run(["sh", "-c", f'cat "{lock}" 2>/dev/null'], capture_output=True, text=True)
        assert blind.stdout == ""
    finally:
        holder.wait(timeout=15)


@pytest.mark.parametrize("knob", ["HEAVY_FREE_FLOOR_MB", "HEAVY_LOAD_CEILING"])
def test_the_thresholds_are_readable_from_the_environment(knob: str) -> None:
    """The margin is the point, so the numbers must be visible and testable.

    A threshold that can only be changed by editing the file is a threshold no
    test can exercise, and an untested threshold is the one that hangs.
    """
    assert f"{knob}:-" in SCRIPT.read_text(), f"{knob} is not readable from the environment"


def test_the_watchdog_signals_the_whole_process_group(tmp_path: Path) -> None:
    """The runs this stops fork browsers that outlive a signal to their shell.

    Read rather than executed: provoking a real memory collapse to watch the
    rescue is the one measurement the machine discipline forbids outright.
    """
    body = SCRIPT.read_text()
    assert 'kill -TERM -"$child"' in body, "the watchdog signals the child alone"
    assert 'kill -KILL -"$child"' in body, "the watchdog's last resort spares the group"
    assert "set -m" in body, "without job control the child leads no group to signal"


def test_a_machine_that_reports_no_memory_runs_rather_than_waits(
    tmp_path: Path,
) -> None:
    """THE SECOND DEFECT THIS FILE CAUGHT, and it is the first one's shape.

    `vm_stat` is Darwin's and the repository's runners are Linux, so the first
    version could not read free memory there — and WAITED for a number it could
    never obtain, hanging every job that touched it. A gate that cannot measure
    must let the run through and say so; only a gate that measures may hold one.
    """
    empty = tmp_path / "bin"
    empty.mkdir()
    for name in (
        "vm_stat",
        "sh",
        "awk",
        "uptime",
        "sleep",
        "mkdir",
        "rm",
        "cat",
        "dirname",
        "find",
    ):
        pass
    started = time.monotonic()
    result = subprocess.run(
        ["sh", str(SCRIPT), "tester", "sh", "-c", "echo ran"],
        capture_output=True,
        text=True,
        timeout=25,
        env={
            **os.environ,
            "HEAVY_LOCK": str(tmp_path / "holder"),
            "HEAVY_FREE_FLOOR_MB": "1",
            "HEAVY_LOAD_CEILING": "9999",
            "PATH": f"{empty}:{os.environ['PATH']}",
        },
    )
    assert "ran" in result.stdout
    assert time.monotonic() - started < 20


def test_the_memory_reader_covers_both_operating_systems() -> None:
    """Darwin answers through `vm_stat`, Linux through `/proc/meminfo`.

    Read rather than executed: a test cannot become the other operating system,
    and the branch that matters is the one this machine never takes.
    """
    body = SCRIPT.read_text()
    assert "command -v vm_stat" in body, "the Darwin reader is not guarded by a probe"
    assert "/proc/meminfo" in body, "no Linux reader — CI cannot run what it must enforce"
    assert 'if [ -z "$free" ] || [ -z "$load" ]' in body, "an unmeasurable machine still waits"


# A `vm_stat` reading taken on this machine while a browser-class gate was held
# off for fourteen minutes: free and inactive make 3 868 MB, the speculative
# pages 1 837 MB more.
VM_STAT_WITH_SPECULATIVE_PAGES = """\
Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                                    6648.
Pages active:                                400000.
Pages inactive:                              240956.
Pages speculative:                           117584.
Pages wired down:                            274432.
"""


def test_the_speculative_pages_macos_reclaims_first_are_counted_free(
    tmp_path: Path,
) -> None:
    """THE SPECULATIVE PAGES ARE FREE MEMORY, and the Darwin reader left them out.

    They are the file cache macOS pre-fetches and hands back before anything
    else, which is what Linux's `MemAvailable` already counts on the other
    branch. Summing only free and inactive held an a·10 gate for nine minutes
    and an a·13 gate for fourteen over 5.7 GB the machine could have given.
    The reading is the one `vm_stat` printed then, served by a stand-in.
    """
    stand_in = tmp_path / "bin"
    stand_in.mkdir()
    reader = stand_in / "vm_stat"
    reader.write_text(f"#!/bin/sh\ncat <<'READING'\n{VM_STAT_WITH_SPECULATIVE_PAGES}READING\n")
    reader.chmod(0o755)
    result = run(tmp_path / "holder", "true", PATH=f"{stand_in}:{os.environ['PATH']}")
    assert result.returncode == 0, result.stderr
    # (6 648 + 240 956 + 117 584) pages x 16 384 bytes = 5 706 MB.
    assert "starts (5706MB free" in result.stderr, result.stderr


# ── The readiness floor, read from the run's class (B-386) ───────────────────
# There was ONE floor for every run: a single rule replayed against the served
# copy waited behind the same 4 GB and load 6 a two-browser suite needs, and a
# wave asked to lower the floor by environment to get a `make check` started —
# the bypass the floor exists to forbid. The class carries the floor now, and
# under a named class the environment may only RAISE it.
#
# These drive the refusal path, which answers before any waiting, so no test
# here passes or fails on how much room the machine happens to have.

CLASS_FLOORS = {"browser": 4096, "test": 3072, "rule": 2560}


def run_under_class(lock: Path, name: str, *command: str, timeout: float = 30, **environment: str):
    """Run the script under a named class, with nothing made permissive.

    Args:
        lock: The lock this run takes, so the machine's own is untouched.
        name: The class name passed as `--class`.
        command: The command to wrap.
        timeout: Seconds before the subprocess is killed.
        environment: Extra environment, verbatim.

    Returns:
        The completed process.
    """
    env = {**os.environ, "HEAVY_LOCK": str(lock)}
    env.pop("HEAVY_FREE_FLOOR_MB", None)
    env.pop("HEAVY_LOAD_CEILING", None)
    env.update(environment)
    return subprocess.run(
        ["sh", str(SCRIPT), "--class", name, "tester", *command],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


@pytest.mark.parametrize(("name", "floor"), sorted(CLASS_FLOORS.items()))
def test_a_class_refuses_a_floor_the_environment_tries_to_lower(tmp_path: Path, name: str, floor: int) -> None:
    """Each class names its own floor, and the environment cannot talk it down."""
    result = run_under_class(
        tmp_path / "holder",
        name,
        "true",
        HEAVY_FREE_FLOOR_MB=str(floor - 1),
    )
    assert result.returncode == 64, result.stderr
    assert f"class {name} wants {floor}MB free" in result.stderr, result.stderr


@pytest.mark.parametrize("name", sorted(CLASS_FLOORS))
def test_a_class_refuses_a_load_ceiling_the_environment_tries_to_raise(tmp_path: Path, name: str) -> None:
    """The other half of the same statement: a class's load ceiling only lowers."""
    result = run_under_class(
        tmp_path / "holder",
        name,
        "true",
        HEAVY_FREE_FLOOR_MB=str(CLASS_FLOORS[name]),
        HEAVY_LOAD_CEILING="9999",
    )
    assert result.returncode == 64, result.stderr
    assert "may only lower a class's ceiling" in result.stderr, result.stderr


def test_an_unknown_class_is_refused_rather_than_read_as_none(tmp_path: Path) -> None:
    """A misspelt class must not silently become the historical floor."""
    result = run_under_class(tmp_path / "holder", "browsers", "true")
    assert result.returncode == 64, result.stderr
    assert "unknown class 'browsers'" in result.stderr, result.stderr


def test_no_class_keeps_the_historical_floor_and_its_bypass(tmp_path: Path) -> None:
    """Every invocation written before B-386 must still work, untouched.

    A run with no class keeps 4 096 MB and keeps the environment override that
    goes with it — which is what the whole suite above, and every wrapped
    command in every brief, is written against.
    """
    result = run(tmp_path / "holder", "sh", "-c", "echo ran")
    assert result.returncode == 0, result.stderr
    assert "ran" in result.stdout
    assert "(class none)" in result.stderr, result.stderr
    assert "wants 1MB free" in result.stderr, result.stderr


def test_the_class_floors_are_written_down_with_their_arithmetic() -> None:
    """The numbers and the reasoning live together, or the next reader guesses.

    Read rather than executed: a test cannot wait for 4 GB of free memory to
    observe the browser class's floor without passing or failing on whatever
    else the machine is doing. The refusals above execute each number; this
    holds that the number is not a bare constant, and that the watchdog's hard
    floor did not move with the classes.
    """
    body = SCRIPT.read_text()
    for name, floor in CLASS_FLOORS.items():
        assert re.search(rf"^\s*{name}\)\s+CLASS_FLOOR_MB={floor};", body, re.MULTILINE), (
            f"the {name} class does not carry the floor {floor}"
        )
    assert "1.1 GB" in body, "the browser group's cost is not written beside the numbers"
    assert "HARD_FLOOR_MB=${HEAVY_HARD_FLOOR_MB:-2048}" in body, "the hard floor moved with the class"


def test_the_holder_writes_its_pid_beside_its_name(tmp_path: Path) -> None:
    """The breaker asks the pid, so the holder must leave it — alive for as long as the run."""
    lock = tmp_path / "holder"
    env = {**os.environ, "HEAVY_LOCK": str(lock), **PERMISSIVE}
    holder = subprocess.Popen(
        ["sh", str(SCRIPT), "the-holder", "sleep", "4"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(40):
            if (lock / "pid").exists():
                break
            time.sleep(0.1)
        written = (lock / "pid").read_text().strip() if (lock / "pid").exists() else ""
        assert written == str(holder.pid), f"pid file reads {written!r}, holder is {holder.pid}"
    finally:
        holder.wait(timeout=15)


def test_an_old_lock_whose_holder_is_alive_is_held_off_and_never_broken(
    tmp_path: Path,
) -> None:
    """A run alive and silent past 45 minutes is waited on, and said aloud — never broken."""
    lock = tmp_path / "holder"
    lock.mkdir()
    (lock / "who").write_text("a hung but living run\n")
    (lock / "pid").write_text(f"{os.getpid()}\n")
    old = time.time() - 60 * 60
    os.utime(lock, (old, old))
    env = {**os.environ, "HEAVY_LOCK": str(lock), **PERMISSIVE}
    waiter = subprocess.Popen(
        ["sh", str(SCRIPT), "tester", "sh", "-c", "echo ran"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(5)
    waiter.terminate()
    stdout, stderr = waiter.communicate(timeout=15)
    assert "ran" not in stdout, stderr
    assert "alive and silent for" in stderr, stderr
    assert (lock / "pid").read_text().strip() == str(os.getpid())


def test_an_old_lock_whose_holder_is_gone_is_broken(tmp_path: Path) -> None:
    """THE CONTROL: a pid that no longer exists is a session that died holding the lock."""
    gone = subprocess.Popen(["true"])
    gone.wait()
    lock = tmp_path / "holder"
    lock.mkdir()
    (lock / "who").write_text("a session that died\n")
    (lock / "pid").write_text(f"{gone.pid}\n")
    old = time.time() - 60 * 60
    os.utime(lock, (old, old))
    result = run(lock, "sh", "-c", "echo ran", timeout=30)
    assert "ran" in result.stdout
    assert "breaking a stale lock" in result.stderr


# ── A holder waiting for room must not keep the lock (auditor's order 71) ────
# `heavy.sh` used to take the lock and only THEN wait for room, so a holder
# stuck waiting for load to drop held the lock the whole time it waited — and
# every run behind it waited too, including a run whose class already fit.
# Measured: docs-l22 held the lock 27 minutes waiting for load, with a
# `--class rule` run (ceiling 10) queued behind it.

FAKE_UPTIME_LOAD_EIGHT = "12:00  up 1 day,  1 user, load averages: 8.00 7.50 7.00\n"


def test_a_holder_waiting_for_room_does_not_block_a_run_that_already_fits(
    tmp_path: Path,
) -> None:
    """THE DEFECT: a browser-class holder waiting for room must not keep the lock.

    Free memory is stubbed generous (5 706 MB, comfortably above every class's
    floor) and load is stubbed at 8 — over the browser class's ceiling of 6, but
    under the rule class's ceiling of 10. The browser-class run therefore waits
    for room forever; the rule-class run already fits and must take the lock and
    finish without waiting behind a holder that never started.
    """
    stand_in = tmp_path / "bin"
    stand_in.mkdir()
    vm_stat = stand_in / "vm_stat"
    vm_stat.write_text(f"#!/bin/sh\ncat <<'READING'\n{VM_STAT_WITH_SPECULATIVE_PAGES}READING\n")
    vm_stat.chmod(0o755)
    uptime = stand_in / "uptime"
    uptime.write_text(f"#!/bin/sh\necho '{FAKE_UPTIME_LOAD_EIGHT.strip()}'\n")
    uptime.chmod(0o755)

    lock = tmp_path / "holder"
    env = {**os.environ, "HEAVY_LOCK": str(lock), "PATH": f"{stand_in}:{os.environ['PATH']}"}
    env.pop("HEAVY_FREE_FLOOR_MB", None)
    env.pop("HEAVY_LOAD_CEILING", None)

    waiting_for_room = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "browser", "waits-for-room", "sleep", "30"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        time.sleep(2)
        started = time.monotonic()
        try:
            already_fits = subprocess.run(
                ["sh", str(SCRIPT), "--class", "rule", "already-fits", "sh", "-c", "echo ran"],
                capture_output=True,
                text=True,
                timeout=8,
                env=env,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(
                "a rule-class run (ceiling 10, load stubbed at 8) waited behind a "
                "browser-class holder (ceiling 6) still waiting for room — the "
                "holder must not keep the lock while it waits for room"
            )
        assert already_fits.returncode == 0, already_fits.stderr
        assert "ran" in already_fits.stdout
        assert time.monotonic() - started < 8
    finally:
        waiting_for_room.terminate()
        waiting_for_room.wait(timeout=15)


# ── Heavy runs yield to Plex (auditor's order 88) ────────────────────────────
# 2026-09-29 22:27, the operator: « J'ai plex qui bug, les videos tourne plus la
# machine est saturé ? ». A full harness suite ran with no `TM_HARNESS_JOBS`,
# fanned out to the core count, and starved the Plex Transcoder while `heavy.sh`
# waited for room only BEFORE its child started — nothing yielded once it was
# running. These tests fake both readings the guard needs (a process named
# « Plex Transcoder » and the one-minute load) so none of them waits for a real
# transcode or a real busy machine.


def _write_uptime_stub(bin_dir: Path, load_file: Path) -> None:
    """Install a fake `uptime` whose load average is read from a file the test can rewrite.

    Args:
        bin_dir: Directory prepended to PATH, so this stub is found before the real one.
        load_file: File holding the one-minute load this stub reports, one bare number.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "uptime"
    stub.write_text(
        "#!/bin/sh\n"
        f'load=$(cat "{load_file}")\n'
        'echo "12:00  up 1 day,  1 user, load averages: ${load} ${load} ${load}"\n'
    )
    stub.chmod(0o755)


def _fake_plex_pattern(tmp_path: Path) -> str:
    """A process-name pattern unique to one test, read through `HEAVY_PLEX_PROCESS_PATTERN`.

    THE REAL PLEX TRANSCODER CAN BE GENUINELY RUNNING on the machine a test runs
    on — it was, on this one, while these tests were first written. A fixture
    literally named « Plex Transcoder » is then indistinguishable from the real
    thing: killing the fixture leaves the guard still reading a transcode, and a
    test built on « no transcoder is running » is quietly false. `heavy.sh`
    reads its pattern from the environment for exactly this reason.

    Args:
        tmp_path: Pytest's per-test scratch directory, already unique.

    Returns:
        A pattern no real process answers to.
    """
    return f"heavy-sh-test-fixture-transcoder-{tmp_path.name}"


def _spawn_fake_transcoder(tmp_path: Path, pattern: str) -> subprocess.Popen[bytes]:
    """Start a process whose command line contains the given pattern, nothing more.

    `pgrep -f` matches the full command line, which is how the guard tells a real
    transcode apart from Plex merely running — the fixture's path alone is enough
    to fool it exactly the way the real binary's own path does.

    Args:
        tmp_path: Scratch directory to hold the fake executable.
        pattern: The (unique) name this fixture's path carries — see `_fake_plex_pattern`.

    Returns:
        The running process; the caller terminates it.
    """
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir(exist_ok=True)
    fake = fixture_dir / pattern
    fake.write_text("#!/bin/sh\nsleep 120\n")
    fake.chmod(0o755)
    return subprocess.Popen([str(fake)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_until(predicate: Callable[[], bool], timeout: float, interval: float = 0.2) -> bool:
    """Poll a predicate until it is true or the timeout passes.

    Args:
        predicate: Zero-argument callable checked each iteration.
        timeout: Seconds to keep polling.
        interval: Seconds between polls.

    Returns:
        Whether the predicate became true within the timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


@pytest.mark.parametrize("knob", ["HEAVY_PLEX_LOAD_CEILING", "HEAVY_PLEX_LOAD_RESUME", "HEAVY_PLEX_PROCESS_PATTERN"])
def test_the_plex_thresholds_are_readable_from_the_environment(knob: str) -> None:
    """The margin is the point here too: an unreadable threshold is a threshold nobody can raise."""
    assert f"{knob}:-" in SCRIPT.read_text(), f"{knob} is not readable from the environment"


def test_a_heavy_run_is_suspended_while_plex_transcodes_under_load_and_resumes_when_load_falls(
    tmp_path: Path,
) -> None:
    """THE CORE CASE: Plex active + load over the ceiling suspends; load under the resume threshold, not."""
    stand_in = tmp_path / "bin"
    load_file = tmp_path / "load"
    load_file.write_text("20\n")
    _write_uptime_stub(stand_in, load_file)

    heartbeat = tmp_path / "heartbeat"
    heartbeat.write_text("")
    lock = tmp_path / "holder"
    pattern = _fake_plex_pattern(tmp_path)
    env = {
        **os.environ,
        "HEAVY_LOCK": str(lock),
        "PATH": f"{stand_in}:{os.environ['PATH']}",
        "HB": str(heartbeat),
        "HEAVY_PLEX_PROCESS_PATTERN": pattern,
        **PERMISSIVE,
    }
    child_script = 'i=0; while [ "$i" -lt 200 ]; do printf x >> "$HB"; i=$((i + 1)); sleep 0.2; done'

    transcoder = _spawn_fake_transcoder(tmp_path, pattern)
    try:
        run_proc = subprocess.Popen(
            ["sh", str(SCRIPT), "plex-yield", "sh", "-c", child_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        try:
            assert _wait_until(lambda: heartbeat.stat().st_size > 0, timeout=10), "the child never started"
            # The guard's first check lands at ~3 s; wait past it so the snapshot
            # below is taken AFTER the child is already suspended, not before.
            time.sleep(5)
            size_at_suspend = heartbeat.stat().st_size
            time.sleep(5)
            size_after_wait = heartbeat.stat().st_size
            assert size_after_wait == size_at_suspend, (
                f"the heartbeat grew from {size_at_suspend} to {size_after_wait} bytes "
                "while Plex transcoded under load — the child was not suspended"
            )

            # Drop the load under the resume threshold (8) and confirm growth resumes.
            load_file.write_text("5\n")
            resumed = _wait_until(lambda: heartbeat.stat().st_size > size_after_wait, timeout=8)
            assert resumed, "the child did not resume once load fell under the resume threshold"
        finally:
            run_proc.terminate()
            run_proc.wait(timeout=15)
    finally:
        transcoder.terminate()
        transcoder.wait(timeout=10)


def test_a_suspended_run_also_resumes_when_the_transcoder_is_gone_rather_than_load_alone(
    tmp_path: Path,
) -> None:
    """THE OTHER RESUME PATH: the transcoder disappearing resumes the run even if load stays high."""
    stand_in = tmp_path / "bin"
    load_file = tmp_path / "load"
    load_file.write_text("20\n")
    _write_uptime_stub(stand_in, load_file)

    heartbeat = tmp_path / "heartbeat"
    heartbeat.write_text("")
    lock = tmp_path / "holder"
    pattern = _fake_plex_pattern(tmp_path)
    env = {
        **os.environ,
        "HEAVY_LOCK": str(lock),
        "PATH": f"{stand_in}:{os.environ['PATH']}",
        "HB": str(heartbeat),
        "HEAVY_PLEX_PROCESS_PATTERN": pattern,
        **PERMISSIVE,
    }
    child_script = 'i=0; while [ "$i" -lt 200 ]; do printf x >> "$HB"; i=$((i + 1)); sleep 0.2; done'

    transcoder = _spawn_fake_transcoder(tmp_path, pattern)
    run_proc = subprocess.Popen(
        ["sh", str(SCRIPT), "plex-yield-gone", "sh", "-c", child_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        assert _wait_until(lambda: heartbeat.stat().st_size > 0, timeout=10), "the child never started"
        # Past the guard's first ~3 s check, so it has already suspended the child.
        time.sleep(5)
        size_at_suspend = heartbeat.stat().st_size
        time.sleep(4)
        assert heartbeat.stat().st_size == size_at_suspend, "the child was not suspended under load"

        # Load stays at 20 — well over the ceiling — but the transcoder is gone.
        transcoder.terminate()
        transcoder.wait(timeout=10)
        resumed = _wait_until(lambda: heartbeat.stat().st_size > size_at_suspend, timeout=8)
        assert resumed, "the run did not resume once the transcoder disappeared, load still over the ceiling"
    finally:
        run_proc.terminate()
        run_proc.wait(timeout=15)


def test_high_load_alone_never_suspends_a_run_with_no_transcoder(tmp_path: Path) -> None:
    """THE GUARD READS PLEX, NOT LOAD ALONE: no transcoder, no suspension, whatever the load."""
    stand_in = tmp_path / "bin"
    load_file = tmp_path / "load"
    load_file.write_text("20\n")
    _write_uptime_stub(stand_in, load_file)

    heartbeat = tmp_path / "heartbeat"
    heartbeat.write_text("")
    lock = tmp_path / "holder"
    env = {
        **os.environ,
        "HEAVY_LOCK": str(lock),
        "PATH": f"{stand_in}:{os.environ['PATH']}",
        "HB": str(heartbeat),
        **PERMISSIVE,
    }
    child_script = 'i=0; while [ "$i" -lt 40 ]; do printf x >> "$HB"; i=$((i + 1)); sleep 0.2; done'

    run_proc = subprocess.Popen(
        ["sh", str(SCRIPT), "plex-no-transcoder", "sh", "-c", child_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        assert _wait_until(lambda: heartbeat.stat().st_size >= 5, timeout=10), "the child never ran"
        size_a = heartbeat.stat().st_size
        time.sleep(5)
        size_b = heartbeat.stat().st_size
        assert size_b > size_a, "the run stalled with no Plex Transcoder anywhere in sight"
    finally:
        run_proc.terminate()
        run_proc.wait(timeout=15)


def test_a_transcoder_below_the_load_ceiling_never_suspends_a_run(tmp_path: Path) -> None:
    """THE OTHER CONTROL: Plex transcoding at a quiet machine is not a reason to pause anything."""
    stand_in = tmp_path / "bin"
    load_file = tmp_path / "load"
    load_file.write_text("2\n")
    _write_uptime_stub(stand_in, load_file)

    heartbeat = tmp_path / "heartbeat"
    heartbeat.write_text("")
    lock = tmp_path / "holder"
    pattern = _fake_plex_pattern(tmp_path)
    env = {
        **os.environ,
        "HEAVY_LOCK": str(lock),
        "PATH": f"{stand_in}:{os.environ['PATH']}",
        "HB": str(heartbeat),
        "HEAVY_PLEX_PROCESS_PATTERN": pattern,
        **PERMISSIVE,
    }
    child_script = 'i=0; while [ "$i" -lt 40 ]; do printf x >> "$HB"; i=$((i + 1)); sleep 0.2; done'

    transcoder = _spawn_fake_transcoder(tmp_path, pattern)
    try:
        run_proc = subprocess.Popen(
            ["sh", str(SCRIPT), "plex-quiet-machine", "sh", "-c", child_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        try:
            assert _wait_until(lambda: heartbeat.stat().st_size >= 5, timeout=10), "the child never ran"
            size_a = heartbeat.stat().st_size
            time.sleep(5)
            size_b = heartbeat.stat().st_size
            assert size_b > size_a, "the run stalled while Plex transcoded on an otherwise quiet machine"
        finally:
            run_proc.terminate()
            run_proc.wait(timeout=15)
    finally:
        transcoder.terminate()
        transcoder.wait(timeout=10)


def test_the_suspended_signal_also_reaches_a_descendant_that_left_the_process_group(
    tmp_path: Path,
) -> None:
    """THE DEFECT A PLAIN GROUP SIGNAL MISSES: a browser a driver launches detached (its own session).

    The wrapped command here spawns a grandchild with `start_new_session=True` —
    its own process group, exactly what a Playwright-launched browser can end up
    in. `kill -STOP -$child` alone never reaches it; the guard must walk the
    process tree by descent, not by group, to suspend it too.
    """
    stand_in = tmp_path / "bin"
    load_file = tmp_path / "load"
    load_file.write_text("20\n")
    _write_uptime_stub(stand_in, load_file)

    grandchild_hb = tmp_path / "grandchild_heartbeat"
    grandchild_hb.write_text("")
    grandchild_script = tmp_path / "grandchild.py"
    grandchild_script.write_text(
        "import time\n"
        "i = 0\n"
        "while i < 200:\n"
        f"    with open({str(grandchild_hb)!r}, 'a') as f:\n"
        "        f.write('x')\n"
        "    time.sleep(0.2)\n"
        "    i += 1\n"
    )

    grandchild_pid_file = tmp_path / "grandchild.pid"
    parent_script = tmp_path / "parent.py"
    parent_script.write_text(
        "import subprocess, sys, time\n"
        f"gc = subprocess.Popen([sys.executable, {str(grandchild_script)!r}], start_new_session=True)\n"
        f"open({str(grandchild_pid_file)!r}, 'w').write(str(gc.pid))\n"
        "while True:\n"
        "    time.sleep(0.2)\n"
    )

    lock = tmp_path / "holder"
    pattern = _fake_plex_pattern(tmp_path)
    env = {
        **os.environ,
        "HEAVY_LOCK": str(lock),
        "PATH": f"{stand_in}:{os.environ['PATH']}",
        "HEAVY_PLEX_PROCESS_PATTERN": pattern,
        **PERMISSIVE,
    }

    transcoder = _spawn_fake_transcoder(tmp_path, pattern)
    run_proc = subprocess.Popen(
        ["sh", str(SCRIPT), "plex-detached-grandchild", "python3", str(parent_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        assert _wait_until(lambda: grandchild_hb.stat().st_size > 0, timeout=10), "the grandchild never started"
        # Past the guard's first ~3 s check, so it has already suspended the tree.
        time.sleep(5)
        size_at_suspend = grandchild_hb.stat().st_size
        time.sleep(4)
        assert grandchild_hb.stat().st_size == size_at_suspend, (
            "the detached grandchild kept writing while its ancestor's run was suspended — "
            "a process-group-only signal missed it"
        )

        load_file.write_text("5\n")
        resumed = _wait_until(lambda: grandchild_hb.stat().st_size > size_at_suspend, timeout=8)
        assert resumed, "the detached grandchild never resumed"
    finally:
        run_proc.terminate()
        run_proc.wait(timeout=15)
        transcoder.terminate()
        transcoder.wait(timeout=10)
        # The grandchild left the process group ON PURPOSE (that is the point of
        # this test) — `run_proc.terminate()` above never reaches it, so it is
        # killed by the pid its own parent wrote down.
        if grandchild_pid_file.exists():
            try:
                os.kill(int(grandchild_pid_file.read_text().strip()), 9)
            except (ProcessLookupError, ValueError):
                pass


# ── heavy.sh chooses TM_HARNESS_JOBS for its own child (auditor's order 90) ──
# Once the Plex guard exists, `heavy.sh` knows whether a transcode is running
# at the moment it starts a child — so it can hand that child a fan-out
# already lowered, rather than starting at 3 and discovering the starve later.
# `run.sh`'s own bare default is untouched by this (it stays 2 outside
# heavy.sh); this is heavy.sh choosing a number FOR its child's environment.

CHILD_ECHOES_HARNESS_JOBS = 'echo "TM_HARNESS_JOBS=${TM_HARNESS_JOBS:-UNSET}"'


def _run_with_no_ambient_harness_jobs(lock: Path, *command: str, **environment: str):
    """Like `run()`, but with `TM_HARNESS_JOBS` stripped from the inherited environment first.

    This suite can itself run wrapped by `sh scripts/heavy.sh --class test …`
    (the gate this repair's own tests run under) — and heavy.sh, once order 90
    lands, exports `TM_HARNESS_JOBS` for ITS OWN child (this pytest process).
    A test asking what a *fresh* heavy.sh invocation chooses must not inherit
    that ambient value, or it is testing the outer wrapper, not the inner one.

    Args:
        lock: The lock this run takes, moved aside as usual.
        *command: The command to wrap.
        **environment: Extra environment, verbatim, applied after the strip.

    Returns:
        The completed process.
    """
    env = {k: v for k, v in os.environ.items() if k != "TM_HARNESS_JOBS"}
    env = {**env, "HEAVY_LOCK": str(lock), **PERMISSIVE, **environment}
    return subprocess.run(
        ["sh", str(SCRIPT), "tester", *command],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_heavy_sets_three_harness_jobs_for_its_child_when_plex_is_not_transcoding(
    tmp_path: Path,
) -> None:
    """No transcoder in sight: the child gets the higher of the two figures.

    The pattern is pointed at a name nothing answers to — the real Plex
    Transcoder can be genuinely running on the machine this test runs on (see
    `_fake_plex_pattern`), and the default pattern would then read it as active.
    """
    result = _run_with_no_ambient_harness_jobs(
        tmp_path / "holder",
        "sh",
        "-c",
        CHILD_ECHOES_HARNESS_JOBS,
        HEAVY_PLEX_PROCESS_PATTERN=_fake_plex_pattern(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert "TM_HARNESS_JOBS=3" in result.stdout, result.stdout


def test_heavy_sets_two_harness_jobs_for_its_child_when_plex_is_transcoding(tmp_path: Path) -> None:
    """A transcode already running: the child starts at the lower figure, not after starving it."""
    pattern = _fake_plex_pattern(tmp_path)
    transcoder = _spawn_fake_transcoder(tmp_path, pattern)
    try:
        result = _run_with_no_ambient_harness_jobs(
            tmp_path / "holder",
            "sh",
            "-c",
            CHILD_ECHOES_HARNESS_JOBS,
            HEAVY_PLEX_PROCESS_PATTERN=pattern,
        )
        assert result.returncode == 0, result.stderr
        assert "TM_HARNESS_JOBS=2" in result.stdout, result.stdout
    finally:
        transcoder.terminate()
        transcoder.wait(timeout=10)


@pytest.mark.parametrize("spawn_transcoder", [False, True])
def test_heavy_never_overrides_an_explicit_harness_jobs_value(tmp_path: Path, spawn_transcoder: bool) -> None:
    """A caller that already knows its own number is never second-guessed, either way."""
    pattern = _fake_plex_pattern(tmp_path)
    transcoder = _spawn_fake_transcoder(tmp_path, pattern) if spawn_transcoder else None
    try:
        result = run(
            tmp_path / "holder",
            "sh",
            "-c",
            CHILD_ECHOES_HARNESS_JOBS,
            TM_HARNESS_JOBS="7",
            HEAVY_PLEX_PROCESS_PATTERN=pattern,
        )
        assert result.returncode == 0, result.stderr
        assert "TM_HARNESS_JOBS=7" in result.stdout, result.stdout
    finally:
        if transcoder is not None:
            transcoder.terminate()
            transcoder.wait(timeout=10)


# ── A short run preempts a browser-class holder (auditor's order 90) ────────
# Tonight a tm-design build waited 35 min behind a full harness suite. These
# tests use the class thresholds for real (a named class refuses a lowered
# floor, so `PERMISSIVE` cannot apply here) — `vm_stat`/`uptime` are stubbed to
# report abundant room regardless, because THE REAL MACHINE'S OWN ROOM MOVES:
# other sessions on this host can and do push it under a browser class's own
# 4 096 MB / load 6 while these tests run, and a class's floor may only be
# RAISED by the environment, never lowered — there is no permissive escape
# hatch here the way `PERMISSIVE` is one for an unclassed run.

_HEARTBEAT_LOOP = 'i=0; while [ "$i" -lt {n} ]; do printf x >> "$HB"; i=$((i + 1)); sleep 0.2; done'


def _room_stub_bin(tmp_path: Path) -> Path:
    """Build a `bin/` whose `vm_stat`/`uptime` report abundant room, whatever the real machine reads.

    Args:
        tmp_path: Scratch directory to hold the stub executables.

    Returns:
        The directory, meant to be prepended to PATH.
    """
    stand_in = tmp_path / "room_bin"
    stand_in.mkdir(exist_ok=True)
    vm_stat = stand_in / "vm_stat"
    vm_stat.write_text(f"#!/bin/sh\ncat <<'READING'\n{VM_STAT_WITH_SPECULATIVE_PAGES}READING\n")
    vm_stat.chmod(0o755)
    uptime = stand_in / "uptime"
    uptime.write_text("#!/bin/sh\necho '12:00  up 1 day,  1 user, load averages: 2.00 2.00 2.00'\n")
    uptime.chmod(0o755)
    return stand_in


def _classed_env(tmp_path: Path, lock: Path, **extra: str) -> dict[str, str]:
    """Environment for a classed run: the real class thresholds, room stubbed abundant.

    Args:
        tmp_path: The test's scratch directory, for the room stubs.
        lock: The moved lock this run and its holder share.
        **extra: Additional variables, merged in last.

    Returns:
        The environment dict for `subprocess.Popen`/`subprocess.run`.
    """
    stand_in = _room_stub_bin(tmp_path)
    env = {**os.environ, "HEAVY_LOCK": str(lock), "PATH": f"{stand_in}:{os.environ['PATH']}"}
    env.pop("HEAVY_FREE_FLOOR_MB", None)
    env.pop("HEAVY_LOAD_CEILING", None)
    env.update(extra)
    return env


def test_a_short_run_preempts_a_browser_holder_instead_of_waiting_behind_it(tmp_path: Path) -> None:
    """THE CORE CASE: the browser holder's tree freezes for the short run's duration, then resumes."""
    lock = tmp_path / "holder"
    holder_hb = tmp_path / "holder_heartbeat"
    holder_hb.write_text("")
    short_hb = tmp_path / "short_heartbeat"
    short_hb.write_text("")

    holder = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "browser", "browser-holder", "sh", "-c", _HEARTBEAT_LOOP.format(n=300)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_classed_env(tmp_path, lock, HB=str(holder_hb)),
    )
    try:
        assert _wait_until(lambda: holder_hb.stat().st_size > 0, timeout=15), "the holder never started"

        started = time.monotonic()
        short_run = subprocess.run(
            ["sh", str(SCRIPT), "--class", "test", "short-run", "sh", "-c", _HEARTBEAT_LOOP.format(n=20)],
            capture_output=True,
            text=True,
            timeout=30,
            env=_classed_env(tmp_path, lock, HB=str(short_hb)),
        )
        elapsed = time.monotonic() - started
        assert short_run.returncode == 0, short_run.stdout + short_run.stderr
        assert "preempts" in short_run.stderr, short_run.stderr
        assert elapsed < 15, f"the short run waited {elapsed:.1f}s — it should have preempted, not queued"
        # It ran its own 4 s of heartbeats (20 x 0.2 s) to completion.
        assert short_hb.stat().st_size >= 15, short_hb.read_text()

        # The holder's own heartbeat must have been frozen for at least some of
        # that window — not merely slowed by contention.
        holder_size_at_end_of_short_run = holder_hb.stat().st_size
        time.sleep(1)
        assert holder_hb.stat().st_size > holder_size_at_end_of_short_run, (
            "the browser holder never resumed after the short run finished"
        )
    finally:
        holder.terminate()
        holder.wait(timeout=15)


def test_a_short_run_past_its_cap_resumes_the_holder_and_keeps_going_unprotected(tmp_path: Path) -> None:
    """THE FALLBACK: past `HEAVY_PREEMPT_CAP_SECONDS`, the holder resumes and the short run just runs."""
    lock = tmp_path / "holder"
    holder_hb = tmp_path / "holder_heartbeat"
    holder_hb.write_text("")
    short_hb = tmp_path / "short_heartbeat"
    short_hb.write_text("")

    holder = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "browser", "browser-holder", "sh", "-c", _HEARTBEAT_LOOP.format(n=300)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_classed_env(tmp_path, lock, HB=str(holder_hb)),
    )
    try:
        assert _wait_until(lambda: holder_hb.stat().st_size > 0, timeout=15), "the holder never started"

        short_run = subprocess.Popen(
            ["sh", str(SCRIPT), "--class", "test", "short-run-long", "sh", "-c", _HEARTBEAT_LOOP.format(n=40)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            env=_classed_env(tmp_path, lock, HB=str(short_hb), HEAVY_PREEMPT_CAP_SECONDS="2"),
        )
        try:
            # The short run itself takes ~8 s (40 x 0.2 s); the cap (2 s) should
            # resume the holder well before the short run is done.
            holder_grew_before_short_run_finished = _wait_until(
                lambda: short_run.poll() is None and _holder_grew(holder_hb),
                timeout=6,
            )
            assert holder_grew_before_short_run_finished, (
                "the holder never resumed before the capped short run finished"
            )
            stderr = short_run.communicate(timeout=15)[1]
            assert "past 2s" in stderr or "past " in stderr, stderr
        finally:
            if short_run.poll() is None:
                short_run.terminate()
                short_run.wait(timeout=15)
    finally:
        holder.terminate()
        holder.wait(timeout=15)


def _holder_grew(holder_hb: Path, _seen: dict[Path, int] = {}) -> bool:  # noqa: B006 - a closure's own memo
    """True once, the first time `holder_hb` is read larger than its own first reading.

    Args:
        holder_hb: The holder's heartbeat file.
        _seen: Memoised first reading, keyed by path — a `_wait_until` predicate
            takes no arguments of its own, so the baseline has to live here.

    Returns:
        Whether the file has grown since the first call for this path.
    """
    size = holder_hb.stat().st_size
    if holder_hb not in _seen:
        _seen[holder_hb] = size
        return False
    return size > _seen[holder_hb]


def test_two_short_runs_queue_behind_each_other_not_behind_the_browser_holder(tmp_path: Path) -> None:
    """NO NESTING DEADLOCK: a second short run waits for the first short run, never for the long holder."""
    lock = tmp_path / "holder"
    holder_hb = tmp_path / "holder_heartbeat"
    holder_hb.write_text("")

    holder = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "browser", "browser-holder", "sh", "-c", _HEARTBEAT_LOOP.format(n=300)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_classed_env(tmp_path, lock, HB=str(holder_hb)),
    )
    try:
        assert _wait_until(lambda: holder_hb.stat().st_size > 0, timeout=15), "the holder never started"

        started = time.monotonic()
        results: list[subprocess.CompletedProcess[str]] = []

        def _run_short(who: str) -> None:
            hb = tmp_path / f"{who}_heartbeat"
            hb.write_text("")
            results.append(
                subprocess.run(
                    ["sh", str(SCRIPT), "--class", "test", who, "sh", "-c", _HEARTBEAT_LOOP.format(n=15)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=_classed_env(tmp_path, lock, HB=str(hb)),
                )
            )

        import threading

        first = threading.Thread(target=_run_short, args=("short-a",))
        second = threading.Thread(target=_run_short, args=("short-b",))
        first.start()
        time.sleep(0.5)
        second.start()
        first.join(timeout=30)
        second.join(timeout=30)
        elapsed = time.monotonic() - started

        assert len(results) == 2
        assert all(r.returncode == 0 for r in results), [r.stdout + r.stderr for r in results]
        # Two ~3 s short runs (15 x 0.2 s), serialised by the preempt sub-lock,
        # finish in a few seconds — nowhere near the browser holder's own 60 s.
        assert elapsed < 20, f"the second short run waited {elapsed:.1f}s — it queued behind the holder, not the first"
    finally:
        holder.terminate()
        holder.wait(timeout=15)


def test_the_holder_reports_its_own_total_preempted_time_on_exit(tmp_path: Path) -> None:
    """THE KNOWN LIMIT, MADE VISIBLE: a SIGSTOPped process's own wall-clock waits keep counting down.

    Nothing outside the holder's process can add back the seconds a `timeout(1)`
    wrapper or a Playwright deadline lost while frozen — a rule preempted for
    long enough can surface a timeout the instant it resumes, for a pause, not
    a hang. What this proves: the holder's own exit line names how long it was
    preempted, so a reader can tell the two apart.
    """
    lock = tmp_path / "holder"
    holder_hb = tmp_path / "holder_heartbeat"
    holder_hb.write_text("")
    short_hb = tmp_path / "short_heartbeat"
    short_hb.write_text("")

    holder = subprocess.Popen(
        ["sh", str(SCRIPT), "--class", "browser", "browser-holder", "sh", "-c", _HEARTBEAT_LOOP.format(n=30)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        env=_classed_env(tmp_path, lock, HB=str(holder_hb)),
    )
    try:
        assert _wait_until(lambda: holder_hb.stat().st_size > 0, timeout=15), "the holder never started"

        short_run = subprocess.run(
            ["sh", str(SCRIPT), "--class", "test", "short-run", "sh", "-c", _HEARTBEAT_LOOP.format(n=15)],
            capture_output=True,
            text=True,
            timeout=30,
            env=_classed_env(tmp_path, lock, HB=str(short_hb)),
        )
        assert short_run.returncode == 0, short_run.stdout + short_run.stderr

        holder_stderr = holder.communicate(timeout=20)[1]
        assert "preempted for" in holder_stderr, holder_stderr
        assert "not a hang" in holder_stderr, holder_stderr
    finally:
        if holder.poll() is None:
            holder.terminate()
            holder.wait(timeout=15)
