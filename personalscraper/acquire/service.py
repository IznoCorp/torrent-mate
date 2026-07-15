"""Acquisition service — batch grab loop + atomic-claim state machine (RP5b, phase 4b).

:meth:`AcquisitionService.run` iterates ``list_pending`` + ``list_stale_searching``,
claims each item via the atomic :meth:`WantedSubStore.claim_for_search`
(``BEGIN IMMEDIATE`` UPDATE — the single serialisation point), resolves the
effective :class:`~personalscraper.acquire.desired.QualityProfile`, delegates to
:meth:`GrabOrchestrator.grab`, and maps the returned :class:`GrabOutcome`
disposition onto a wanted status:

- ``"success"``   → :meth:`WantedSubStore.mark_grabbed` (persists status + the
  info-hash for the idempotence guard), THEN emit ``GrabSucceeded``
  (emit-after-persist — DESIGN §15 / §11(d): a ``mark_grabbed`` crash means NO
  emit happened, so the stale-recovery re-grab emits exactly once).
- ``"retryable"`` → reset ``searching → pending`` (re-listed next run) UNLESS
  ``attempts >= MAX_ATTEMPTS`` → abandon + emit ``WantedAbandoned('attempts_cap')``
  (no infinite loop).
- ``"terminal"``  → set ``searching → abandoned``.

The orchestrator emits the FAILURE events (``GrabFailed`` / ``WantedAbandoned``)
itself; ``GrabSucceeded`` is emitted by the SERVICE after ``mark_grabbed``
persists (DESIGN §15 / §11(d)). The service owns the status transitions, the
success emit, and the attempts-cap ``WantedAbandoned`` the orchestrator cannot
know about. Per-item store/decode failures are isolated (DESIGN §6.2) so ONE
bad row never aborts the batch — a DB lock leaves the row for the stale-searching
sweep; corrupt criteria JSON abandons just that row.

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
    from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome
    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.service")

# Per-item outcome tag (maps onto a RunSummary counter in run()).
_ItemOutcome = Literal["grabbed", "retried", "abandoned", "skipped"]

# Attempts cap (DESIGN §6.2): a retryable item is abandoned once its claim count
# reaches this floor, so a permanently-flaky source never loops forever.
MAX_ATTEMPTS = 5

# Stale-searching threshold: items stuck in 'searching' longer than this are
# eligible for recovery (a process killed mid-grab before any status write).
_STALE_THRESHOLD_S = 3600  # 1 hour


@dataclass(frozen=True, kw_only=True)
class RunSummary:
    """Counts for one :meth:`AcquisitionService.run` call.

    Attributes:
        grabbed: Items successfully grabbed (orchestrator ``success``).
        retried: Items reset to 'pending' (orchestrator ``retryable``, below cap).
        abandoned: Items abandoned (orchestrator ``terminal``, attempts cap, OR a
            corrupt-criteria-JSON row isolated out of the batch — DESIGN §6.2).
        skipped: Items not grabbed without a status change — the atomic claim was
            lost to a concurrent process, the row was already grabbed (hash-guard
            short-circuit), or a DB lock left it for the stale-searching sweep
            (DESIGN §6.2).
    """

    grabbed: int = 0
    retried: int = 0
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
    """Batch grab loop over the wanted queue (RP5b).

    Attributes:
        _store: Acquire store (queue reads + ``wanted`` status writes only).
        _orchestrator: Single-item grab chain.
        _event_bus: Bus for the attempts-cap ``WantedAbandoned`` the
            orchestrator cannot emit (it never sees the cap). Required, per the
            project's no-optional-event_bus contract (fire-and-forget).
        _config: Typed JSON5 configuration; ``config.acquire.cadence`` is the
            global cadence policy resolved once per :meth:`run`.
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
        """Process the pending + stale-searching wanted queue.

        For each item: atomically claim it; if the claim is lost (concurrent
        process or no longer 'pending'/recoverable), skip. Otherwise resolve the
        effective profile, delegate to the orchestrator, and map the disposition
        onto a status. A grabbed row is never re-claimed on a later run (it is
        no longer 'pending' and not stale) — the idempotence hash-guard.

        Args:
            limit: Maximum number of items to attempt this run; ``None`` = all
                pending + stale items.
            followed_id: When set, restrict the run to wanted items belonging to
                that followed series (webui-overhaul OBJ3 per-series manual
                trigger). Items with a different — or ``None`` — ``followed_id``
                are skipped. Applied BEFORE ``limit`` so the cap counts only the
                targeted series' items.

        Returns:
            A :class:`RunSummary` of outcome counts.
        """
        now = int(time.time())
        stale_threshold = now - _STALE_THRESHOLD_S

        pending = self._store.wanted.list_pending()
        stale = self._store.wanted.list_stale_searching(older_than=stale_threshold)

        # Merge pending + stale, de-duplicated by id (a stale row is not pending).
        seen_ids: set[int] = set()
        queue: list[WantedItem] = []
        for item in [*pending, *stale]:
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

        # Build the cadence resolution map ONCE per run (DESIGN §7): the global
        # cadence comes from config; each distinct non-None followed_id is looked
        # up once so per-item resolution below is a dict hit, not a store read.
        # Items with followed_id=None fall back to the global default.
        global_cadence = cadence_from_config(self._config.acquire.cadence)
        follow_map: dict[int, FollowedSeries] = {}
        for item in queue:
            if item.followed_id is not None and item.followed_id not in follow_map:
                fs = self._store.follow.get(item.followed_id)
                if fs is not None:
                    follow_map[item.followed_id] = fs

        grabbed = retried = abandoned = skipped = 0

        for item in queue:
            assert item.id is not None  # noqa: S101 — ensured by the SELECTs above
            wanted_id = item.id

            # Resolve the effective cadence for this item: a per-series override
            # (FollowedSeries.cadence_json) wins over the global default.
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
            cadence = effective_cadence(override, global_cadence)

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

    def _process_item(self, item: WantedItem, now: int, *, cadence: Cadence) -> _ItemOutcome:
        """Claim, grab and persist the result for ONE queued item.

        Extracted so :meth:`run` can wrap each item in error isolation
        (DESIGN §6.2) without an over-broad try around the whole loop body.

        Before claiming, two cadence gates run (DESIGN §7) — both keyed on the
        item's age from ``enqueued_at`` against the resolved ``cadence``:

        - CUTOFF: past the cadence cutoff → abandon (emit-after-persist, mirroring
          the attempts-cap abandon) and return ``"abandoned"`` — NO claim.
        - CADENCE: not yet due for its tier interval → stay 'pending' (re-listed
          next run), return ``"skipped"`` — NO claim, NO attempts increment.

        Args:
            item: The queued :class:`WantedItem` (``item.id`` is non-None — the
                SELECTs in :meth:`run` populate it).
            now: Unix epoch seconds (stamps the atomic claim; also the cadence
                reference clock).
            cadence: Effective cadence policy for this item (resolved in
                :meth:`run` — series override over the global default).

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

        # A stale 'searching' row is not 'pending', so its claim would fail.
        # Recover it back to 'pending' first, then re-claim atomically — the
        # re-claim re-stamps attempts/last_search_at and re-serialises.
        if item.status == "searching":
            self._store.wanted.set_status(wanted_id, "pending")

        # --- CUTOFF CHECK (DESIGN §7) ---
        # Past the cadence cutoff → abandon. Emit-after-persist: set_status first,
        # then emit, symmetrical to the attempts-cap abandon in _abandon_at_cap.
        # Distinct reason ('cutoff_reached' vs 'attempts_cap') so consumers can
        # tell an age-out from a flaky-source give-up. No claim.
        if is_past_cutoff(cadence, now=now, enqueued_at=item.enqueued_at):
            self._store.wanted.set_status(wanted_id, "abandoned")
            self._event_bus.emit(WantedAbandoned(media_ref=item.media_ref, reason="cutoff_reached"))
            log.info("acquire.service.cutoff_abandoned", wanted_id=wanted_id)
            return "abandoned"

        # --- CADENCE CHECK (DESIGN §7) ---
        # Not yet due for its tier interval → stays 'pending' and is re-listed
        # next run. No claim, no attempts increment.
        if not is_due_by_cadence(cadence, now=now, enqueued_at=item.enqueued_at, last_search_at=item.last_search_at):
            log.debug("acquire.service.cadence_not_due", wanted_id=wanted_id)
            return "skipped"

        won = self._store.wanted.claim_for_search(wanted_id, now)
        if not won:
            # Lost the atomic claim (concurrent winner) — skip, do NOT proceed.
            log.debug("acquire.service.claim_lost", wanted_id=wanted_id)
            return "skipped"

        # Re-fetch to read the post-claim attempts count.
        current = self._store.wanted.get(wanted_id)
        if current is None:
            return "skipped"

        # Hash-guard consultation (DESIGN §7 / §11(d)): if the row already
        # carries a persisted info-hash it was grabbed before (e.g. force-reset
        # to 'pending' while retaining grabbed_hash, or re-listed by an
        # external producer). Short-circuit — NO re-grab, NO re-emit. The
        # primary defence is that ``claim_for_search`` only matches a 'pending'
        # row, so a 'grabbed' row is normally never re-claimed; this consults
        # the persisted hash as the belt-and-suspenders guard.
        if current.status == "grabbed" or current.grabbed_hash is not None:
            log.info("acquire.service.already_grabbed_skipped", wanted_id=wanted_id)
            return "skipped"

        profile = self._resolve_profile(current)
        outcome = self._orchestrator.grab(current, profile)

        if outcome.disposition == "success":
            return self._persist_success(current, outcome)
        if outcome.disposition == "terminal":
            self._store.wanted.set_status(wanted_id, "abandoned")
            return "abandoned"
        if outcome.disposition == "not_found":
            # Clean search, nothing usable YET (B.4): stay pending under
            # cadence pacing. The attempts cap does NOT apply — it exists for
            # flaky-infrastructure loops, not for "the release is not out yet";
            # only the cadence cutoff ages a not-found item out.
            self._store.wanted.set_status(wanted_id, "pending")
            return "retried"
        # "retryable"
        if current.attempts >= MAX_ATTEMPTS:
            self._abandon_at_cap(current)
            return "abandoned"
        self._store.wanted.set_status(wanted_id, "pending")
        return "retried"

    def _persist_success(self, item: WantedItem, outcome: GrabOutcome) -> _ItemOutcome:
        """Persist a successful grab then emit ``GrabSucceeded`` (emit-after-persist).

        DESIGN §15 / §11(d): the orchestrator does NOT emit ``GrabSucceeded`` —
        the service persists the info-hash via ``mark_grabbed`` FIRST, then emits
        the event. A ``mark_grabbed`` crash therefore means NO emit happened: the
        row stays 'searching', stale-recovery re-grabs (idempotent ``add``) and
        emits exactly ONCE. Emit follows persistence.

        Args:
            item: The claimed item (``item.id`` non-None).
            outcome: The success :class:`GrabOutcome` carrying the
                ``GrabSucceeded`` payload (``info_hash`` / ``category`` /
                ``tags``).

        Returns:
            The ``"grabbed"`` outcome tag.

        Raises:
            sqlite3.OperationalError: If ``mark_grabbed`` loses the DB lock — the
                emit is then skipped (no double-emit on the eventual re-grab).
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

    def _abandon_at_cap(self, item: WantedItem) -> None:
        """Abandon an item that hit the attempts cap and emit ``WantedAbandoned``.

        The orchestrator never sees the cap (it grabs a single item without
        queue context), so the service emits the distinct
        ``WantedAbandoned('attempts_cap')`` event itself.

        Args:
            item: The over-cap item (``item.id`` is guaranteed non-None here).
        """
        assert item.id is not None  # noqa: S101 — caller fetched it by id
        self._store.wanted.set_status(item.id, "abandoned")
        log.warning("acquire.service.attempts_cap_abandoned", wanted_id=item.id, attempts=item.attempts)
        self._event_bus.emit(WantedAbandoned(media_ref=item.media_ref, reason="attempts_cap"))

    def _resolve_profile(self, item: WantedItem) -> QualityProfile:
        """Resolve the effective :class:`QualityProfile` for one item.

        Precedence (DESIGN §1, §3 — decode-only at RP5b): the series-level
        profile (from ``FollowedSeries.quality_profile_json`` when the item is
        bound to a followed series, else the permissive default) is overlaid
        with the per-item ``SourceCriteria`` decoded from ``item.criteria_json``.

        Args:
            item: The claimed item to resolve a profile for.

        Returns:
            The effective :class:`QualityProfile` for the grab attempt.
        """
        series_profile = QualityProfile()
        if item.followed_id is not None:
            followed = self._store.follow.get(item.followed_id)
            if followed is not None:
                series_profile = quality_profile_from_json(followed.quality_profile_json)
        criteria = source_criteria_from_json(item.criteria_json)
        return effective_quality(series_profile, criteria)


__all__ = ["MAX_ATTEMPTS", "AcquisitionService", "GrabCore", "RunSummary"]
