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

from personalscraper.acquire.cadence import is_due_by_cadence, is_past_cutoff
from personalscraper.acquire.desired import (
    QualityProfile,
    effective_quality,
    quality_profile_from_json,
    source_criteria_from_json,
)
from personalscraper.acquire.domain import OPEN_WANTED_STATUSES, WantedItem
from personalscraper.acquire.events import SeasonFellBackToEpisodes, WantedAbandoned
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
        assert item.followed_id is not None  # noqa: S101
        assert item.season is not None  # noqa: S101
        season_wanted_id = item.id
        followed_id = item.followed_id
        season_num = item.season

        # List aired episodes for this season from the catalog cache.
        aired_rows = self._store.aired.list_for_followed(followed_id)
        episode_numbers = sorted(int(r.episode) for r in aired_rows if r.season == season_num)

        # Re-enqueue the aired episodes as fresh individual wanteds — skipping
        # any episode that already holds an OPEN row (review F11: a duplicate
        # (follow, season, episode) row would double-search and double-grab).
        # A row that exists only in a terminal/absorbed status DOES get a fresh
        # one: absorption is irreversible by design, so the fallback re-mints.
        # The detect pass skips owned ones, so over-enqueueing is harmless.
        reenqueued = 0
        for ep_num in episode_numbers:
            existing = self._store.wanted.find(
                followed_id=followed_id,
                kind="episode",
                season=season_num,
                episode=ep_num,
                statuses=tuple(sorted(OPEN_WANTED_STATUSES)),
            )
            if existing is not None:
                continue
            self._store.wanted.add(
                WantedItem(
                    media_ref=item.media_ref,
                    kind="episode",
                    status="pending",
                    enqueued_at=now,
                    followed_id=followed_id,
                    season=season_num,
                    episode=ep_num,
                ),
            )
            reenqueued += 1

        # Transition the season row.
        self._store.wanted.fallback_season(season_wanted_id)

        self._event_bus.emit(
            SeasonFellBackToEpisodes(
                season_wanted_id=season_wanted_id,
                media_ref=item.media_ref,
                season=season_num,
                reenqueued_count=reenqueued,
            ),
        )
        log.info(
            "acquire.service.season_fallback",
            wanted_id=season_wanted_id,
            season=season_num,
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


def merge_pass_queue(
    head: list[WantedItem],
    stale: list[WantedItem],
    *,
    followed_id: int | None,
    limit: int | None,
) -> list[WantedItem]:
    """Merge a pass's own head with the stale-'searching' sweep into one queue.

    The SINGLE implementation of the queue rule — ordering, de-duplication,
    per-series scoping and capping. Three call sites share it and MUST keep
    sharing it: :meth:`AcquisitionService.run` (head = ``list_available()``),
    :meth:`AcquisitionService.run_search` (head = ``list_pending()``) and the
    ``grab --dry-run`` preview (same head as the grab run). A second
    implementation is what let the preview drift onto the wrong queue and
    report « nothing to do » for a row the next real run grabbed.

    Args:
        head: The pass's own queue (``list_pending`` or ``list_available``).
        stale: The stale-'searching' rows, which belong to whichever pass runs
            next — a process killed mid-claim leaves no orphan.
        followed_id: When set, keep only items of that followed series.
            Applied BEFORE ``limit`` so the cap counts the series' items.
        limit: Maximum number of items to return; ``None`` = no cap.

    Returns:
        The queued :class:`WantedItem` list (possibly empty), de-duplicated by
        id, ``head`` rows first.
    """
    # A stale row is in neither list_pending nor list_available, but the guard
    # keeps the merge total.
    seen_ids: set[int] = set()
    queue: list[WantedItem] = []
    for item in [*head, *stale]:
        if item.id is not None and item.id not in seen_ids:
            seen_ids.add(item.id)
            queue.append(item)

    # Per-series scoping (OBJ3): keep only this series' items. The wanted queue
    # is small, so an in-memory filter avoids a bespoke scoped store query.
    if followed_id is not None:
        queue = [item for item in queue if item.followed_id == followed_id]

    if limit is not None:
        queue = queue[:limit]
    return queue


__all__ = ["PassGatesMixin", "merge_pass_queue", "resolve_effective_profile"]
