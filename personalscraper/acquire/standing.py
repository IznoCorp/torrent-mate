"""The ratio standing: where a tracker's ratio stands against its own economy (K3 DESIGN § 2.10).

One derivation, read by the grab orchestrator (it fills ``TrackerResult.tracker_ratio_state``
before ``rank()``) and by the ranking preview, so the preview can never show a state the engine
would not score. The standing is derived from facts the engine already holds — the observed ratio
in ``ratio_state`` and the tracker's ``economy`` block — never fetched, never computed from the
tracker's account statistics (those are K5's).

Dormant until K5 (O-8 A): nothing writes ``ratio_state`` yet, so every tracker's standing reads
``None`` and no ranking score moves. Even once a ratio is written, a score moves only when the
operator names ``tracker_ratio_state`` in a ranking criterion; no default criterion ships.

Import direction: ``acquire/`` imports ``conf/`` downward only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from personalscraper.acquire._ports import RatioSubStore
    from personalscraper.conf.models.api_config import TrackerEconomyConfig

__all__ = ["RatioStanding", "TrackerRatioState"]

#: The members of a tracker's standing — the contract's ``trackerRatioState`` enum, minus its null.
TrackerRatioState = Literal["under_floor", "under_target", "comfortable"]


class RatioStanding:
    """A tracker's ratio read against that tracker's own economy.

    Holds the ``ratio_state`` reader and the economy map and answers per tracker; the pure
    rule itself is :meth:`classify`.
    """

    def __init__(self, ratio: RatioSubStore, economy: Mapping[str, TrackerEconomyConfig]) -> None:
        """Hold the two sources of a standing.

        Args:
            ratio: The ``ratio_state`` reader (``store.ratio``); read on every :meth:`of`, so a
                ratio written after construction is seen by the next call.
            economy: Tracker name → its ``economy`` block, for the trackers that declare one.
        """
        self._ratio = ratio
        self._economy = economy

    @staticmethod
    def classify(observed: float | None, economy: TrackerEconomyConfig | None) -> TrackerRatioState | None:
        """Classify an observed ratio against an economy.

        Args:
            observed: The last observed ratio, or ``None`` when none was ever recorded. NaN is no
                observation (it compares false to every threshold); ``inf`` — an account that never
                downloaded — is a ratio like any other.
            economy: The tracker's economy block, or ``None`` when it declares none.

        Returns:
            ``"under_floor"`` below ``min_ratio``; ``"under_target"`` from ``min_ratio`` up to
            below ``target_ratio``; ``"comfortable"`` from ``target_ratio`` up; ``None`` when there
            is no economy (no policy) or no observed ratio (no fact).
        """
        if economy is None or observed is None or math.isnan(observed):
            return None
        if observed < economy.min_ratio:
            return "under_floor"
        if observed < economy.target_ratio:
            return "under_target"
        return "comfortable"

    def of(self, tracker: str) -> TrackerRatioState | None:
        """Say where a tracker's ratio stands now.

        Args:
            tracker: The tracker's name, as ``ratio_state`` and the economy map key it.

        Returns:
            The standing, or ``None`` when the tracker declares no economy or has no recorded ratio.
        """
        economy = self._economy.get(tracker)
        if economy is None:
            # No policy: skip the store read, a ratio alone says nothing without a floor.
            return None
        state = self._ratio.get(tracker)
        return self.classify(state.observed_ratio if state is not None else None, economy)
