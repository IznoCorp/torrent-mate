"""Tests for the self-managed cron scheduler (``personalscraper schedule``).

Regression for the PM2 ``cron_restart`` defect: PM2 6.0.8 ticks TWICE around a
boundary (10:59:59 then 11:00:00) and its second tick SIGINT-kills the run the
first one started a second earlier. The scheduler fires once per boundary, never
early, and never while a run is still going; a fake clock drives every test.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from personalscraper import scheduler


class FakeClock:
    """A clock whose ``sleep`` can wake early, as a real timer does around a boundary.

    Args:
        start: The instant the clock reads first.
        early_wake: When set, each ``sleep`` returns this long BEFORE the asked
            duration elapsed (PM2's first tick, one second before the boundary).
    """

    def __init__(self, start: datetime, early_wake: timedelta | None = None) -> None:
        """Start the clock at ``start``; see the class docstring for ``early_wake``."""
        self.now = start
        self.early_wake = early_wake
        self.sleeps: list[float] = []

    def __call__(self) -> datetime:
        """Return the current instant."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Advance by ``seconds``, minus ``early_wake`` once per asked sleep > early_wake."""
        self.sleeps.append(seconds)
        wake = timedelta(seconds=seconds)
        if self.early_wake is not None and wake > self.early_wake:
            wake -= self.early_wake
        self.now += wake


class Runs:
    """Records each run's start and end on the fake clock; a run takes ``duration``."""

    def __init__(self, clock: FakeClock, duration: timedelta, stop_after: int) -> None:
        """Bind the clock; each run lasts ``duration``; ``done`` turns true after ``stop_after`` runs."""
        self.clock = clock
        self.duration = duration
        self.stop_after = stop_after
        self.spans: list[tuple[datetime, datetime]] = []
        self.argvs: list[list[str]] = []

    def __call__(self, argv: list[str]) -> int:
        """Run one job: occupy the clock for ``duration``, count it, ask to stop when done."""
        start = self.clock.now
        self.clock.now += self.duration
        self.spans.append((start, self.clock.now))
        self.argvs.append(argv)
        return 0

    def done(self) -> bool:
        """Whether enough runs happened for the test to end."""
        return len(self.spans) >= self.stop_after


def _drive(cron: str, start: datetime, runs: Runs, clock: FakeClock) -> None:
    scheduler.run_schedule(cron, ["health-check"], clock=clock, sleep=clock.sleep, run=runs, stop=runs.done)


def test_double_tick_at_a_boundary_starts_one_run_that_is_never_cut() -> None:
    """The timer wakes 1 s early, then again at the boundary: ONE run, whole, never re-fired."""
    start = datetime(2026, 10, 2, 14, 59, 0)
    clock = FakeClock(start, early_wake=timedelta(seconds=1))
    runs = Runs(clock, duration=timedelta(milliseconds=800), stop_after=2)

    _drive("15 * * * *", start, runs, clock)

    assert [s for s, _ in runs.spans] == [datetime(2026, 10, 2, 15, 15, 0), datetime(2026, 10, 2, 16, 15, 0)]
    # Never early: a run starting at 15:14:59 is the tick that killed its twin.
    assert all(s.second == 0 and s.microsecond == 0 for s, _ in runs.spans)
    # Whole: each span ends after it began and before the next begins (no overlap).
    assert runs.spans[0][1] <= runs.spans[1][0]


def test_a_run_finishing_inside_the_boundary_second_is_not_fired_again() -> None:
    """A run done in 0.2 s at HH:15:00 must not be re-fired by a second tick at the same boundary."""
    start = datetime(2026, 10, 2, 15, 14, 59)
    clock = FakeClock(start)
    runs = Runs(clock, duration=timedelta(milliseconds=200), stop_after=3)

    _drive("15 * * * *", start, runs, clock)

    assert [s for s, _ in runs.spans] == [
        datetime(2026, 10, 2, 15, 15, 0),
        datetime(2026, 10, 2, 16, 15, 0),
        datetime(2026, 10, 2, 17, 15, 0),
    ]


def test_a_run_longer_than_the_period_never_overlaps_and_skips_missed_boundaries() -> None:
    """A 90-minute run on an hourly cron: no second instance, the missed :15 is skipped."""
    start = datetime(2026, 10, 2, 14, 59, 0)
    clock = FakeClock(start)
    runs = Runs(clock, duration=timedelta(minutes=90), stop_after=2)

    _drive("15 * * * *", start, runs, clock)

    first, second = runs.spans
    assert first[0] == datetime(2026, 10, 2, 15, 15, 0)
    assert second[0] == datetime(2026, 10, 2, 17, 15, 0)  # 16:15 fell inside the run
    assert first[1] <= second[0]


def test_the_job_argv_is_passed_through_untouched() -> None:
    """The scheduler runs exactly the CLI arguments it was given."""
    start = datetime(2026, 10, 2, 14, 59, 0)
    clock = FakeClock(start)
    runs = Runs(clock, duration=timedelta(seconds=1), stop_after=1)

    scheduler.run_schedule(
        "15 * * * *", ["library-index", "--mode", "full"], clock=clock, sleep=clock.sleep, run=runs, stop=runs.done
    )

    assert runs.argvs == [["library-index", "--mode", "full"]]


@pytest.mark.parametrize(
    ("cron", "after", "expected"),
    [
        ("0 1 * * 1", datetime(2026, 10, 2, 12, 0), datetime(2026, 10, 5, 1, 0)),  # Monday 01:00
        ("30 4 * * 0", datetime(2026, 10, 2, 12, 0), datetime(2026, 10, 4, 4, 30)),  # Sunday
        ("30 4 * * 7", datetime(2026, 10, 2, 12, 0), datetime(2026, 10, 4, 4, 30)),  # Sunday as 7
        ("10 3,15 * * *", datetime(2026, 10, 2, 3, 10), datetime(2026, 10, 2, 15, 10)),  # strictly after
        ("0 3 * * *", datetime(2026, 10, 2, 3, 0, 0, 500), datetime(2026, 10, 3, 3, 0)),
        ("15 * * * *", datetime(2026, 10, 2, 23, 15), datetime(2026, 10, 3, 0, 15)),
        ("*/20 * * * *", datetime(2026, 10, 2, 10, 21), datetime(2026, 10, 2, 10, 40)),
        ("0 0 31 * *", datetime(2026, 10, 2, 0, 0), datetime(2026, 10, 31, 0, 0)),
    ],
)
def test_next_fire_matches_cron_semantics(cron: str, after: datetime, expected: datetime) -> None:
    """``next_fire`` is the first matching minute strictly after the instant given."""
    assert scheduler.next_fire(cron, after) == expected


@pytest.mark.parametrize("bad", ["", "* * * *", "61 * * * *", "* 24 * * *", "a * * * *", "*/0 * * * *"])
def test_a_malformed_cron_is_refused(bad: str) -> None:
    """A bad expression fails at start, not silently never."""
    with pytest.raises(ValueError):
        scheduler.next_fire(bad, datetime(2026, 10, 2))


def test_the_cli_hands_the_whole_job_after_double_dash_to_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """``schedule --cron X -- library-index --mode full`` runs exactly ``library-index --mode full``."""
    from typer.testing import CliRunner

    import personalscraper.cli  # noqa: F401 — registers the commands
    from personalscraper.cli_app import app

    seen: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(scheduler, "serve", lambda cron, job: seen.append((cron, job)) or 0)

    result = CliRunner().invoke(
        app, ["schedule", "--cron", "0 1 * * 1", "--", "library-index", "--mode", "full", "--no-budget"]
    )

    assert result.exit_code == 0, result.output
    assert seen == [("0 1 * * 1", ["library-index", "--mode", "full", "--no-budget"])]
