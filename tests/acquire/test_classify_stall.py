"""reswitch Phase 2 — classify_stall verdict matrix.

The auto-reswitch acts ONLY on a ``STALLED_DEAD`` verdict, so the boundary
between dead / recoverable / healthy must be exact: a false ``STALLED_DEAD``
throws away a download that would have resumed; a missed one leaves a silent
« en cours » lie. This exercises every branch.
"""

from __future__ import annotations

import pytest

from personalscraper.acquire._stall import StallVerdict, classify_stall
from personalscraper.api.torrent._base import TorrentItem

_DEAD_AFTER = 3600.0  # 1 h hard deadline for these cases.


def _item(
    *,
    state: str,
    progress: float = 0.0,
    swarm_seeds: int | None = None,
    error_reason: str | None = None,
) -> TorrentItem:
    """A TorrentItem carrying only the fields classify_stall reads."""
    return TorrentItem(
        hash="h",
        name="n",
        size_bytes=1,
        progress=progress,
        state=state,
        swarm_seeds=swarm_seeds,
        error_reason=error_reason,
    )


class TestBroken:
    """A broken torrent (error / missingFiles) is always dead, whatever else."""

    def test_error_reason_is_dead_even_when_downloading(self) -> None:
        """An error_reason ⇒ dead regardless of progress/swarm."""
        item = _item(state="downloading", progress=0.5, swarm_seeds=50, error_reason="boom")
        assert classify_stall(item, 1.0, dead_after_s=_DEAD_AFTER) is StallVerdict.STALLED_DEAD


class TestHealthy:
    """Non-stalled states are healthy regardless of progress/swarm."""

    @pytest.mark.parametrize("state", ["downloading", "uploading", "forcedDL", "stalledUP", "checkingDL"])
    def test_non_stalled_states_are_healthy(self, state: str) -> None:
        """Any non-stalled download/seed state is HEALTHY, even with 0 swarm."""
        item = _item(state=state, progress=0.0, swarm_seeds=0)
        assert classify_stall(item, 999_999.0, dead_after_s=_DEAD_AFTER) is StallVerdict.HEALTHY


class TestStalledDead:
    """Stalled + (dead swarm | past deadline) ⇒ dead."""

    def test_stalled_zero_progress_dead_swarm_is_dead(self) -> None:
        """StalledDL + 0 % + 0 known seeds ⇒ dead now (never started, no swarm)."""
        item = _item(state="stalledDL", progress=0.0, swarm_seeds=0)
        assert classify_stall(item, 60.0, dead_after_s=_DEAD_AFTER) is StallVerdict.STALLED_DEAD

    def test_metadl_zero_progress_dead_swarm_is_dead(self) -> None:
        """A metaDL magnet with a dead swarm never resolves ⇒ dead."""
        item = _item(state="metaDL", progress=0.0, swarm_seeds=0)
        assert classify_stall(item, 60.0, dead_after_s=_DEAD_AFTER) is StallVerdict.STALLED_DEAD

    def test_stalled_past_deadline_is_dead_even_with_unknown_swarm(self) -> None:
        """Past the hard deadline ⇒ dead even when swarm health is unknown."""
        item = _item(state="stalledDL", progress=0.0, swarm_seeds=None)
        assert classify_stall(item, _DEAD_AFTER + 1, dead_after_s=_DEAD_AFTER) is StallVerdict.STALLED_DEAD

    def test_stalled_past_deadline_is_dead_even_with_live_swarm(self) -> None:
        """Stuck past the deadline despite a 'live' swarm that never delivers ⇒ dead."""
        item = _item(state="stalledDL", progress=0.0, swarm_seeds=30)
        assert classify_stall(item, _DEAD_AFTER + 1, dead_after_s=_DEAD_AFTER) is StallVerdict.STALLED_DEAD


class TestStalledRecoverable:
    """Stalled but young and swarm alive-or-unknown ⇒ wait, do not switch."""

    def test_stalled_young_live_swarm_is_recoverable(self) -> None:
        """Young stall + a live swarm ⇒ give it time (recoverable)."""
        item = _item(state="stalledDL", progress=0.0, swarm_seeds=10)
        assert classify_stall(item, 60.0, dead_after_s=_DEAD_AFTER) is StallVerdict.STALLED_RECOVERABLE

    def test_stalled_young_unknown_swarm_is_recoverable(self) -> None:
        """Unknown (None) swarm must NOT trigger an early switch — only a hard 0."""
        item = _item(state="stalledDL", progress=0.0, swarm_seeds=None)
        assert classify_stall(item, 60.0, dead_after_s=_DEAD_AFTER) is StallVerdict.STALLED_RECOVERABLE

    def test_stalled_with_partial_progress_is_recoverable_while_young(self) -> None:
        """Progress > 0 means bytes flowed; a young partial stall may still resume."""
        item = _item(state="stalledDL", progress=0.4, swarm_seeds=0)
        assert classify_stall(item, 60.0, dead_after_s=_DEAD_AFTER) is StallVerdict.STALLED_RECOVERABLE
