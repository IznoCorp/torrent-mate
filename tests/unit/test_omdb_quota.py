"""Tests for OMDB daily-quota tracker — api/metadata/_omdb_quota.py.

Covers: fresh state, safety margin, date reset, mark_exhausted,
custom limit, atomic persist, corrupted state recovery, constructor
validation, persist failure recovery, and typed API (ReservationOutcome,
QuotaStatus).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from personalscraper.api.metadata._omdb_quota import (
    _DEFAULT_LIMIT,
    _SAFETY_MARGIN,
    OmdbQuotaTracker,
    QuotaStatus,
)


def _fresh_tracker(tmp_path: Path, **kwargs: int) -> OmdbQuotaTracker:
    """Build a tracker with a temp state file (no pre-existing state)."""
    state_file = tmp_path / ".omdb-quota.json"
    return OmdbQuotaTracker(state_path=state_file, **kwargs)


class TestFreshState:
    """Tracker with no pre-existing state file."""

    def test_fresh_state_allows_calls(self, tmp_path: Path) -> None:
        """New tracker file → reserve_call returns 'allowed' for first 950 calls."""
        tracker = _fresh_tracker(tmp_path)
        for _ in range(_DEFAULT_LIMIT - _SAFETY_MARGIN):
            assert tracker.reserve_call() == "allowed"

    def test_safety_margin_blocks_last_50(self, tmp_path: Path) -> None:
        """After 950 reserves, next reserve returns 'skipped_safety_margin'."""
        tracker = _fresh_tracker(tmp_path)
        for _ in range(_DEFAULT_LIMIT - _SAFETY_MARGIN):
            assert tracker.reserve_call() == "allowed"
        # The 951st call should be blocked
        assert tracker.reserve_call() == "skipped_safety_margin"
        # Subsequent calls also blocked (marked exhausted)
        assert tracker.reserve_call() == "skipped_marked_exhausted"

    def test_status_reflects_state(self, tmp_path: Path) -> None:
        """status() returns a QuotaStatus with expected values."""
        tracker = _fresh_tracker(tmp_path)
        for _ in range(10):
            tracker.reserve_call()
        s = tracker.status()
        # freezegun is not in dev-deps (checked pyproject.toml). Fall back to a
        # ±1 day tolerance to avoid flakiness if the test straddles UTC midnight
        # between the tracker writes and the assertion read.
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(tz=timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        assert s.date in {today, yesterday}
        assert s.count == 10
        assert s.limit == _DEFAULT_LIMIT
        assert s.safety_margin == _SAFETY_MARGIN
        assert s.exhausted is False
        assert s.remaining_before_margin == _DEFAULT_LIMIT - _SAFETY_MARGIN - 10

    def test_status_to_json_dict(self, tmp_path: Path) -> None:
        """QuotaStatus.to_json_dict() produces a JSON-serializable dict."""
        tracker = _fresh_tracker(tmp_path)
        tracker.reserve_call()
        d = tracker.status().to_json_dict()
        assert isinstance(d, dict)
        assert d["count"] == 1
        assert d["exhausted"] is False
        json.dumps(d)  # does not raise


class TestDateReset:
    """Day-change (UTC midnight) resets the counter."""

    def test_date_change_resets(self, tmp_path: Path) -> None:
        """State from 'yesterday' → reserve_call resets and returns 'allowed'."""
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
        assert tracker.reserve_call() == "allowed"
        s = tracker.status()
        assert s.date == datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        assert s.count == 1

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
        assert tracker.reserve_call() == "allowed"
        assert tracker.status().exhausted is False


class TestMarkExhausted:
    """Force-exhaustion via mark_exhausted()."""

    def test_mark_exhausted_forces_skip(self, tmp_path: Path) -> None:
        """mark_exhausted → next reserve returns 'skipped_marked_exhausted'."""
        tracker = _fresh_tracker(tmp_path)
        assert tracker.reserve_call() == "allowed"
        tracker.mark_exhausted("test forced exhaustion")
        assert tracker.reserve_call() == "skipped_marked_exhausted"

    def test_mark_exhausted_persists(self, tmp_path: Path) -> None:
        """Exhausted state survives tracker re-creation."""
        state_file = tmp_path / ".omdb-quota.json"
        tracker1 = OmdbQuotaTracker(state_path=state_file)
        tracker1.mark_exhausted("test")
        # Re-create from the same file
        tracker2 = OmdbQuotaTracker(state_path=state_file)
        assert tracker2.reserve_call() == "skipped_marked_exhausted"


class TestCustomLimit:
    """Configurable daily limit via constructor."""

    def test_custom_limit_via_constructor(self, tmp_path: Path) -> None:
        """limit=100 → blocks after 50 (safety margin still 50)."""
        tracker = _fresh_tracker(tmp_path, limit=100)
        for _ in range(50):  # 100 - 50 = 50
            assert tracker.reserve_call() == "allowed"
        assert tracker.reserve_call() == "skipped_safety_margin"

    def test_custom_safety_margin(self, tmp_path: Path) -> None:
        """safety_margin=10 with limit=50 → blocks after 40."""
        tracker = _fresh_tracker(tmp_path, limit=50, safety_margin=10)
        for _ in range(40):
            assert tracker.reserve_call() == "allowed"
        assert tracker.reserve_call() == "skipped_safety_margin"


class TestAtomicPersist:
    """State file is written atomically and survives reload."""

    def test_atomic_persist_survives_reload(self, tmp_path: Path) -> None:
        """Reserved counts persist correctly across tracker re-creation."""
        state_file = tmp_path / ".omdb-quota.json"
        tracker1 = OmdbQuotaTracker(state_path=state_file)
        for _ in range(42):
            assert tracker1.reserve_call() == "allowed"
        # Re-create from the same file
        tracker2 = OmdbQuotaTracker(state_path=state_file)
        s = tracker2.status()
        assert s.count == 42
        assert s.exhausted is False

    def test_no_stale_tmp_file_left(self, tmp_path: Path) -> None:
        """After persist, only the .json file exists (not .json.tmp)."""
        tracker = _fresh_tracker(tmp_path)
        for _ in range(5):
            tracker.reserve_call()
        # Check only the real state file exists
        files = list(tmp_path.glob(".omdb-quota*"))
        assert len(files) == 1
        assert files[0].suffix == ".json"

    def test_persist_delegates_to_atomic_write_json(self, tmp_path: Path) -> None:
        """_persist delegates the actual write to atomic_write_json.

        Regression test for 11.1 M1: the whole point of the fix is that
        _persist no longer does write_text + os.replace itself. Pinning
        the delegation prevents future inlining.
        """
        from unittest.mock import MagicMock, patch

        tracker = _fresh_tracker(tmp_path)
        # Trigger _persist via reserve_call so state has real data.
        tracker.reserve_call()

        with patch(
            "personalscraper.api.metadata._omdb_quota.atomic_write_json",
            MagicMock(),
        ) as mock_write:
            tracker._persist()

        mock_write.assert_called_once()
        args, _ = mock_write.call_args
        assert args[0] == tracker._state_path
        data = args[1]
        assert isinstance(data, dict)
        assert "date" in data
        assert "count" in data
        assert "limit" in data
        assert "exhausted" in data


class TestCorruptedState:
    """Corrupted JSON in state file → trackers resets gracefully + warns."""

    def test_state_file_corruption_resets(self, tmp_path: Path) -> None:
        """Corrupted JSON → fresh state with today's date and count=0."""
        state_file = tmp_path / ".omdb-quota.json"
        state_file.write_text("this is not valid json {{{")
        tracker = OmdbQuotaTracker(state_path=state_file)
        assert tracker.reserve_call() == "allowed"
        s = tracker.status()
        assert s.date == datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        assert s.count == 1  # the call we just reserved

    def test_state_file_wrong_shape_resets(self, tmp_path: Path) -> None:
        """Valid JSON but missing required keys → fresh state."""
        state_file = tmp_path / ".omdb-quota.json"
        state_file.write_text(json.dumps({"foo": "bar"}))
        tracker = OmdbQuotaTracker(state_path=state_file)
        assert tracker.reserve_call() == "allowed"
        s = tracker.status()
        assert s.count == 1

    def test_state_file_disappears_between_exists_and_read(self, tmp_path: Path, monkeypatch) -> None:
        """TOCTOU: file vanishes after exists() but before read_text() → fall back to fresh state.

        Without OSError in the except tuple, OmdbQuotaTracker(...) would
        crash at construction time if an external process (cleanup cron,
        operator rm) raced with _load_state. The recovery path treats a
        vanished file the same as invalid JSON.
        """
        state_file = tmp_path / ".omdb-quota.json"
        state_file.write_text(json.dumps({"date": "2026-01-01", "count": 10, "limit": 1000, "exhausted": False}))

        _real_read_text = Path.read_text

        def _vanishing_read_text(self: Path, *args, **kwargs):
            if self == state_file:
                raise FileNotFoundError(f"vanished: {self}")
            return _real_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", _vanishing_read_text)

        # Must not raise — fall back to fresh state for today.
        tracker = OmdbQuotaTracker(state_path=state_file)
        s = tracker.status()
        assert s.date == datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        assert s.count == 0

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
        assert tracker.reserve_call() == "allowed"


class TestSameDayPersistence:
    """Same-day runs share the quota budget."""

    def test_same_day_accumulates_count(self, tmp_path: Path) -> None:
        """A second run on the same day continues from the first run's count."""
        state_file = tmp_path / ".omdb-quota.json"
        # Run 1: make 600 calls
        tracker1 = OmdbQuotaTracker(state_path=state_file)
        for _ in range(600):
            assert tracker1.reserve_call() == "allowed"
        # Run 2 (same day): should see count=600 and continue
        tracker2 = OmdbQuotaTracker(state_path=state_file)
        assert tracker2.status().count == 600
        # Can still make (limit - margin - 600) more calls
        for _ in range(_DEFAULT_LIMIT - _SAFETY_MARGIN - 600):
            assert tracker2.reserve_call() == "allowed"
        assert tracker2.reserve_call() == "skipped_safety_margin"


class TestConstructorValidation:
    """Constructor validates safety_margin against limit."""

    def test_safety_margin_zero_is_valid(self, tmp_path: Path) -> None:
        """safety_margin=0 → valid (no margin, exact limit)."""
        tracker = _fresh_tracker(tmp_path, limit=10, safety_margin=0)
        assert tracker.status().safety_margin == 0

    def test_safety_margin_equal_to_limit_raises(self, tmp_path: Path) -> None:
        """safety_margin == limit → ValueError."""
        with pytest.raises(ValueError, match="safety_margin"):
            _fresh_tracker(tmp_path, limit=100, safety_margin=100)

    def test_safety_margin_exceeds_limit_raises(self, tmp_path: Path) -> None:
        """safety_margin > limit → ValueError."""
        with pytest.raises(ValueError, match="safety_margin"):
            _fresh_tracker(tmp_path, limit=100, safety_margin=200)


class TestPersistFailure:
    """OSError during _persist → in-memory state reverts correctly."""

    def test_increment_reverted_on_persist_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Count reverted when _persist raises OSError after increment."""
        from personalscraper.api.metadata import _omdb_quota as _mod

        tracker = _fresh_tracker(tmp_path)
        # Make one successful call first (this calls _persist once).
        assert tracker.reserve_call() == "allowed"
        assert tracker.status().count == 1

        # Fail the NEXT _persist (i.e. the second overall, first after patching).
        _real_persist = _mod.OmdbQuotaTracker._persist
        call_count = 1  # the first reserve_call already called _persist once

        def _failing_persist(self: _mod.OmdbQuotaTracker) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise OSError("Disk full")
            _real_persist(self)

        monkeypatch.setattr(_mod.OmdbQuotaTracker, "_persist", _failing_persist)

        outcome = tracker.reserve_call()
        # Should return a skip outcome since persist failed.
        assert outcome != "allowed"
        # In-memory count should still be 1 (reverted).
        assert tracker.status().count == 1

    def test_mark_exhausted_reverted_on_persist_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exhausted reverted when _persist raises OSError in mark_exhausted."""
        from personalscraper.api.metadata import _omdb_quota as _mod

        tracker = _fresh_tracker(tmp_path)

        _real_persist = _mod.OmdbQuotaTracker._persist
        persist_calls = 0

        def _failing_persist(self: _mod.OmdbQuotaTracker) -> None:
            nonlocal persist_calls
            persist_calls += 1
            if persist_calls == 1:
                raise OSError("Disk full")
            _real_persist(self)

        monkeypatch.setattr(_mod.OmdbQuotaTracker, "_persist", _failing_persist)

        tracker.mark_exhausted("test")
        # exhausted should be False (reverted).
        assert tracker.status().exhausted is False
        # Should still be able to reserve calls.
        assert tracker.reserve_call() == "allowed"


class TestTypedApi:
    """ReservationOutcome and QuotaStatus typed contracts."""

    def test_reserve_allowed_return_value(self, tmp_path: Path) -> None:
        """reserve_call returns 'allowed' string literal when quota available."""
        tracker = _fresh_tracker(tmp_path)
        assert tracker.reserve_call() == "allowed"

    def test_reserve_skipped_marked_exhausted(self, tmp_path: Path) -> None:
        """After mark_exhausted, reserve_call returns 'skipped_marked_exhausted'."""
        tracker = _fresh_tracker(tmp_path)
        tracker.mark_exhausted("test")
        assert tracker.reserve_call() == "skipped_marked_exhausted"

    def test_reserve_skipped_safety_margin(self, tmp_path: Path) -> None:
        """At safety margin, reserve_call returns 'skipped_safety_margin'."""
        tracker = _fresh_tracker(tmp_path)
        for _ in range(_DEFAULT_LIMIT - _SAFETY_MARGIN):
            assert tracker.reserve_call() == "allowed"
        assert tracker.reserve_call() == "skipped_safety_margin"

    def test_quota_status_is_namedtuple(self, tmp_path: Path) -> None:
        """status() returns a QuotaStatus NamedTuple."""
        tracker = _fresh_tracker(tmp_path)
        s = tracker.status()
        assert isinstance(s, QuotaStatus)
        assert hasattr(s, "date")
        assert hasattr(s, "count")
        assert hasattr(s, "limit")
        assert hasattr(s, "safety_margin")
        assert hasattr(s, "remaining_before_margin")
        assert hasattr(s, "exhausted")
