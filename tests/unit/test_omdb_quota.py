"""Tests for OMDB daily-quota tracker — api/metadata/_omdb_quota.py.

Covers: fresh state, safety margin, date reset, mark_exhausted,
custom limit, atomic persist, and corrupted state recovery.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from personalscraper.api.metadata._omdb_quota import (
    _DEFAULT_LIMIT,
    _SAFETY_MARGIN,
    OmdbQuotaTracker,
)


def _fresh_tracker(tmp_path: Path, **kwargs: int) -> OmdbQuotaTracker:
    """Build a tracker with a temp state file (no pre-existing state)."""
    state_file = tmp_path / ".omdb-quota.json"
    return OmdbQuotaTracker(state_path=state_file, **kwargs)


class TestFreshState:
    """Tracker with no pre-existing state file."""

    def test_fresh_state_allows_calls(self, tmp_path: Path) -> None:
        """New tracker file → reserve_call returns True for first 950 calls."""
        tracker = _fresh_tracker(tmp_path)
        for _ in range(_DEFAULT_LIMIT - _SAFETY_MARGIN):
            assert tracker.reserve_call() is True

    def test_safety_margin_blocks_last_50(self, tmp_path: Path) -> None:
        """After 950 reserves, next reserve returns False (safety margin)."""
        tracker = _fresh_tracker(tmp_path)
        for _ in range(_DEFAULT_LIMIT - _SAFETY_MARGIN):
            assert tracker.reserve_call() is True
        # The 951st call should be blocked
        assert tracker.reserve_call() is False
        # Subsequent calls also blocked
        assert tracker.reserve_call() is False

    def test_status_reflects_state(self, tmp_path: Path) -> None:
        """status() returns a dict with expected keys and values."""
        tracker = _fresh_tracker(tmp_path)
        for _ in range(10):
            tracker.reserve_call()
        s = tracker.status()
        assert s["date"] == datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        assert s["count"] == 10
        assert s["limit"] == _DEFAULT_LIMIT
        assert s["safety_margin"] == _SAFETY_MARGIN
        assert s["exhausted"] is False
        assert s["remaining_before_margin"] == _DEFAULT_LIMIT - _SAFETY_MARGIN - 10


class TestDateReset:
    """Day-change (UTC midnight) resets the counter."""

    def test_date_change_resets(self, tmp_path: Path) -> None:
        """State from 'yesterday' → reserve_call resets and returns True."""
        state_file = tmp_path / ".omdb-quota.json"
        yesterday = (datetime.now(tz=timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        # Pre-seed a near-exhausted state from yesterday
        state_file.write_text(
            json.dumps(
                {
                    "date": yesterday,
                    "count": 998,
                    "limit": _DEFAULT_LIMIT,
                    "exhausted": False,
                }
            )
        )
        tracker = OmdbQuotaTracker(state_path=state_file)
        # First reserve should reset to today and allow the call
        assert tracker.reserve_call() is True
        s = tracker.status()
        assert s["date"] == datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        assert s["count"] == 1

    def test_date_change_clears_exhausted(self, tmp_path: Path) -> None:
        """Exhausted flag from yesterday is cleared on day change."""
        state_file = tmp_path / ".omdb-quota.json"
        yesterday = (datetime.now(tz=timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        state_file.write_text(
            json.dumps(
                {
                    "date": yesterday,
                    "count": 1000,
                    "limit": _DEFAULT_LIMIT,
                    "exhausted": True,
                }
            )
        )
        tracker = OmdbQuotaTracker(state_path=state_file)
        assert tracker.reserve_call() is True
        assert tracker.status()["exhausted"] is False


class TestMarkExhausted:
    """Force-exhaustion via mark_exhausted()."""

    def test_mark_exhausted_forces_skip(self, tmp_path: Path) -> None:
        """mark_exhausted → next reserve returns False even if count is 0."""
        tracker = _fresh_tracker(tmp_path)
        assert tracker.reserve_call() is True  # count goes to 1
        tracker.mark_exhausted("test forced exhaustion")
        assert tracker.reserve_call() is False

    def test_mark_exhausted_persists(self, tmp_path: Path) -> None:
        """Exhausted state survives tracker re-creation."""
        state_file = tmp_path / ".omdb-quota.json"
        tracker1 = OmdbQuotaTracker(state_path=state_file)
        tracker1.mark_exhausted("test")
        # Re-create from the same file
        tracker2 = OmdbQuotaTracker(state_path=state_file)
        assert tracker2.reserve_call() is False


class TestCustomLimit:
    """Configurable daily limit via constructor."""

    def test_custom_limit_via_constructor(self, tmp_path: Path) -> None:
        """limit=100 → blocks after 50 (safety margin still 50)."""
        tracker = _fresh_tracker(tmp_path, limit=100)
        for _ in range(50):  # 100 - 50 = 50
            assert tracker.reserve_call() is True
        assert tracker.reserve_call() is False

    def test_custom_safety_margin(self, tmp_path: Path) -> None:
        """safety_margin=10 with limit=50 → blocks after 40."""
        tracker = _fresh_tracker(tmp_path, limit=50, safety_margin=10)
        for _ in range(40):
            assert tracker.reserve_call() is True
        assert tracker.reserve_call() is False


class TestAtomicPersist:
    """State file is written atomically and survives reload."""

    def test_atomic_persist_survives_reload(self, tmp_path: Path) -> None:
        """Reserved counts persist correctly across tracker re-creation."""
        state_file = tmp_path / ".omdb-quota.json"
        tracker1 = OmdbQuotaTracker(state_path=state_file)
        for _ in range(42):
            assert tracker1.reserve_call() is True
        # Re-create from the same file
        tracker2 = OmdbQuotaTracker(state_path=state_file)
        s = tracker2.status()
        assert s["count"] == 42
        assert s["exhausted"] is False

    def test_no_stale_tmp_file_left(self, tmp_path: Path) -> None:
        """After persist, only the .json file exists (not .json.tmp)."""
        tracker = _fresh_tracker(tmp_path)
        for _ in range(5):
            tracker.reserve_call()
        # Check only the real state file exists
        files = list(tmp_path.glob(".omdb-quota*"))
        assert len(files) == 1
        assert files[0].suffix == ".json"


class TestCorruptedState:
    """Corrupted JSON in state file → trackers resets gracefully + warns."""

    def test_state_file_corruption_resets(self, tmp_path: Path) -> None:
        """Corrupted JSON → fresh state with today's date and count=0."""
        state_file = tmp_path / ".omdb-quota.json"
        state_file.write_text("this is not valid json {{{")
        tracker = OmdbQuotaTracker(state_path=state_file)
        assert tracker.reserve_call() is True
        s = tracker.status()
        assert s["date"] == datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        assert s["count"] == 1  # the call we just reserved

    def test_state_file_wrong_shape_resets(self, tmp_path: Path) -> None:
        """Valid JSON but missing required keys → fresh state."""
        state_file = tmp_path / ".omdb-quota.json"
        state_file.write_text(json.dumps({"foo": "bar"}))
        tracker = OmdbQuotaTracker(state_path=state_file)
        assert tracker.reserve_call() is True
        s = tracker.status()
        assert s["count"] == 1

    def test_state_file_bad_types_resets(self, tmp_path: Path) -> None:
        """Count is a string instead of int → fresh state."""
        state_file = tmp_path / ".omdb-quota.json"
        state_file.write_text(
            json.dumps(
                {
                    "date": "2026-01-01",
                    "count": "not_a_number",
                    "limit": 1000,
                    "exhausted": False,
                }
            )
        )
        tracker = OmdbQuotaTracker(state_path=state_file)
        assert tracker.reserve_call() is True


class TestSameDayPersistence:
    """Same-day runs share the quota budget."""

    def test_same_day_accumulates_count(self, tmp_path: Path) -> None:
        """A second run on the same day continues from the first run's count."""
        state_file = tmp_path / ".omdb-quota.json"
        # Run 1: make 600 calls
        tracker1 = OmdbQuotaTracker(state_path=state_file)
        for _ in range(600):
            assert tracker1.reserve_call() is True
        # Run 2 (same day): should see count=600 and continue
        tracker2 = OmdbQuotaTracker(state_path=state_file)
        assert tracker2.status()["count"] == 600
        # Can still make (limit - margin - 600) more calls
        for _ in range(_DEFAULT_LIMIT - _SAFETY_MARGIN - 600):
            assert tracker2.reserve_call() is True
        assert tracker2.reserve_call() is False  # margin reached
