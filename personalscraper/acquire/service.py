"""Acquisition service — batch grab loop + atomic-claim state machine (RP5b, phase 4b).

:meth:`AcquisitionService.run` iterates ``list_pending`` + ``list_stale_searching``,
claims each item via the atomic :meth:`WantedSubStore.claim_for_search`
(``BEGIN IMMEDIATE`` UPDATE — the single serialisation point), resolves the
effective :class:`~personalscraper.acquire.desired.QualityProfile`, delegates to
:meth:`GrabOrchestrator.grab`, and maps the returned :class:`GrabOutcome`
disposition onto a wanted status:

- ``"success"``   → :meth:`WantedSubStore.mark_grabbed` (persists status + the
  info-hash for the idempotence guard — no double-emit on re-run).
- ``"retryable"`` → reset ``searching → pending`` (re-listed next run) UNLESS
  ``attempts >= MAX_ATTEMPTS`` → abandon + emit ``WantedAbandoned('attempts_cap')``
  (no infinite loop).
- ``"terminal"``  → set ``searching → abandoned``.

The orchestrator already emits ``GrabSucceeded`` / ``GrabFailed`` /
``WantedAbandoned`` on the bus; the service owns ONLY the status transitions
(plus the attempts-cap ``WantedAbandoned`` the orchestrator cannot know about).

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

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.acquire.desired import (
    QualityProfile,
    effective_quality,
    quality_profile_from_json,
    source_criteria_from_json,
)
from personalscraper.acquire.events import WantedAbandoned
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.acquire.orchestrator import GrabOrchestrator
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.service")

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
        abandoned: Items abandoned (orchestrator ``terminal`` OR attempts cap).
        skipped: Items whose atomic claim was lost to a concurrent process.
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
    """

    def __init__(
        self,
        *,
        store: AcquireStore,
        orchestrator: GrabOrchestrator,
        event_bus: EventBus,
    ) -> None:
        """Initialise the service with injected narrow deps (NOT AppContext).

        Args:
            store: Acquire store.
            orchestrator: Single-item grab chain.
            event_bus: In-process event bus for emitting the attempts-cap
                ``WantedAbandoned`` (fire-and-forget).
        """
        self._store = store
        self._orchestrator = orchestrator
        self._event_bus = event_bus

    def run(self, *, limit: int | None = None) -> RunSummary:
        """Process the pending + stale-searching wanted queue.

        For each item: atomically claim it; if the claim is lost (concurrent
        process or no longer 'pending'/recoverable), skip. Otherwise resolve the
        effective profile, delegate to the orchestrator, and map the disposition
        onto a status. A grabbed row is never re-claimed on a later run (it is
        no longer 'pending' and not stale) — the idempotence hash-guard.

        Args:
            limit: Maximum number of items to attempt this run; ``None`` = all
                pending + stale items.

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

        if limit is not None:
            queue = queue[:limit]

        grabbed = retried = abandoned = skipped = 0

        for item in queue:
            assert item.id is not None  # noqa: S101 — ensured by the SELECTs above
            wanted_id = item.id

            # A stale 'searching' row is not 'pending', so its claim would fail.
            # Recover it back to 'pending' first, then re-claim atomically — the
            # re-claim re-stamps attempts/last_search_at and re-serialises.
            if item.status == "searching":
                self._store.wanted.set_status(wanted_id, "pending")

            won = self._store.wanted.claim_for_search(wanted_id, now)
            if not won:
                # Lost the atomic claim (concurrent winner) — skip, do NOT proceed.
                skipped += 1
                log.debug("acquire.service.claim_lost", wanted_id=wanted_id)
                continue

            # Re-fetch to read the post-claim attempts count.
            current = self._store.wanted.get(wanted_id)
            if current is None:
                skipped += 1
                continue

            profile = self._resolve_profile(current)
            outcome = self._orchestrator.grab(current, profile)

            if outcome.disposition == "success":
                info_hash = outcome.info_hash or ""
                self._store.wanted.mark_grabbed(wanted_id, info_hash)
                grabbed += 1
            elif outcome.disposition == "terminal":
                self._store.wanted.set_status(wanted_id, "abandoned")
                abandoned += 1
            else:  # "retryable"
                if current.attempts >= MAX_ATTEMPTS:
                    self._abandon_at_cap(current)
                    abandoned += 1
                else:
                    self._store.wanted.set_status(wanted_id, "pending")
                    retried += 1

        log.info(
            "acquire.service.run_complete",
            grabbed=grabbed,
            retried=retried,
            abandoned=abandoned,
            skipped=skipped,
        )
        return RunSummary(grabbed=grabbed, retried=retried, abandoned=abandoned, skipped=skipped)

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
