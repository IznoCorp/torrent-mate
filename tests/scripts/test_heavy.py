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
    free = subprocess.run(["sh", str(SCRIPT), "--held"], capture_output=True, text=True, env=env, timeout=10)
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
        held = subprocess.run(["sh", str(SCRIPT), "--held"], capture_output=True, text=True, env=env, timeout=10)
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


def test_a_machine_that_reports_no_memory_runs_rather_than_waits(tmp_path: Path) -> None:
    """THE SECOND DEFECT THIS FILE CAUGHT, and it is the first one's shape.

    `vm_stat` is Darwin's and the repository's runners are Linux, so the first
    version could not read free memory there — and WAITED for a number it could
    never obtain, hanging every job that touched it. A gate that cannot measure
    must let the run through and say so; only a gate that measures may hold one.
    """
    empty = tmp_path / "bin"
    empty.mkdir()
    for name in ("vm_stat", "sh", "awk", "uptime", "sleep", "mkdir", "rm", "cat", "dirname", "find"):
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
