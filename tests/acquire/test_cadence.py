"""Tests for acquire/cadence.py — Hot/Warm/Cold tier + cutoff predicates."""

from __future__ import annotations

# Canonical cadence for tests: Hot <72h/2h, Warm <14d/1d, Cold <30d/7d, cutoff=30d
HOT_S = 2 * 3600
WARM_S = 24 * 3600
COLD_S = 7 * 24 * 3600
HOT_MAX = 72 * 3600
WARM_MAX = 14 * 24 * 3600
COLD_MAX = 30 * 24 * 3600
NOW = 1_000_000


def _canon():
    from personalscraper.acquire.cadence import Cadence, CadenceTier

    return Cadence(
        tiers=(
            CadenceTier(max_age_s=HOT_MAX, interval_s=HOT_S),
            CadenceTier(max_age_s=WARM_MAX, interval_s=WARM_S),
            CadenceTier(max_age_s=COLD_MAX, interval_s=COLD_S),
        ),
        cutoff_s=COLD_MAX,
    )


def test_is_due_hot_first_search():
    """age=0, last_search_at=None → due immediately (Hot tier)."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=NOW, last_search_at=None) is True


def test_is_due_hot_too_soon():
    """age=1h, last_search_at=30min ago → NOT due (Hot interval=2h)."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - 3600
    last = NOW - 1800
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is False


def test_is_due_hot_warm_boundary_minus1s():
    """age=72h-1s → still Hot tier, interval=2h."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (HOT_MAX - 1)
    last = NOW - HOT_S - 1  # just past interval → due
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_warm_boundary_plus1s():
    """age=72h+1s → Warm tier, interval=1d."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (HOT_MAX + 1)
    last = NOW - WARM_S - 1  # just past 1d interval → due
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_warm_cold_boundary_minus1s():
    """age=14d-1s → still Warm, interval=1d."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (WARM_MAX - 1)
    last = NOW - WARM_S - 1
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_cold_boundary_plus1s():
    """age=14d+1s → Cold tier, interval=7d."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (WARM_MAX + 1)
    last = NOW - COLD_S - 1
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_cold_too_soon():
    """age=15d, last_search_at=3d ago → NOT due (Cold interval=7d)."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (15 * 24 * 3600)
    last = NOW - (3 * 24 * 3600)
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is False


def test_is_past_cutoff_false_before():
    """age=30d-1s → NOT past cutoff."""
    from personalscraper.acquire.cadence import is_past_cutoff

    assert is_past_cutoff(_canon(), now=NOW, enqueued_at=NOW - (COLD_MAX - 1)) is False


def test_is_past_cutoff_true_at():
    """age=30d exactly → past cutoff."""
    from personalscraper.acquire.cadence import is_past_cutoff

    assert is_past_cutoff(_canon(), now=NOW, enqueued_at=NOW - COLD_MAX) is True


def test_is_past_cutoff_true_after():
    """age=30d+1s → past cutoff."""
    from personalscraper.acquire.cadence import is_past_cutoff

    assert is_past_cutoff(_canon(), now=NOW, enqueued_at=NOW - (COLD_MAX + 1)) is True


def test_is_due_returns_false_past_cutoff():
    """is_due_by_cadence returns False when past cutoff (don't search, abandon)."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (COLD_MAX + 1)
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=None) is False
