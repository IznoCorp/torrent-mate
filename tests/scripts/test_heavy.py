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
        capture_output=True, text=True, timeout=timeout, env=env,
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
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
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
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
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
