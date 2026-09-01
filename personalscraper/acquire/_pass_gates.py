"""Pre-claim gates shared by the two acquisition passes (D6 split).

Extracted VERBATIM from ``acquire/service.py`` — behaviour, log events and
return values are unchanged; only the module boundary moved. The gates are the
work both passes do BEFORE claiming a row:

- :meth:`PassGatesMixin._apply_cutoff_gate` — recover a stale 'searching' claim,
  then age the item out past the cadence cutoff. Both passes run it.
- :meth:`PassGatesMixin._apply_cadence_gates` — the cutoff gate PLUS the
  cadence-due check. The SEARCH pass alone runs it: cadence spaces the
  re-verification of an unavailable item, while an already-available item is
  taken at the next tick whatever its tier.

Mixed into :class:`~personalscraper.acquire.service.AcquisitionService` rather
than injected, so the extraction is a pure move: every ``self.`` reference in
the moved bodies still resolves to the same object it did inline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.acquire._season_fallback import fall_back_to_episodes
from personalscraper.acquire.cadence import is_due_by_cadence, is_past_cutoff
from personalscraper.acquire.desired import (
    QualityProfile,
    effective_quality,
    quality_profile_from_json,
    source_criteria_from_json,
)
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import WantedAbandoned
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.cadence import Cadence
    from personalscraper.acquire.service import _GateVerdict
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.service")

#: Stale-searching threshold: items stuck in 'searching' longer than this are
#: eligible for recovery (a process killed mid-grab before any status write).
#:
#: SINGLE definition on purpose. Two consumers read it and they MUST agree:
#: ``AcquisitionService._build_queue`` uses it to SELECT the stale rows
#: (``list_stale_searching(older_than=now - _STALE_THRESHOLD_S)``) and
#: :meth:`PassGatesMixin._apply_cutoff_gate` uses it to RECOVER them
#: (``reclaim_stale_searching(id, now - _STALE_THRESHOLD_S)``). The D6 split
#: briefly left a copy in each module; a drift between them would list rows the
#: recovery then refuses — every one of them silently skipped.
_STALE_THRESHOLD_S = 3600  # 1 hour


class PassGatesMixin:
    """The pre-claim gates, shared by the search and grab passes."""

    _store: AcquireStore
    _event_bus: EventBus

    def _apply_cutoff_gate(self, item: WantedItem, now: int, *, cadence: Cadence) -> _GateVerdict:
        """Recover a stale claim, then age the item out past the cutoff (BOTH passes).

        This is the gate the GRAB pass keeps. It recovers a stale 'searching'
        row back to 'pending' (its claim would otherwise fail), then abandons
        the item if it is past the cadence cutoff, keyed on its age from
        ``enqueued_at``. Aging at grab time is what bounds infinite retries on a
        permanently-failing add — without it an item the trackers keep offering
        but the client keeps refusing would be re-grabbed forever.

        Args:
            item: The queued item (``item.id`` non-None).
            now: Unix epoch seconds — the cadence reference clock (also the
                staleness reference for the atomic recovery, so both passes use
                the SAME snapshot the queue was built from).
            cadence: Effective cadence policy for this item.

        Returns:
            ``"proceed"`` when the item may be claimed, ``"abandoned"`` past the
            cutoff, or ``"skipped"`` when a stale 'searching' row could not be
            recovered (it is no longer stale, or it holds a grabbed hash).

        Raises:
            sqlite3.OperationalError: On a DB lock during a status write (the
                callers' per-item isolation handles it).
        """
        assert item.id is not None  # noqa: S101 — ensured by the SELECTs in the callers
        wanted_id = item.id

        # A stale 'searching' row is not 'pending', so its claim would fail.
        # Recover it ATOMICALLY first (one rowcount-gated UPDATE, same shape as
        # the claims), then re-claim — the re-claim re-stamps attempts /
        # last_search_at and re-serialises. The row read here was listed at the
        # top of the pass, so a get-then-set recovery would blindly overwrite
        # whatever a concurrent runner did in between: it reverted COMPLETED
        # grabs back to 'pending' (losing the 'grabbed' status) and handed the
        # same item to two passes at once. Losing the recovery = skip.
        if item.status == "searching" and not self._store.wanted.reclaim_stale_searching(
            wanted_id, now - _STALE_THRESHOLD_S
        ):
            log.debug("acquire.service.stale_recovery_lost", wanted_id=wanted_id)
            return "skipped"

        # --- CUTOFF CHECK (DESIGN §7) ---
        # Past the cadence cutoff → abandon. Emit-after-persist: set_status
        # first, then emit, as everywhere else. The reason ('cutoff_reached') is
        # distinct so consumers can tell an age-out from a terminal verdict. No
        # claim.
        if is_past_cutoff(cadence, now=now, enqueued_at=item.enqueued_at):
            # R6: season kind → fallback instead of plain abandon.
            # Re-enqueue missing episodes individually so the per-episode
            # retry loop can still resolve them after the season-level
            # attempt timed out.
            if item.kind == "season" and item.season is not None and item.followed_id is not None:
                return self._fallback_season(item, now)

            self._store.wanted.set_status(wanted_id, "abandoned")
            self._event_bus.emit(WantedAbandoned(media_ref=item.media_ref, reason="cutoff_reached"))
            log.info("acquire.service.cutoff_abandoned", wanted_id=wanted_id)
            return "abandoned"

        return "proceed"

    # ------------------------------------------------------------------
    # R6: Season Cutoff Fallback
    # ------------------------------------------------------------------

    def _fallback_season(self, item: WantedItem, now: int) -> _GateVerdict:
        """R6: season cutoff → re-enqueue missing episodes, set ``fallback_episodes``.

        Reads the aired catalog to know which episodes exist, re-enqueues
        each one that has no OPEN wanted row yet (a live row is reused as-is
        — never duplicated), transitions the season row to
        ``fallback_episodes``, and emits :class:`SeasonFellBackToEpisodes`
        whose ``reenqueued_count`` is the number of rows actually created.
        The transition itself lives in
        :func:`~personalscraper.acquire._season_fallback.fall_back_to_episodes`
        — shared with the landed-but-incomplete trigger in ``reconcile``, which
        is the same transition reached by a different route.

        Ownership is NOT checked here (Option B from the plan): the detect
        pass already skips owned episodes, so re-enqueuing all aired
        episodes is safe — the cost of creating-then-skipping rows is
        acceptable for a cutoff that fires rarely.

        The caller (``_apply_cutoff_gate``) suppresses its own
        ``WantedAbandoned`` emit — the season row is terminal with a
        different status, so the ``abandoned`` reason would be misleading.

        Args:
            item: The season ``wanted`` row past its cutoff.
            now: Unix epoch seconds (stamps ``enqueued_at`` on the
                re-enqueued rows).

        Returns:
            ``"abandoned"`` — the season row is terminal; the gate outcome
            maps to abandoned for the caller's counter.
        """
        assert item.id is not None  # noqa: S101
        assert item.season is not None  # noqa: S101
        # Episodes left implicit: the cutoff path re-enqueues the WHOLE aired
        # season, ownership unchecked (Option B above).
        reenqueued = fall_back_to_episodes(self._store, item, now=now, event_bus=self._event_bus)
        log.info(
            "acquire.service.season_fallback",
            wanted_id=item.id,
            season=item.season,
            reenqueued=reenqueued,
        )
        return "abandoned"

    def _apply_cadence_gates(self, item: WantedItem, now: int, *, cadence: Cadence) -> _GateVerdict:
        """Run the pre-claim gates of the SEARCH pass (DESIGN §7).

        The cutoff gate (shared, see :meth:`_apply_cutoff_gate`) followed by the
        cadence gate, which belongs to this pass ALONE: cadence is what spaces
        the re-verification of an episode the trackers do not have yet. The grab
        pass never calls this — an item already known available is taken at the
        next tick whatever its tier says.

        - CUTOFF: past the cadence cutoff → abandon → ``"abandoned"``, NO claim.
        - CADENCE: not yet due for its tier interval → stays 'pending' and is
          re-listed next pass → ``"skipped"``, NO claim, NO attempts increment.

        Args:
            item: The queued item (``item.id`` non-None).
            now: Unix epoch seconds — the cadence reference clock.
            cadence: Effective cadence policy for this item.

        Returns:
            ``"proceed"`` when the item may be claimed, else the outcome tag the
            caller returns as-is.

        Raises:
            sqlite3.OperationalError: On a DB lock during a status write (the
                callers' per-item isolation handles it).
        """
        assert item.id is not None  # noqa: S101 — ensured by the SELECTs in the callers
        wanted_id = item.id

        gate = self._apply_cutoff_gate(item, now, cadence=cadence)
        if gate != "proceed":
            return gate

        # --- CADENCE CHECK (DESIGN §7) ---
        # Not yet due for its tier interval → stays 'pending' and is re-listed
        # next run. No claim, no attempts increment.
        if not is_due_by_cadence(cadence, now=now, enqueued_at=item.enqueued_at, last_search_at=item.last_search_at):
            log.debug("acquire.service.cadence_not_due", wanted_id=wanted_id)
            return "skipped"

        return "proceed"

    def _resolve_profile(self, item: WantedItem) -> QualityProfile:
        """Resolve the effective :class:`QualityProfile` for one item.

        Thin instance wrapper over :func:`resolve_effective_profile` so the
        real grab and the ``grab --dry-run`` preview resolve the profile
        IDENTICALLY (no divergence — §9 quality on the whole grab path).

        Args:
            item: The claimed item to resolve a profile for.

        Returns:
            The effective :class:`QualityProfile` for the grab attempt.
        """
        return resolve_effective_profile(self._store, item)


def resolve_effective_profile(store: "AcquireStore", item: WantedItem) -> QualityProfile:
    """Resolve the effective :class:`QualityProfile` for one wanted item.

    Precedence (DESIGN §1, §3): the series-level profile (from
    ``FollowedSeries.quality_profile_json`` when the item is bound to a
    followed series, else the permissive default) is overlaid with the per-item
    ``SourceCriteria`` decoded from ``item.criteria_json``. Shared by the real
    grab (:class:`AcquisitionService`) and the ``grab --dry-run`` preview so the
    preview never diverges from the run (a series ``exclude_3d=False`` /
    ``min_resolution`` must show in both).

    Args:
        store: The acquire store (for the followed-series lookup).
        item: The wanted item to resolve a profile for.

    Returns:
        The effective :class:`QualityProfile` for the grab attempt.
    """
    series_profile = QualityProfile()
    if item.followed_id is not None:
        followed = store.follow.get(item.followed_id)
        if followed is not None:
            series_profile = quality_profile_from_json(followed.quality_profile_json)
    criteria = source_criteria_from_json(item.criteria_json)
    return effective_quality(series_profile, criteria)


__all__ = ["PassGatesMixin", "resolve_effective_profile"]
