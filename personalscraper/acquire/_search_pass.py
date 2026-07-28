"""The SEARCH pass — gate, claim, search, persist the verdict (D6 split).

Extracted VERBATIM from ``acquire/service.py``: same gates, same claim, same
verdict persistence (verdict BEFORE status, the #320 order), same log events.
Only the module boundary moved.

The pass answers ONE question per item — « is this takeable? » — and writes what
it concluded. It never touches the torrent client: the grab pass
(``_grab_pass.py``) is what acts on an ``available`` verdict.

Mixed into :class:`~personalscraper.acquire.service.AcquisitionService`, so the
moved bodies keep resolving ``self._store`` / ``self._orchestrator`` /
``self._event_bus`` exactly as they did inline.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from personalscraper.acquire._pass_gates import PassGatesMixin
from personalscraper.acquire.events import WantedAbandoned
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.cadence import Cadence
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.acquire.orchestrator import GrabOrchestrator, SearchVerdict
    from personalscraper.acquire.service import _SearchItemOutcome
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.service")

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


class SearchPassMixin(PassGatesMixin):
    """The search pass: one item in, one persisted verdict out."""

    _store: AcquireStore
    _orchestrator: GrabOrchestrator
    _event_bus: EventBus

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


__all__ = ["SEARCH_OUTCOME_STATUS", "SearchPassMixin"]
