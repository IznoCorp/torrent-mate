"""Unit tests for acquire/domain.py frozen value objects."""

from __future__ import annotations

import time

import pytest

from personalscraper.acquire.domain import (
    FollowedSeries,
    RatioState,
    SeedObligation,
    WantedItem,
)
from personalscraper.core.identity import MediaRef


def _ref(tvdb_id: int = 1) -> MediaRef:
    """Create a minimal MediaRef with the given tvdb_id."""
    return MediaRef(tvdb_id=tvdb_id)


def test_followed_series_frozen() -> None:
    """FollowedSeries is a frozen dataclass — mutation raises."""
    fs = FollowedSeries(media_ref=_ref(), title="TestShow", added_at=int(time.time()))
    with pytest.raises((AttributeError, TypeError)):
        fs.title = "other"  # type: ignore[misc]


def test_wanted_item_valid_kinds() -> None:
    """WantedItem accepts valid kind/status literals."""
    wi = WantedItem(
        media_ref=_ref(),
        kind="episode",
        status="pending",
        enqueued_at=int(time.time()),
    )
    assert wi.kind == "episode"


def test_wanted_item_rejects_invalid_kind() -> None:
    """WantedItem raises ValueError for an invalid kind."""
    with pytest.raises((ValueError, TypeError)):
        WantedItem(
            media_ref=_ref(),
            kind="invalid",  # type: ignore[arg-type]
            status="pending",
            enqueued_at=int(time.time()),
        )


def test_seed_obligation_fields() -> None:
    """SeedObligation nullable fields default to None."""
    so = SeedObligation(
        info_hash="abc123",
        source_tracker="lacale",
        min_seed_time_s=72 * 3600,
        min_ratio=1.0,
        added_at=int(time.time()),
    )
    assert so.dispatched_path is None
    assert so.satisfied_at is None
    assert so.breached_at is None
    assert so.released_at is None


def test_seed_obligation_rejects_negative_min_seed_time() -> None:
    """T1: a negative min_seed_time_s raises ValueError.

    A negative floor would make ``seed_time_elapsed >= min_seed_time_s``
    trivially true in DeleteAuthority.may_delete, silently passing the HnR
    guard for a live seed.
    """
    with pytest.raises(ValueError, match="min_seed_time_s"):
        SeedObligation(
            info_hash="abc123",
            source_tracker="lacale",
            min_seed_time_s=-1,
            min_ratio=1.0,
            added_at=int(time.time()),
        )


def test_seed_obligation_rejects_negative_min_ratio() -> None:
    """T1: a negative min_ratio raises ValueError."""
    with pytest.raises(ValueError, match="min_ratio"):
        SeedObligation(
            info_hash="abc123",
            source_tracker="lacale",
            min_seed_time_s=72 * 3600,
            min_ratio=-0.5,
            added_at=int(time.time()),
        )


def test_seed_obligation_accepts_zero_floors() -> None:
    """T1: zero is a valid (non-negative) floor — no exception."""
    so = SeedObligation(
        info_hash="abc123",
        source_tracker="lacale",
        min_seed_time_s=0,
        min_ratio=0.0,
        added_at=int(time.time()),
    )
    assert so.min_seed_time_s == 0
    assert so.min_ratio == 0.0


def test_ratio_state_fields() -> None:
    """RatioState stores per-tracker ratio state."""
    rs = RatioState(
        tracker_name="lacale",
        observed_ratio=1.2,
        accumulated_seed_time_s=100000,
        hnr_count=0,
        updated_at=int(time.time()),
    )
    assert rs.hnr_count == 0
