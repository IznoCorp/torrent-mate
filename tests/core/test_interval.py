"""Tests for the poll-interval strategy in :mod:`kanbanmate.core.interval`.

Covers the **fixed 10 s default cadence** (idle back-off disabled), plus the
opt-in geometric back-off exercised via an explicit ``IntervalConfig(base=15,
idle_max=300, backoff=2)``: the short cadence while active, the back-off as idle
time grows, the clamp at ``idle_max``, and monotonic non-decreasing behaviour.
"""

from __future__ import annotations

from kanbanmate.core.interval import IntervalConfig, next_sleep


class TestActive:
    """Behaviour while the board is recently active."""

    def test_short_when_just_active(self) -> None:
        """Zero idle returns the tight base interval."""
        cfg = IntervalConfig(base=15.0, idle_max=300.0, backoff=2.0)
        assert next_sleep(last_activity_ts=100.0, now=100.0, cfg=cfg) == 15.0

    def test_short_within_first_stretch(self) -> None:
        """Idle below one base stretch still returns the base interval."""
        cfg = IntervalConfig(base=15.0, idle_max=300.0, backoff=2.0)
        assert next_sleep(last_activity_ts=100.0, now=114.0, cfg=cfg) == 15.0

    def test_negative_idle_treated_as_active(self) -> None:
        """Clock skew (now < last activity) is clamped to the base interval."""
        cfg = IntervalConfig(base=15.0, idle_max=300.0, backoff=2.0)
        assert next_sleep(last_activity_ts=200.0, now=100.0, cfg=cfg) == 15.0


class TestBackoff:
    """Geometric back-off as idle time grows."""

    def test_one_stretch_idle_backs_off_once(self) -> None:
        """One full idle stretch multiplies the base by the backoff factor."""
        cfg = IntervalConfig(base=15.0, idle_max=300.0, backoff=2.0)
        # idle = 15 -> exactly one stretch -> 15 * 2**1 = 30.
        assert next_sleep(last_activity_ts=100.0, now=115.0, cfg=cfg) == 30.0

    def test_two_stretches_idle_backs_off_twice(self) -> None:
        """Two idle stretches apply the backoff factor twice."""
        cfg = IntervalConfig(base=15.0, idle_max=300.0, backoff=2.0)
        # idle = 30 -> two stretches -> 15 * 2**2 = 60.
        assert next_sleep(last_activity_ts=100.0, now=130.0, cfg=cfg) == 60.0

    def test_monotonic_non_decreasing(self) -> None:
        """Sleep never decreases as idle time grows."""
        cfg = IntervalConfig(base=15.0, idle_max=300.0, backoff=2.0)
        previous = 0.0
        for elapsed in range(0, 600, 5):
            sleep = next_sleep(last_activity_ts=0.0, now=float(elapsed), cfg=cfg)
            assert sleep >= previous
            previous = sleep


class TestIdleClamp:
    """The idle ceiling clamp."""

    def test_approaches_idle_max_when_idle(self) -> None:
        """A long idle period clamps the interval at idle_max."""
        cfg = IntervalConfig(base=15.0, idle_max=300.0, backoff=2.0)
        assert next_sleep(last_activity_ts=0.0, now=100_000.0, cfg=cfg) == 300.0

    def test_never_exceeds_idle_max(self) -> None:
        """The interval is clamped at idle_max once the candidate would exceed it."""
        cfg = IntervalConfig(base=15.0, idle_max=300.0, backoff=2.0)
        # idle = 60 -> 4 stretches -> 15 * 2**4 = 240 (still under the ceiling).
        assert next_sleep(last_activity_ts=0.0, now=60.0, cfg=cfg) == 240.0
        # idle = 75 -> 5 stretches -> 15 * 2**5 = 480, clamped down to 300.
        assert next_sleep(last_activity_ts=0.0, now=75.0, cfg=cfg) == 300.0


class TestDefaults:
    """The shipped defaults give a FIXED 10 s cadence (idle back-off disabled)."""

    def test_default_base_is_ten_seconds(self) -> None:
        """The default config pins the poll cadence at 10 s."""
        assert IntervalConfig().base == 10.0
        assert IntervalConfig().idle_max == 10.0

    def test_default_config_active(self) -> None:
        """With defaults, a freshly-active board sleeps for the base interval."""
        assert next_sleep(last_activity_ts=0.0, now=0.0) == IntervalConfig().base

    def test_default_config_idle(self) -> None:
        """With defaults, a long-idle board sleeps for idle_max."""
        assert next_sleep(last_activity_ts=0.0, now=1_000_000.0) == IntervalConfig().idle_max

    def test_default_is_flat_ten_for_any_idle(self) -> None:
        """The default config returns a FLAT 10.0 no matter how long the board is idle.

        ``idle_max == base == 10.0`` clamps the back-off curve to a constant, so the
        idle back-off never lengthens the cadence (the operator-requested behaviour).
        """
        # An idle of 100× the base must NOT lengthen the cadence.
        assert next_sleep(last_activity_ts=0.0, now=1000.0) == 10.0
        # A constant 10.0 across a long sweep of idle durations (no growth anywhere).
        for elapsed in range(0, 1000, 7):
            assert next_sleep(last_activity_ts=0.0, now=float(elapsed)) == 10.0


class TestDaemonBaseSeconds:
    """The webhook-fallback cadence selector (ingress-multiproject §5.2)."""

    def test_all_webhook_returns_slow_fallback(self) -> None:
        """An all-webhook daemon polls slowly at the safety-sweep fallback (120 s by default)."""
        from kanbanmate.core.interval import daemon_base_seconds

        assert daemon_base_seconds(["webhook", "webhook"]) == 120.0

    def test_any_polling_pulls_to_tight_cadence(self) -> None:
        """A single polling project pulls the whole daemon to the tight 10 s cadence."""
        from kanbanmate.core.interval import daemon_base_seconds

        assert daemon_base_seconds(["webhook", "polling"]) == 10.0
        assert daemon_base_seconds(["polling"]) == 10.0

    def test_empty_degrades_to_tight(self) -> None:
        """No enabled project → the safe tight default (never the slow fallback)."""
        from kanbanmate.core.interval import daemon_base_seconds

        assert daemon_base_seconds([]) == 10.0

    def test_custom_seconds_honoured(self) -> None:
        from kanbanmate.core.interval import daemon_base_seconds

        assert (
            daemon_base_seconds(["webhook"], polling_seconds=5.0, webhook_fallback_seconds=300.0)
            == 300.0
        )
