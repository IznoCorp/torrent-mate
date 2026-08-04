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

from personalscraper.acquire._grab_pass import GrabPassMixin
from personalscraper.acquire._pass_gates import _STALE_THRESHOLD_S, resolve_effective_profile
from personalscraper.acquire._search_pass import SEARCH_OUTCOME_STATUS, SearchPassMixin
from personalscraper.acquire.cadence import Cadence
from personalscraper.acquire.desired import (
    cadence_from_config,
    cadence_from_json,
    effective_cadence,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import FollowedSeries, WantedItem
    from personalscraper.acquire.orchestrator import GrabOrchestrator
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


class AcquisitionService(SearchPassMixin, GrabPassMixin):
    """Search pass + batch grab loop over the wanted queue (RP5b).

    The façade owns the RUN loops (queue building, per-item error isolation,
    summaries) and inherits the per-item work from the two pass mixins —
    :class:`~personalscraper.acquire._search_pass.SearchPassMixin` and
    :class:`~personalscraper.acquire._grab_pass.GrabPassMixin`, which share the
    pre-claim gates of
    :class:`~personalscraper.acquire._pass_gates.PassGatesMixin` (D6 split). The
    public surface is unchanged: constructor, :meth:`run`, :meth:`run_search`,
    the two summaries and ``SEARCH_OUTCOME_STATUS`` all still live here.

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
        # F3 run-linkage: the grab-stage run_uid, set per-run at run() entry from the
        # command's CliRunRecorder (grab's ContextVar is a misaligned fresh uuid).
        self._grab_run_uid: str | None = None

    def run(
        self, *, limit: int | None = None, followed_id: int | None = None, run_uid: str | None = None
    ) -> RunSummary:
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
            run_uid: The grab command's ``pipeline_run.run_uid`` (hex, from its
                ``CliRunRecorder``), stamped onto each grabbed item's provenance row
                (F3). ``None`` when grab runs with no run row.

        Returns:
            A :class:`RunSummary` of outcome counts.
        """
        self._grab_run_uid = run_uid  # F3: per-run grab-stage run stamp (see _persist_success)
        # O4/D5: re-assert global transfer caps at every run start — idempotent,
        # self-healing (a client restart that lost the limits gets them back here).
        self._orchestrator.apply_global_caps()
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

        # D1 — per-PASS memo bounding the starvation season probe to ONE extra
        # tracker query per (follow, season). Ten starved siblings of the same
        # season would otherwise fire ten identical season searches, every pass.
        season_probed: set[tuple[int, int]] = set()

        for item in queue:
            assert item.id is not None  # noqa: S101 — ensured by the SELECTs above
            wanted_id = item.id

            cadence = self._cadence_for(item, follow_map, global_cadence)

            # Per-item error isolation (DESIGN §6.2), identical to run(): ONE
            # item's store/decode failure must never abort the pass — the
            # search_run_complete summary MUST still fire.
            try:
                outcome_tag = self._search_item(item, now, cadence=cadence, season_probed=season_probed)
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


__all__ = [
    "SEARCH_OUTCOME_STATUS",
    "AcquisitionService",
    "GrabCore",
    "RunSummary",
    "SearchRunSummary",
    "resolve_effective_profile",
]
