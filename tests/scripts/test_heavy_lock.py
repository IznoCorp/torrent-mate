"""Tests for `scripts/heavy.sh`, the machine-wide lock for heavy runs.

Each test moves the lock into its own temporary directory (`HEAVY_LOCK`) and
lifts the room thresholds, so nothing here waits on the machine's real load or
touches a lock another session holds.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "heavy.sh"


def environment(lock: Path) -> dict[str, str]:
    """The environment that points the script at a private lock and always finds room.

    Args:
        lock: The lock directory to use.

    Returns:
        The process environment.
    """
    return {
        **os.environ,
        "HEAVY_LOCK": str(lock),
        "HEAVY_FREE_FLOOR_MB": "0",
        "HEAVY_LOAD_CEILING": "100000",
    }


def held_by(lock: Path, pid: int, who: str) -> None:
    """Writes a lock as a holder writes it.

    Args:
        lock: The lock directory.
        pid: The holder's process id.
        who: The holder's name.
    """
    lock.mkdir(parents=True)
    (lock / "who").write_text(who + "\n", encoding="utf-8")
    (lock / "pid").write_text(f"{pid}\n", encoding="utf-8")


def test_the_start_says_when_and_how_long_it_waited(tmp_path: Path) -> None:
    """B-495: how long a wrapped run waited was unmeasurable afterwards.

    « holding off » was printed once and « starts » with no time, so a log could
    not say whether a run held for a minute or an hour.
    """
    result = subprocess.run(
        ["sh", str(SCRIPT), "tester", "true"],
        env=environment(tmp_path / "lock" / "holder"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    start = next(line for line in result.stderr.splitlines() if "tester starts" in line)
    assert re.match(r"heavy: \d{2}:\d{2}:\d{2} ", start), start
    assert re.search(r"after \d+ s waiting", start), start


def test_an_older_waiter_goes_before_a_newer_one(tmp_path: Path) -> None:
    """B-472: a polled `mkdir` gave an old demander no precedence over a new one.

    With a lock held and an older waiter queued, the newcomer must not take the
    lock when it frees while the older waiter is still there, and must take it
    once the older one has gone.
    """
    lock = tmp_path / "lock" / "holder"
    holder = subprocess.Popen(["sleep", "60"])
    older = subprocess.Popen(["sleep", "60"])
    newcomer = None
    try:
        held_by(lock, holder.pid, "holder")
        queue = lock.parent / "queue"
        queue.mkdir()
        (queue / f"{1:012d}.{older.pid:08d}").write_text("older\n", encoding="utf-8")
        newcomer = subprocess.Popen(
            ["sh", str(SCRIPT), "newcomer", "true"],
            env=environment(lock),
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
