"""Acquisition service — search pass + batch grab loop + atomic-claim state machine.

Two passes over the wanted queue (acq-states phase 2 splits what used to be one
atomic operation — see :mod:`personalscraper.acquire.orchestrator`):

- :meth:`AcquisitionService.run_search` — the SEARCH pass. Claims each item,
  asks the orchestrator for a :class:`~personalscraper.acquire.orchestrator.SearchVerdict`
  and persists it (status + ``last_search_outcome`` + ``last_search_found``).
  It **never touches the torrent client**, and it carries the cadence gates:
  cadence is what spaces the re-verification of an unavailable episode.
  ``found`` is a count only where the search concluded — an outage persists
  ``NULL``, never ``0`` (panne ≠ absence).
- :meth:`AcquisitionService.run` — the GRAB pass, described below.

:meth:`AcquisitionService.run` iterates ``list_available`` +
``list_stale_searching`` — **never** ``list_pending``. It consumes only the
items a search already concluded takeable; bounding it there is what keeps the
operator's « always re-search at grab time » choice cheap (a handful of
known-available items instead of the whole backlog — NE-DOIT-PAS-8). It claims
each item atomically (``BEGIN IMMEDIATE`` UPDATE — the single serialisation
point) via :meth:`WantedSubStore.claim_for_grab` for an 'available' row, or via
:meth:`WantedSubStore.claim_for_search` for a stale 'searching' row the sweep
recovered to 'pending'. It then resolves the effective
:class:`~personalscraper.acquire.desired.QualityProfile`, delegates to
:meth:`GrabOrchestrator.grab`, and maps the returned :class:`GrabOutcome`
disposition onto a wanted status:

- ``"success"``   → the ``'grabbed'`` verdict then
  :meth:`WantedSubStore.mark_grabbed` (persists status + the info-hash for the
  idempotence guard), THEN emit ``GrabSucceeded`` (emit-after-persist —
  DESIGN §15 / §11(d): a ``mark_grabbed`` crash means NO emit happened, so the
  stale-recovery re-grab emits exactly once).
- ``"not_found"`` → verdict ``(reason, 0)`` + back to ``'pending'``: the honest
  revert when the torrent vanished between the two passes — never an
  add-anyway, never a row frozen on « À récupérer ».
- ``"retryable"`` → the verdict is left UNTOUCHED (the grab's own re-search did
  not conclude) and the status FOLLOWS it: back to ``'available'`` when the
  recorded verdict is ``available``, otherwise back to ``'pending'``. A row
  whose last search never concluded must not be promoted to « À récupérer » by
  a failed grab — status and verdict stay in sync either way.
- ``"terminal"``  → ``'abandoned'`` + verdict ``(reason, NULL)``.

The grab pass carries NO cadence gate — cadence spaces the re-verification of
an UNAVAILABLE episode, which is the search pass's job; an already-available
item is taken at the next tick regardless of its tier. It does keep the 30-day
cutoff, applied BEFORE the claim, which bounds infinite retries on a
permanently-failing add. There is no attempts cap: ``attempts`` is the search
pass's cadence-paced counter, and capping the grab pass on it would abandon a
perfectly available item on its first flaky add.

The orchestrator emits the FAILURE events (``GrabFailed`` / ``WantedAbandoned``)
itself; ``GrabSucceeded`` is emitted by the SERVICE after ``mark_grabbed``
persists (DESIGN §15 / §11(d)). The service owns the status transitions, the
success emit, and the cutoff ``WantedAbandoned`` the orchestrator cannot know
about (it never sees the queue). Per-item store/decode failures are isolated
(DESIGN §6.2) so ONE bad row never aborts the batch — a DB lock leaves the row
for the stale-searching sweep; corrupt criteria JSON abandons just that row.

``GrabCore`` is a frozen sub-handle (service + orchestrator) attached to
``AcquireContext`` via ONE new field; it is constructed inside
``_factory.build_acquire_context`` (the only frame holding registry +
``config.ranking`` + ``torrent_client`` + ``event_bus`` + store together).

NEGATIVE invariant (DESIGN §9): the service NEVER writes a seed obligation
(``store.seed.add`` / ``record_dispatch``) at grab time — its acquire-DB seam is
``store.wanted.*`` only.

Import direction: ``acquire/`` imports ``api/`` / ``core/`` / ``conf/`` /
``events/`` downward only — never the triage packages (layering guard).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from personalscraper.acquire.cadence import Cadence, is_due_by_cadence, is_past_cutoff
from personalscraper.acquire.desired import (
    QualityProfile,
    cadence_from_config,
    cadence_from_json,
    effective_cadence,
    effective_quality,
    quality_profile_from_json,
    source_criteria_from_json,
)
from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.events import GrabSucceeded, WantedAbandoned
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import FollowedSeries, WantedItem
    from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome, SearchVerdict
    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.service")

# Per-item outcome tag (maps onto a RunSummary counter in run()).
_ItemOutcome = Literal["grabbed", "retried", "abandoned", "skipped"]

# Per-item outcome tag of the SEARCH pass (maps onto a SearchRunSummary counter).
_SearchItemOutcome = Literal["available", "waiting", "unverified", "abandoned", "skipped"]

# Verdict of the pre-claim gates. The cutoff gate
# (:meth:`AcquisitionService._apply_cutoff_gate`) is shared by both passes; the
# cadence gate on top of it (:meth:`AcquisitionService._apply_cadence_gates`)
# belongs to the search pass alone.
_GateVerdict = Literal["proceed", "abandoned", "skipped"]

#: Status the service applies per named search outcome. MUST cover
#: ``orchestrator.SEARCH_OUTCOMES`` EXACTLY — the set-equality test fails when a
#: new outcome ships without a mapping, so a « forgotten exit path » cannot
#: silently reopen the founding defect (an item reading « En attente » because
#: nobody wrote down what the last search actually concluded).
#:
#: Every INCONCLUSIVE outcome maps to ``'pending'``: an outage is not knowledge,
#: so the item goes back in the queue rather than claiming a conclusion.
SEARCH_OUTCOME_STATUS: dict[str, str] = {
    "available": "available",
    "no_candidates": "pending",
    "no_matching_episode": "pending",
    "all_filtered": "pending",
    "trackers_unavailable": "pending",
    "circuit_open": "pending",
    "search_api_error": "pending",
    "no_seeders": "pending",
    "tracker_auth": "abandoned",
}

# Stale-searching threshold: items stuck in 'searching' longer than this are
# eligible for recovery (a process killed mid-grab before any status write).
_STALE_THRESHOLD_S = 3600  # 1 hour


@dataclass(frozen=True, kw_only=True)
class RunSummary:
    """Counts for one :meth:`AcquisitionService.run` call.

    Attributes:
        grabbed: Items successfully grabbed (orchestrator ``success``).
        retried: Items left queued for another attempt — ``retryable`` (kept
            'available', verdict untouched) or ``not_found`` (reverted to
            'pending' with the new verdict). Both mean « not taken this pass,
            still wanted ».
        abandoned: Items abandoned (orchestrator ``terminal``, the cadence
            cutoff aging the item out, OR a corrupt-criteria-JSON row isolated
            out of the batch — DESIGN §6.2).
        skipped: Items not grabbed without a status change — the atomic claim was
            lost to a concurrent process, the row was already grabbed (hash-guard
            short-circuit), or a DB lock left it for the stale-searching sweep
            (DESIGN §6.2).
    """

    grabbed: int = 0
    retried: int = 0
    abandoned: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class SearchRunSummary:
    """Counts for one :meth:`AcquisitionService.run_search` call.

    The buckets keep « nothing is takeable » and « I could not tell » apart —
    the whole point of the search pass. Collapsing them would reintroduce the
    lie the feature removes (panne ≠ absence).

    Attributes:
        available: Items the search concluded takeable → status ``'available'``
            (the grab pass's queue).
        waiting: Items the search concluded on with nothing takeable YET → stay
            ``'pending'`` with a ``found=0`` verdict recorded.
        unverified: Items whose search did NOT conclude (outage / open circuit /
            dead swarm) → stay ``'pending'`` with ``found=NULL``. Never counted
            as waiting: we do not know that there is nothing.
        abandoned: Items abandoned — a terminal verdict (broken passkey), the
            cadence cutoff aging the item out, or a corrupt-criteria-JSON row
            isolated out of the batch (DESIGN §6.2).
        skipped: Items not searched without a status change — cadence-gated, the
            atomic claim lost to a concurrent process, or a DB lock left the row
            for the stale-searching sweep.
    """

    available: int = 0
    waiting: int = 0
    unverified: int = 0
    abandoned: int = 0
    skipped: int = 0


@dataclass(frozen=True, kw_only=True)
class GrabCore:
    """Single sub-handle bundling the grab orchestrator + service.

    Attached as ``AcquireContext.grab`` (ONE new field). Built inside
    ``_factory.build_acquire_context`` — the only frame holding registry +
    ``config.ranking`` + ``torrent_client`` + ``event_bus`` + store together
    (transports via ``TrackerRegistry.transports()``).

    ``GrabCore is None`` when ``torrent_client is None`` (read-only / dry-run
    commands can still search+filter+rank via the registry, but cannot add).
    Owns no closeable resource of its own — the bus is borrowed and the store /
    registry lifecycles are owned by ``AcquireContext``.

    Attributes:
        service: Batch acquisition loop (atomic-claim state machine).
        orchestrator: Single-item grab chain (also reachable for CLI ``--dry-run``).
    """

    service: AcquisitionService
    orchestrator: GrabOrchestrator


class AcquisitionService:
    """Search pass + batch grab loop over the wanted queue (RP5b).

    Attributes:
        _store: Acquire store (queue reads + ``wanted`` status writes only).
        _orchestrator: Single-item search + grab chains.
        _event_bus: Bus for the ``WantedAbandoned`` events the orchestrator
            cannot emit (it never sees the queue, so it knows nothing of the
            cadence cutoff or of a terminal search verdict). Required, per the
            project's no-optional-event_bus contract (fire-and-forget).
        _config: Typed JSON5 configuration; ``config.acquire.cadence`` is the
            global cadence policy resolved once per pass.
    """

    def __init__(
        self,
        *,
        store: AcquireStore,
        orchestrator: GrabOrchestrator,
        event_bus: EventBus,
        config: Config,
    ) -> None:
        """Initialise the service with injected narrow deps (NOT AppContext).

        Args:
            store: Acquire store.
            orchestrator: Single-item grab chain.
            event_bus: In-process event bus for emitting the attempts-cap
                ``WantedAbandoned`` (fire-and-forget).
            config: Typed JSON5 configuration; the service reads
                ``config.acquire.cadence`` to build the global cadence policy
                (DESIGN §7) — the per-run cadence-gating + cutoff floor.
        """
        self._store = store
        self._orchestrator = orchestrator
        self._event_bus = event_bus
        self._config = config

    def run(self, *, limit: int | None = None, followed_id: int | None = None) -> RunSummary:
        """Run the GRAB pass over the available + stale-searching queue.

        Takes the items a search already concluded takeable — and ONLY those.
        The pending backlog is invisible to this pass: bounding grab to
        ``list_available()`` is what makes the operator's « always re-search at
        grab time » choice affordable, since it re-queries a handful of
        known-available items instead of the whole queue (NE-DOIT-PAS-8).

        For each item: age it out if it is past the cadence cutoff (the only
        gate left here — there is NO cadence gate, an available item is taken at
        the next tick regardless of its tier), then atomically claim it. If the
        claim is lost (concurrent process, or the row is no longer
        'available'/recoverable), skip. Otherwise resolve the effective profile,
        delegate to the orchestrator, and map the disposition onto a status. A
        grabbed row is never re-claimed on a later run (it is no longer
        'available' and not stale) — the idempotence hash-guard.

        Args:
            limit: Maximum number of items to attempt this run; ``None`` = all
                available + stale items.
            followed_id: When set, restrict the run to wanted items belonging to
                that followed series (webui-overhaul OBJ3 per-series manual
                trigger). Items with a different — or ``None`` — ``followed_id``
                are skipped. Applied BEFORE ``limit`` so the cap counts only the
                targeted series' items.

        Returns:
            A :class:`RunSummary` of outcome counts.
        """
        now = int(time.time())
        queue = self._build_queue(
            self._store.wanted.list_available(),
            now=now,
            limit=limit,
            followed_id=followed_id,
        )
        global_cadence = cadence_from_config(self._config.acquire.cadence)
        follow_map = self._load_follow_map(queue)

        grabbed = retried = abandoned = skipped = 0

        for item in queue:
            assert item.id is not None  # noqa: S101 — ensured by the SELECTs above
            wanted_id = item.id

            cadence = self._cadence_for(item, follow_map, global_cadence)

            # Per-item error isolation (DESIGN §6.2): ONE item's store/decode
            # failure must never abort the batch — the run_complete summary MUST
            # still fire. We catch only the specific store-lock / corrupt-JSON
            # errors (NOT a bare ``except Exception`` — a genuine programming bug
            # must still surface and crash loudly).
            try:
                outcome_tag = self._process_item(item, now, cadence=cadence)
            except sqlite3.OperationalError as exc:
                # DB lock (RETRYABLE, §6.2): leave the row for the stale-searching
                # sweep to recover (do NOT abort the run). Count as skipped.
                log.warning("acquire.service.item_db_locked", wanted_id=wanted_id, error=str(exc))
                skipped += 1
                continue
            except json.JSONDecodeError as exc:
                # Corrupt criteria_json / quality_profile_json: one bad row must
                # not kill the batch. Abandon it (guarded) and move on.
                log.warning("acquire.service.item_bad_criteria_json", wanted_id=wanted_id, error=str(exc))
                try:
                    self._store.wanted.set_status(wanted_id, "abandoned")
                except sqlite3.OperationalError as set_exc:
                    # Even the abandon write lost the lock — leave it for the sweep.
                    log.warning("acquire.service.item_db_locked", wanted_id=wanted_id, error=str(set_exc))
                abandoned += 1
                continue

            if outcome_tag == "grabbed":
                grabbed += 1
            elif outcome_tag == "retried":
                retried += 1
            elif outcome_tag == "abandoned":
                abandoned += 1
            else:  # "skipped"
                skipped += 1

        log.info(
            "acquire.service.run_complete",
            grabbed=grabbed,
            retried=retried,
            abandoned=abandoned,
            skipped=skipped,
        )
        return RunSummary(grabbed=grabbed, retried=retried, abandoned=abandoned, skipped=skipped)

    def run_search(self, *, limit: int | None = None, followed_id: int | None = None) -> SearchRunSummary:
        """Run the SEARCH pass over the pending + stale-searching queue.

        States availability without downloading anything: for each item it
        claims the row, asks the orchestrator for a :class:`SearchVerdict`, and
        persists the verdict + the resulting status. **This pass never touches
        the torrent client** — the service holds no client reference at all and
        :meth:`GrabOrchestrator.search` adds nothing, so a deployment with
        ``torrent_client=None`` runs the search pass normally. That separation
        is the whole feature: while search and grab were one atomic call,
        « À récupérer » existed for milliseconds inside a single function and
        the operator could never see what was available but not yet taken.

        The cadence gates (tier interval + 30-day cutoff, DESIGN §7) belong to
        THIS pass — cadence is what spaces the re-verification of an episode the
        trackers do not have yet. The grab pass takes a known-available item at
        its next tick regardless of cadence.

        Verdict mapping (contract, per disposition):

        - ``available``  → status ``'available'`` + verdict ``(outcome, found)``
        - ``not_found``  → status ``'pending'``   + verdict ``(outcome, 0)``
        - ``retryable``  → status ``'pending'``   + verdict ``(outcome, NULL)``
        - ``terminal``   → status ``'abandoned'`` + verdict ``(outcome, NULL)``

        ``found`` is a COUNT only where the search actually concluded. ``0``
        means « I looked, there is nothing »; on an outage that statement is
        false, so those paths persist ``NULL`` (panne ≠ absence). Writing ``0``
        by convenience would move the founding lie one level down instead of
        removing it.

        Per-item failures are isolated exactly like :meth:`run` (DESIGN §6.2):
        a DB lock leaves the row for the stale-searching sweep (counted
        ``skipped``), corrupt criteria JSON abandons just that row.

        Args:
            limit: Maximum number of items to search this pass; ``None`` = all
                pending + stale items.
            followed_id: When set, restrict the pass to wanted items belonging
                to that followed series. Applied BEFORE ``limit`` so the cap
                counts only the targeted series' items.

        Returns:
            A :class:`SearchRunSummary` of outcome counts.
        """
        now = int(time.time())
        queue = self._build_queue(
            self._store.wanted.list_pending(),
            now=now,
            limit=limit,
            followed_id=followed_id,
        )
        global_cadence = cadence_from_config(self._config.acquire.cadence)
        follow_map = self._load_follow_map(queue)

        available = waiting = unverified = abandoned = skipped = 0

        for item in queue:
            assert item.id is not None  # noqa: S101 — ensured by the SELECTs above
            wanted_id = item.id

            cadence = self._cadence_for(item, follow_map, global_cadence)

            # Per-item error isolation (DESIGN §6.2), identical to run(): ONE
            # item's store/decode failure must never abort the pass — the
            # search_run_complete summary MUST still fire.
            try:
                outcome_tag = self._search_item(item, now, cadence=cadence)
            except sqlite3.OperationalError as exc:
                # DB lock (RETRYABLE, §6.2): leave the row for the stale-searching
                # sweep to recover (do NOT abort the pass). Count as skipped.
                log.warning("acquire.service.item_db_locked", wanted_id=wanted_id, error=str(exc))
                skipped += 1
                continue
            except json.JSONDecodeError as exc:
                # Corrupt criteria_json / quality_profile_json: one bad row must
                # not kill the batch. Abandon it (guarded) and move on.
                log.warning("acquire.service.item_bad_criteria_json", wanted_id=wanted_id, error=str(exc))
                try:
                    self._store.wanted.set_status(wanted_id, "abandoned")
                except sqlite3.OperationalError as set_exc:
                    # Even the abandon write lost the lock — leave it for the sweep.
                    log.warning("acquire.service.item_db_locked", wanted_id=wanted_id, error=str(set_exc))
                abandoned += 1
                continue

            if outcome_tag == "available":
                available += 1
            elif outcome_tag == "waiting":
                waiting += 1
            elif outcome_tag == "unverified":
                unverified += 1
            elif outcome_tag == "abandoned":
                abandoned += 1
            else:  # "skipped"
                skipped += 1

        log.info(
            "acquire.service.search_run_complete",
            available=available,
            waiting=waiting,
            unverified=unverified,
            abandoned=abandoned,
            skipped=skipped,
        )
        return SearchRunSummary(
            available=available,
            waiting=waiting,
            unverified=unverified,
            abandoned=abandoned,
            skipped=skipped,
        )

    # ------------------------------------------------------------------
    # Shared queue / cadence plumbing (both passes)
    # ------------------------------------------------------------------

    def _build_queue(
        self,
        head: list[WantedItem],
        *,
        now: int,
        limit: int | None,
        followed_id: int | None,
    ) -> list[WantedItem]:
        """Return ``head`` + the stale-searching sweep as one pass queue.

        Shared by :meth:`run` and :meth:`run_search` so both passes apply the
        SAME ordering, de-duplication and scoping semantics. Only the head
        differs, and that difference IS the split: the search pass passes
        ``list_pending()`` (items whose availability is unknown), the grab pass
        passes ``list_available()`` (items a search already concluded takeable).
        Both then pick up the stale-'searching' rows, which belong to whichever
        pass runs next — a process killed mid-claim leaves no orphan.

        Args:
            head: The pass's own queue (``list_pending`` or ``list_available``).
            now: Unix epoch seconds (the stale-searching threshold's clock).
            limit: Maximum number of items to return; ``None`` = no cap.
            followed_id: When set, keep only items of that followed series.
                Applied BEFORE ``limit`` so the cap counts the series' items.

        Returns:
            The queued :class:`WantedItem` list (possibly empty), de-duplicated
            by id, ``head`` rows first.
        """
        stale_threshold = now - _STALE_THRESHOLD_S

        stale = self._store.wanted.list_stale_searching(older_than=stale_threshold)

        # Merge head + stale, de-duplicated by id (a stale row is in neither
        # list_pending nor list_available, but the guard keeps the merge total).
        seen_ids: set[int] = set()
        queue: list[WantedItem] = []
        for item in [*head, *stale]:
            if item.id is not None and item.id not in seen_ids:
                seen_ids.add(item.id)
                queue.append(item)

        # Per-series scoping (OBJ3): keep only this series' items. The wanted
        # queue is small, so an in-memory filter avoids a bespoke scoped store
        # query. Applied before the limit so `limit` caps the series, not the
        # whole queue.
        if followed_id is not None:
            queue = [item for item in queue if item.followed_id == followed_id]

        if limit is not None:
            queue = queue[:limit]
        return queue

    def _load_follow_map(self, queue: list[WantedItem]) -> dict[int, FollowedSeries]:
        """Load each queued item's followed series ONCE (DESIGN §7).

        Each distinct non-``None`` ``followed_id`` is looked up once, so the
        per-item cadence resolution in :meth:`_cadence_for` is a dict hit rather
        than a store read.

        Args:
            queue: The queue returned by :meth:`_build_queue`.

        Returns:
            A ``followed_id → FollowedSeries`` map (missing rows are absent).
        """
        follow_map: dict[int, FollowedSeries] = {}
        for item in queue:
            if item.followed_id is not None and item.followed_id not in follow_map:
                fs = self._store.follow.get(item.followed_id)
                if fs is not None:
                    follow_map[item.followed_id] = fs
        return follow_map

    def _cadence_for(
        self,
        item: WantedItem,
        follow_map: dict[int, FollowedSeries],
        global_cadence: Cadence,
    ) -> Cadence:
        """Resolve the effective cadence for one item (series override > global).

        Args:
            item: The queued item.
            follow_map: The map built by :meth:`_load_follow_map`.
            global_cadence: The config-level default cadence.

        Returns:
            The effective :class:`Cadence` for this item.
        """
        fs = follow_map.get(item.followed_id) if item.followed_id is not None else None
        override = None
        if fs is not None and fs.cadence_json is not None:
            override = cadence_from_json(fs.cadence_json)
            if override is None:
                log.warning(
                    "acquire.service.cadence_override_dropped",
                    followed_id=fs.id,
                    title=fs.title,
                )  # malformed per-series cadence_json → fell back to the global default
        return effective_cadence(override, global_cadence)

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
            self._store.wanted.set_status(wanted_id, "abandoned")
            self._event_bus.emit(WantedAbandoned(media_ref=item.media_ref, reason="cutoff_reached"))
            log.info("acquire.service.cutoff_abandoned", wanted_id=wanted_id)
            return "abandoned"

        return "proceed"

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

    def _search_item(self, item: WantedItem, now: int, *, cadence: Cadence) -> _SearchItemOutcome:
        """Gate, claim and search ONE queued item, persisting its verdict.

        Extracted so :meth:`run_search` can wrap each item in error isolation
        (DESIGN §6.2) without an over-broad try around the whole loop body.

        The torrent client is never referenced on this path — the orchestrator's
        :meth:`~personalscraper.acquire.orchestrator.GrabOrchestrator.search`
        runs the search→filter→rank chain and returns a pure verdict.

        Args:
            item: The queued :class:`WantedItem` (``item.id`` is non-None).
            now: Unix epoch seconds (stamps the atomic claim; also the cadence
                reference clock).
            cadence: Effective cadence policy for this item.

        Returns:
            A one-word outcome tag mapped onto a :class:`SearchRunSummary`
            counter by :meth:`run_search`.

        Raises:
            sqlite3.OperationalError: On a DB lock (RETRYABLE — :meth:`run_search`
                isolates it and leaves the row for the stale-searching sweep).
            json.JSONDecodeError: On corrupt criteria/profile JSON
                (:meth:`run_search` isolates it and abandons the row).
        """
        assert item.id is not None  # noqa: S101 — ensured by the SELECTs in run_search()
        wanted_id = item.id

        gate = self._apply_cadence_gates(item, now, cadence=cadence)
        if gate != "proceed":
            return gate

        # The claim stamps `last_search_at`, which is the STALENESS clock other
        # runners read — so it must be the time of the claim, not of the pass
        # start. A long pass stamping its start clock makes its own in-flight
        # rows read as stale to a concurrent sweep, which then reclaims them.
        # (The gates above deliberately keep `now`: cadence and cutoff want one
        # consistent snapshot for the whole pass.)
        won = self._store.wanted.claim_for_search(wanted_id, int(time.time()))
        if not won:
            # Lost the atomic claim (concurrent winner) — skip, do NOT proceed.
            log.debug("acquire.service.claim_lost", wanted_id=wanted_id)
            return "skipped"

        # Re-fetch so the profile is resolved from the post-claim row (mirrors
        # _process_item) and a row deleted between listing and claim is skipped.
        current = self._store.wanted.get(wanted_id)
        if current is None:
            return "skipped"

        profile = self._resolve_profile(current)
        verdict = self._orchestrator.search(current, profile)
        return self._apply_search_verdict(current, verdict)

    def _apply_search_verdict(self, item: WantedItem, verdict: SearchVerdict) -> _SearchItemOutcome:
        """Persist ONE :class:`SearchVerdict` — verdict first, then status.

        Write order is deliberate. Recording the verdict BEFORE the status
        transition means a crash in between leaves the row 'searching' with a
        fresh verdict: the stale sweep re-searches it and overwrites. The
        reverse order would leave a row displaying a NEW status alongside the
        PREVIOUS search's verdict — the exact « status says one thing, the
        evidence says another » incoherence this feature removes.

        ``found`` is normalised from the disposition rather than trusted
        verbatim, so an inconclusive path can never persist ``0``
        (panne ≠ absence) even if a future orchestrator path passes one.

        Args:
            item: The claimed item (``item.id`` non-None).
            verdict: The orchestrator's verdict for this item.

        Returns:
            The outcome tag for the :class:`SearchRunSummary` bucket.

        Raises:
            sqlite3.OperationalError: On a DB lock (isolated by
                :meth:`run_search`).
        """
        assert item.id is not None  # noqa: S101 — caller claimed it by id
        wanted_id = item.id

        status = SEARCH_OUTCOME_STATUS.get(verdict.outcome)
        if status is None:
            # Unreachable while the set-equality test holds; if it ever fires,
            # keep the item queued rather than inventing a conclusion.
            log.warning("acquire.service.unmapped_search_outcome", wanted_id=wanted_id, outcome=verdict.outcome)
            status = "pending"

        if verdict.disposition == "available":
            found = verdict.found
        elif verdict.disposition == "not_found":
            found = 0  # concluded: « I looked, nothing takeable yet »
        else:
            found = None  # NOT concluded (outage / circuit / dead swarm / auth)

        self._store.wanted.record_search_outcome(wanted_id, verdict.outcome, found)

        if status == "abandoned":
            # Terminal verdict (broken passkey): the search pass emits nothing of
            # its own, so the service emits WantedAbandoned here — an abandon the
            # operator never hears about is exactly the silent failure the
            # constitution forbids. Emit-after-persist, as everywhere else.
            self._store.wanted.set_status(wanted_id, "abandoned")
            self._event_bus.emit(WantedAbandoned(media_ref=item.media_ref, reason=verdict.outcome))
            log.warning("acquire.service.search_abandoned", wanted_id=wanted_id, outcome=verdict.outcome)
            return "abandoned"

        if status == "available":
            self._store.wanted.set_status(wanted_id, "available")
            log.info("acquire.service.search_available", wanted_id=wanted_id, found=found)
            return "available"

        self._store.wanted.set_status(wanted_id, "pending")
        # not_found concluded « nothing yet » (waiting); everything else did not
        # conclude at all (unverified) — never merge the two.
        return "waiting" if verdict.disposition == "not_found" else "unverified"

    def _process_item(self, item: WantedItem, now: int, *, cadence: Cadence) -> _ItemOutcome:
        """Claim, grab and persist the result for ONE queued item.

        Extracted so :meth:`run` can wrap each item in error isolation
        (DESIGN §6.2) without an over-broad try around the whole loop body.

        Before claiming, ONE gate runs (:meth:`_apply_cutoff_gate`): past the
        cadence cutoff → abandon and return ``"abandoned"``, NO claim. There is
        deliberately NO cadence gate here (it belongs to the search pass) and NO
        attempts cap (``attempts`` counts cadence-paced searches; capping the
        grab pass on it would abandon a known-available item after one flaky
        add).

        Args:
            item: The queued :class:`WantedItem` (``item.id`` is non-None — the
                SELECTs in :meth:`run` populate it).
            now: Unix epoch seconds (stamps the atomic claim; also the cutoff
                reference clock).
            cadence: Effective cadence policy for this item (resolved in
                :meth:`run` — series override over the global default); only its
                cutoff is consulted on this path.

        Returns:
            A one-word outcome tag mapped onto a :class:`RunSummary` counter by
            :meth:`run`.

        Raises:
            sqlite3.OperationalError: On a DB lock (RETRYABLE — :meth:`run`
                isolates it and leaves the row for the stale-searching sweep).
            json.JSONDecodeError: On corrupt criteria/profile JSON (:meth:`run`
                isolates it and abandons the row).
        """
        assert item.id is not None  # noqa: S101 — ensured by the SELECTs in run()
        wanted_id = item.id

        gate = self._apply_cutoff_gate(item, now, cadence=cadence)
        if gate != "proceed":
            return gate

        # Two claim paths, one per queue: an 'available' row is the grab pass's
        # own (claim_for_grab matches 'available'), while a stale 'searching'
        # row was just recovered to 'pending' by the gate and claims through
        # claim_for_search (which matches 'pending'). Using the wrong one would
        # silently no-op and skip every row of that queue.
        #
        # Both stamp a FRESH clock (never the pass-start `now`): `last_search_at`
        # is the staleness reference other runners read, so a long pass stamping
        # its start clock would make its own in-flight rows look stale.
        claim_now = int(time.time())
        if item.status == "searching":
            won = self._store.wanted.claim_for_search(wanted_id, claim_now)
        else:
            won = self._store.wanted.claim_for_grab(wanted_id, claim_now)
        if not won:
            # Lost the atomic claim (concurrent winner) — skip, do NOT proceed.
            log.debug("acquire.service.claim_lost", wanted_id=wanted_id)
            return "skipped"

        # Re-fetch so the profile is resolved from the post-claim row.
        current = self._store.wanted.get(wanted_id)
        if current is None:
            return "skipped"

        # Hash-guard consultation (DESIGN §7 / §11(d)): if the row already
        # carries a persisted info-hash it was grabbed before (e.g. force-reset
        # to 'available' while retaining grabbed_hash, or re-listed by an
        # external producer). Short-circuit — NO re-grab, NO re-emit. The
        # primary defence is that the claim only matches an 'available' (or
        # recovered 'pending') row, so a 'grabbed' row is normally never
        # re-claimed; this consults the persisted hash as the belt-and-suspenders
        # guard.
        if current.status == "grabbed" or current.grabbed_hash is not None:
            log.info("acquire.service.already_grabbed_skipped", wanted_id=wanted_id)
            return "skipped"

        profile = self._resolve_profile(current)
        outcome = self._orchestrator.grab(current, profile)

        if outcome.disposition == "success":
            return self._persist_success(current, outcome)
        if outcome.disposition == "terminal":
            # The orchestrator already emitted WantedAbandoned on this path, so
            # the service only persists: verdict first, then the status (same
            # order as the search pass — a crash in between leaves a row the
            # stale sweep re-processes, never a status contradicting its verdict).
            self._store.wanted.record_search_outcome(wanted_id, outcome.reason or "terminal", None)
            self._store.wanted.set_status(wanted_id, "abandoned")
            return "abandoned"
        if outcome.disposition == "not_found":
            # The torrent vanished between the two passes: the grab's own
            # re-search concluded with nothing takeable. Revert honestly to
            # 'pending' with the new verdict (found=0 — this search DID
            # conclude) rather than adding something else or freezing the row on
            # « À récupérer ».
            self._store.wanted.record_search_outcome(wanted_id, outcome.reason or "no_candidates", 0)
            self._store.wanted.set_status(wanted_id, "pending")
            return "retried"
        # "retryable" — the grab's own search did NOT conclude (circuit, API
        # error, add failure). The SEARCH pass's verdict stands untouched:
        # overwriting it would replace a real conclusion with an outage.
        #
        # The status follows that verdict rather than being forced to
        # 'available'. Only a row whose recorded verdict IS 'available' goes
        # back to « À récupérer » — that is the state its own evidence claims.
        # A row that reached this pass WITHOUT that verdict (the stale
        # 'searching' sweep recovers rows whose last search never concluded, or
        # never ran at all) would otherwise be PROMOTED to 'available' by a
        # failed grab: the UI would announce a takeable item on the strength of
        # an outage, and the search pass — which only walks 'pending' — would
        # never re-verify it. Back to 'pending' is the honest place for it.
        if current.last_search_outcome == "available":
            self._store.wanted.set_status(wanted_id, "available")
        else:
            self._store.wanted.set_status(wanted_id, "pending")
        return "retried"

    def _persist_success(self, item: WantedItem, outcome: GrabOutcome) -> _ItemOutcome:
        """Persist a successful grab then emit ``GrabSucceeded`` (emit-after-persist).

        DESIGN §15 / §11(d): the orchestrator does NOT emit ``GrabSucceeded`` —
        the service persists the info-hash via ``mark_grabbed`` FIRST, then emits
        the event. So a crash AFTER ``mark_grabbed`` cannot double-emit: the
        persisted hash is on the row, and every later pass short-circuits on it.
        Emit follows persistence.

        WHAT THIS DOES NOT COVER (PR #320 review, M9 — OPEN): the window between
        the orchestrator's ``add()`` returning and ``mark_grabbed`` committing.
        In that window the torrent IS in the client and NOTHING records it — no
        hash on the row, no seed obligation. The previous wording called the
        recovery an « idempotent ``add`` » emitting « exactly ONCE »; that is not
        what happens. A crash here leaves:

        * an ORPHAN torrent in qBittorrent, downloading, with no ``wanted`` row
          pointing at it and no seed obligation protecting it from the deletion
          authority;
        * a row that recovers to 'pending' and is re-SEARCHED from scratch — a
          fresh search against today's trackers, NOT a replay of the same
          decision. It may pick a different release, or none at all.

        The window is small (one local SQLite write) and the failure is loud
        rather than silent — the orphan is visible in the client — but it is a
        real gap, not a guarantee. Closing it needs the hash reserved BEFORE the
        add (a two-phase claim), which is a state-machine change.

        The ``'grabbed'`` verdict (with the re-search's takeable count) is
        recorded BEFORE ``mark_grabbed``: recording it after would open a window
        where the row reads 'grabbed' while its verdict still describes the
        previous search, and a lock on that second write would strand a grabbed
        row that no sweep re-visits (``list_stale_searching`` only sees
        'searching').

        Args:
            item: The claimed item (``item.id`` non-None).
            outcome: The success :class:`GrabOutcome` carrying the
                ``GrabSucceeded`` payload (``info_hash`` / ``category`` /
                ``tags``) and the ``found`` count of its re-search.

        Returns:
            The ``"grabbed"`` outcome tag.

        Raises:
            sqlite3.OperationalError: If a persist loses the DB lock — the emit
                is then skipped (no double-emit on the eventual re-grab).
        """
        assert item.id is not None  # noqa: S101 — caller fetched it by id
        info_hash = outcome.info_hash or ""
        if not info_hash:
            # A 'success' disposition with no hash is a contract violation upstream
            # (the orchestrator only reaches success after add() returns a hash).
            # Persist + emit with an empty hash rather than silently swallow it,
            # but log loudly so the anomaly is observable (m3).
            log.warning("acquire.service.success_without_hash", wanted_id=item.id)
        # Persist FIRST — if this raises (lock), the emit below is skipped and the
        # re-grab on the next run emits exactly once.
        self._store.wanted.record_search_outcome(item.id, "grabbed", outcome.found)
        self._store.wanted.mark_grabbed(item.id, info_hash)
        # Seed obligation at GRAB time (2026-07-15): the dispatch-time
        # name+size correlation can never match a renamed/aggregated TV show
        # folder, so TV grabs left the seed_obligation table empty. Here the
        # identity is fully known (hash + tracker + economy floors); the
        # dispatched_path is backfilled by record_dispatch when its
        # correlation hits. Fail-soft — an obligation write must never break
        # the grab persistence/emit contract.
        source_tracker = outcome.chosen.provider if outcome.chosen is not None else ""
        if info_hash and source_tracker:
            try:
                self._record_seed_obligation(info_hash, source_tracker)
            except Exception:  # noqa: BLE001 — fail-soft: obligation is advisory
                log.warning(
                    "acquire.service.obligation_write_failed",
                    wanted_id=item.id,
                    info_hash=info_hash,
                    exc_info=True,
                )
        self._event_bus.emit(
            GrabSucceeded(
                media_ref=item.media_ref,
                info_hash=info_hash,
                source_tracker=outcome.chosen.provider if outcome.chosen is not None else "",
                category=outcome.category,
                tags=outcome.tags,
            )
        )
        return "grabbed"

    def _record_seed_obligation(self, info_hash: str, source_tracker: str) -> None:
        """Record the seeding obligation for a freshly grabbed torrent.

        Skips silently when the tracker declares no ``economy`` block
        (activation-only trackers carry no seeding floors — same rule as the
        dispatch-time writer) or when an active obligation for this hash
        already exists (stale-recovery re-grabs are idempotent).

        Args:
            info_hash: The grabbed torrent's info-hash.
            source_tracker: Tracker name from the winning search result.
        """
        provider = self._config.tracker.providers.get(source_tracker)
        economy = getattr(provider, "economy", None) if provider is not None else None
        if economy is None:
            return
        if self._store.seed.find_active_by_hash(info_hash) is not None:
            return
        self._store.seed.add(
            SeedObligation(
                info_hash=info_hash,
                source_tracker=source_tracker,
                min_seed_time_s=economy.min_seed_time,
                min_ratio=economy.min_ratio,
                added_at=int(time.time()),
                dispatched_path=None,
            )
        )
        log.info(
            "acquire.grab.obligation_recorded",
            info_hash=info_hash,
            tracker=source_tracker,
            min_seed_time_s=economy.min_seed_time,
            min_ratio=economy.min_ratio,
        )

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


__all__ = [
    "SEARCH_OUTCOME_STATUS",
    "AcquisitionService",
    "GrabCore",
    "RunSummary",
    "SearchRunSummary",
    "resolve_effective_profile",
]
