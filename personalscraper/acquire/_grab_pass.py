"""The GRAB pass — claim, orchestrate the add, persist + emit (D6 split).

Extracted VERBATIM from ``acquire/service.py``: same cutoff gate, same claim,
same disposition routing, the same two-phase hash claim (D2 intent BEFORE the
add, ``mark_grabbed`` as confirmation), the same emit-after-persist contract and
the same fail-soft obligation write. Only the module boundary moved.

Mixed into :class:`~personalscraper.acquire.service.AcquisitionService`, so the
moved bodies keep resolving ``self._store`` / ``self._orchestrator`` /
``self._event_bus`` / ``self._config`` exactly as they did inline.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from personalscraper.acquire._pass_gates import PassGatesMixin
from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.events import GrabSucceeded
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.cadence import Cadence
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome
    from personalscraper.acquire.service import _ItemOutcome
    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.service")


class GrabPassMixin(PassGatesMixin):
    """The grab pass: one available item in, one torrent added + recorded."""

    _store: AcquireStore
    _orchestrator: GrabOrchestrator
    _event_bus: EventBus
    _config: Config
    # F3 run-linkage: the grab command's pipeline_run.run_uid (set on the service at run()
    # entry from its CliRunRecorder). None outside a recorded grab run.
    _grab_run_uid: str | None

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
        # reswitch #342 — exclude releases already grabbed-and-failed for this
        # item (dead swarm / broken payload), so a re-grab after an auto-reswitch
        # never re-picks the same dead release. Empty on the ordinary first grab.
        tried = frozenset(self._store.wanted.list_tried_hashes(wanted_id))
        # D2 — the orchestrator writes the chosen hash onto this still
        # 'searching' row through the hook, immediately before its ``add()``.
        # A crash in the add→``mark_grabbed`` window then leaves an INTENT the
        # reconciliation can replay against the client, not an orphan torrent.
        outcome = self._orchestrator.grab(
            current,
            profile,
            on_intent=lambda info_hash: self._record_grab_intent(wanted_id, info_hash),
            exclude_hashes=tried,
        )

        if outcome.disposition == "success":
            return self._persist_success(current, outcome)

        # D2 (release half) — the grab did NOT hand a torrent to the client, so
        # the hash reserved before ``add()`` must go back. Done HERE, once, for
        # every non-success disposition and BEFORE any status write: the store
        # guard matches ``status='searching'``, which is what the row still
        # reads at this point and stops reading the moment a branch below calls
        # ``set_status``. Leaving the hash on strands the row — see
        # ``clear_grab_intent`` for the full list of actors it locks out.
        self._release_grab_intent(wanted_id)

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

    def _record_grab_intent(self, wanted_id: int, info_hash: str) -> None:
        """Reserve *info_hash* on the claimed row before the torrent is added (D2).

        Called by the orchestrator through its ``on_intent`` hook. A ``False``
        return from the store means the row is no longer a hash-less 'searching'
        row — a concurrent runner reserved or completed it. That is logged and
        NOT raised: the add still proceeds and ``mark_grabbed`` will persist the
        client's hash, so the outcome is the pre-D2 behaviour rather than a lost
        grab. A store EXCEPTION (lock) does propagate: the add must not run when
        nothing recorded the intent.

        Args:
            wanted_id: Rowid of the claimed ``wanted`` row.
            info_hash: Info-hash of the release about to be added.
        """
        if not self._store.wanted.record_grab_intent(wanted_id, info_hash):
            log.warning(
                "acquire.service.grab_intent_not_reserved",
                wanted_id=wanted_id,
                info_hash=info_hash,
            )

    def _release_grab_intent(self, wanted_id: int) -> None:
        """Give back the hash reserved for a grab that failed (D2).

        Fail-soft on the ``False`` return, which is not an anomaly here: the
        row legitimately carries no reservation when the chain failed BEFORE
        ``resolve_source`` (no candidate was ever chosen, so ``on_intent`` never
        fired). Only the release of an actual reservation is logged.

        A store EXCEPTION (lock) propagates to :meth:`run`'s per-item isolation,
        which leaves the row 'searching' for the stale sweep — the same
        treatment every other persistence failure on this path gets.

        Args:
            wanted_id: Rowid of the claimed ``wanted`` row.
        """
        if self._store.wanted.clear_grab_intent(wanted_id):
            log.info("acquire.service.grab_intent_released", wanted_id=wanted_id)

    def _persist_success(self, item: WantedItem, outcome: GrabOutcome) -> _ItemOutcome:
        """Persist a successful grab then emit ``GrabSucceeded`` (emit-after-persist).

        DESIGN §15 / §11(d): the orchestrator does NOT emit ``GrabSucceeded`` —
        the service persists the info-hash via ``mark_grabbed`` FIRST, then emits
        the event. So a crash AFTER ``mark_grabbed`` cannot double-emit: the
        persisted hash is on the row, and every later pass short-circuits on it.
        Emit follows persistence.

        THE add() → mark_grabbed WINDOW (D2, closed): the hash is no longer
        first written here. ``_record_grab_intent`` reserves it on the still
        'searching' row BEFORE the orchestrator's ``add()``, and this method is
        the CONFIRMATION half of that two-phase claim. A crash in the window
        therefore leaves an intent row, and the reconciliation replays it:

        * torrent present in the client ⇒ ``confirm_grab_intent`` promotes the
          row to 'grabbed' and the seed obligation is recorded then
          (``DeleteAuthority.record_grab_obligation``) — no orphan, nothing
          unprotected from the deletion authority;
        * torrent absent ⇒ ``requeue_missing`` clears the hash and the row is
          searchable again — the add never landed, so re-searching is honest.

        What the recovery is NOT is a fresh decision: it confirms the release
        already chosen rather than re-ranking today's trackers, so the window can
        no longer swap the release or add a second torrent for the same item.

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
        # Provenance seed (feature provenance / #30): record the grabbed identity so
        # the scrape can later resolve it DETERMINISTICALLY (via staging_path → hash →
        # this row → media_ref) instead of re-inferring it from the renamed folder.
        # This is the grab pass over FOLLOW-DRIVEN wanted items, so a manual/direct
        # grab never reaches here → no row (ACC-06). The write is best-effort (the
        # store swallows any error), so it never affects the grab persist/emit contract.
        if info_hash:
            self._store.provenance.upsert_grab(
                info_hash,
                followed_id=item.followed_id,
                media_ref=item.media_ref,
                kind=item.kind,
                grabbed_at=int(time.time()),
                # Identité AFFICHABLE (017) : sans elle, deux épisodes du même feuilleton
                # donnent deux cartes identiques dans « Parcours ».
                season=item.season,
                episode=item.episode,
                # F3: the grab command's OWN pipeline_run.run_uid (from its CliRunRecorder,
                # NOT the ContextVar — grab's correlation is a misaligned fresh uuid). None
                # when grab runs with no run row.
                run_uid=self._grab_run_uid,
            )
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


__all__ = ["GrabPassMixin"]
