"""Self-managed cron loop — ``personalscraper schedule --cron EXPR -- JOB...``.

Replaces PM2's ``cron_restart`` for the scheduled jobs of ``ecosystem.config.js``.
PM2 6.0.8's cron ticks TWICE around a boundary (10:59:59 then 11:00:00) and its
second tick SIGINT-kills the run the first had started a second earlier (25
health-check, 4 search, 4 grab and 1 follow-detect runs cut on 2026-10-02).

Here PM2 only keeps ONE long-lived loop alive per job (``autorestart: true``, no
``cron_restart``). The loop sleeps to the next matching minute, runs the job to its
end in a child process, and only then looks for the next minute — so a boundary
fires once, never early, and never while a run is still going.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from types import FrameType

from personalscraper.logger import get_logger

log = get_logger(__name__)

#: (low, high) bounds of the five cron fields: minute, hour, day of month, month, day of week.
#: Day of week accepts 0-7 (0 and 7 are Sunday).
_BOUNDS: tuple[tuple[int, int], ...] = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))

#: A search for the next minute gives up after this many days (a Feb 30 never matches).
_HORIZON_DAYS = 366 * 5

#: Longest single sleep: a clock that jumps (NTP, wake from sleep) is re-read at least this often.
_MAX_SLEEP_SECONDS = 60.0


def _parse_field(field: str, low: int, high: int) -> frozenset[int]:
    """Expand one cron field to the set of values it matches.

    Args:
        field: One field: ``*``, ``N``, ``N-M``, ``*/S``, ``N-M/S`` or a comma list of those.
        low: Lowest legal value.
        high: Highest legal value.

    Returns:
        The matching values.

    Raises:
        ValueError: If the field is malformed or out of bounds.
    """
    values: set[int] = set()
    for part in field.split(","):
        body, _, step_text = part.partition("/")
        step = int(step_text) if step_text else 1
        if step < 1:
            raise ValueError(f"cron step must be >= 1, got {part!r}")
        if body == "*":
            first, last = low, high
        elif "-" in body:
            first_text, _, last_text = body.partition("-")
            first, last = int(first_text), int(last_text)
        else:
            first = int(body)
            last = high if step_text else first
        if not (low <= first <= last <= high):
            raise ValueError(f"cron field {part!r} out of bounds {low}-{high}")
        values.update(range(first, last + 1, step))
    return frozenset(values)


def _parse(cron: str) -> tuple[frozenset[int], ...]:
    """Parse a 5-field cron expression into its five value sets.

    Args:
        cron: ``minute hour day-of-month month day-of-week``.

    Returns:
        The five sets, day of week folded to 0-6 (Sunday = 0).

    Raises:
        ValueError: If the expression is not five valid fields.
    """
    fields = cron.split()
    if len(fields) != 5:
        raise ValueError(f"cron expression needs 5 fields, got {cron!r}")
    try:
        sets = [_parse_field(f, lo, hi) for f, (lo, hi) in zip(fields, _BOUNDS, strict=True)]
    except ValueError as exc:
        raise ValueError(f"invalid cron expression {cron!r}: {exc}") from exc
    sets[4] = frozenset(v % 7 for v in sets[4])
    return tuple(sets)


def next_fire(cron: str, after: datetime) -> datetime:
    """Return the first minute matching ``cron`` strictly after ``after``.

    Day of month and day of week combine as classic cron does: when both are
    restricted, a day matching EITHER fires.

    Args:
        cron: A 5-field cron expression, in the clock's local time.
        after: The instant to search from (exclusive; sub-minute parts are dropped).

    Returns:
        The matching minute, seconds and microseconds zero.

    Raises:
        ValueError: If the expression is malformed or never matches.
    """
    minutes, hours, days, months, weekdays = _parse(cron)
    day_restricted = cron.split()[2] != "*"
    weekday_restricted = cron.split()[4] != "*"
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = candidate + timedelta(days=_HORIZON_DAYS)
    while candidate < limit:
        if candidate.month not in months:
            candidate = (candidate.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
            continue
        weekday = (candidate.weekday() + 1) % 7  # Monday=0 → cron's Sunday=0
        if day_restricted and weekday_restricted:
            day_ok = candidate.day in days or weekday in weekdays
        else:
            day_ok = candidate.day in days and weekday in weekdays
        if not day_ok:
            candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
            continue
        if candidate.hour not in hours:
            candidate = candidate.replace(minute=0) + timedelta(hours=1)
            continue
        if candidate.minute not in minutes:
            candidate += timedelta(minutes=1)
            continue
        return candidate
    raise ValueError(f"cron expression {cron!r} never matches")


def run_schedule(
    cron: str,
    job_argv: list[str],
    *,
    clock: Callable[[], datetime],
    sleep: Callable[[float], None],
    run: Callable[[list[str]], int],
    stop: Callable[[], bool],
) -> None:
    """Run ``job_argv`` at every boundary of ``cron`` until ``stop()`` is true.

    Each iteration waits for the boundary (re-reading the clock after every sleep, so
    a timer that wakes early never fires early), runs the job to its end, then looks
    for the next boundary strictly after the LATER of "the one just run" and "now" —
    a second tick at the same boundary, or a boundary that fell inside a long run, can
    therefore never start a second run.

    Args:
        cron: A 5-field cron expression.
        job_argv: CLI arguments of the job (what follows ``personalscraper``).
        clock: Returns the current local time.
        sleep: Sleeps that many seconds (may return early).
        run: Runs the job to its end and returns its exit code.
        stop: Polled between sleeps and after each run; true ends the loop.

    Raises:
        ValueError: If ``cron`` is malformed (raised before the first sleep).
    """
    after = clock()
    next_fire(cron, after)  # fail at start on a bad expression, not silently never
    while not stop():
        fire = next_fire(cron, after)
        while not stop() and clock() < fire:
            sleep(min((fire - clock()).total_seconds(), _MAX_SLEEP_SECONDS))
        if stop():
            return
        log.info("scheduled_run_start", cron=cron, job=job_argv, fire=fire.isoformat())
        code = run(job_argv)
        log.info("scheduled_run_end", cron=cron, job=job_argv, exit_code=code)
        after = max(fire, clock())


def run_job(argv: list[str]) -> int:
    """Run one job as ``python -m personalscraper ARGV`` and wait for it.

    The child inherits the environment (``PERSONALSCRAPER_CONFIG``) and the cwd. A
    stop signal received by the loop is forwarded to the child by :func:`serve`.

    Args:
        argv: CLI arguments of the job.

    Returns:
        The child's exit code.
    """
    child = subprocess.Popen([sys.executable, "-m", "personalscraper", *argv])
    _CURRENT_CHILD.append(child)
    try:
        return child.wait()
    finally:
        _CURRENT_CHILD.remove(child)


#: The job child being waited on, if any — so the stop signal can be relayed to it.
_CURRENT_CHILD: list[subprocess.Popen[bytes]] = []


def serve(cron: str, job_argv: list[str]) -> int:
    """Run the loop on the real clock until SIGINT/SIGTERM; a stop is relayed to a running job.

    Args:
        cron: A 5-field cron expression.
        job_argv: CLI arguments of the job.

    Returns:
        0 once stopped by a signal.

    Raises:
        ValueError: If ``cron`` is malformed.
    """
    stopped = threading.Event()

    def on_signal(signum: int, _frame: FrameType | None) -> None:
        stopped.set()  # also wakes the sleep below at once, well inside PM2's kill_timeout
        for child in _CURRENT_CHILD:
            child.send_signal(signum)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    def sleep(seconds: float) -> None:
        stopped.wait(seconds)

    run_schedule(cron, job_argv, clock=datetime.now, sleep=sleep, run=run_job, stop=stopped.is_set)
    return 0
