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
from personalscraper.acquire.domain import OPEN_WANTED_STATUSES, WantedItem
from personalscraper.acquire.events import SeasonAbsorbedEpisodes, WantedAbandoned, WantedEnqueued
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.cadence import Cadence
    from personalscraper.acquire.orchestrator import GrabOrchestrator, SearchVerdict
    from personalscraper.acquire.service import _SearchItemOutcome
    from personalscraper.api.tracker._base import TrackerResult
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
    "no_matching_season": "pending",
    "all_filtered": "pending",
    "trackers_unavailable": "pending",
    "trackers_degraded": "pending",
    "circuit_open": "pending",
    "search_api_error": "pending",
    "no_seeders": "pending",
    "tracker_auth": "abandoned",
}

#: Terminal outcomes that abandon only on a SECOND CONSECUTIVE occurrence.
#:
#: ``tracker_auth`` fires when EVERY queried tracker reported a broken
#: credential. That is a real permanent failure and it must terminate — but it is
#: also exactly what an ordinary passkey rotation looks like for the few minutes
#: the old keys are dead. Abandoning on the first observation would empty the
#: whole queue on a condition that fixes itself.
#:
#: So the first all-auth search RECORDS the verdict and leaves the row queued;
#: the next one confirms it and abandons. The counter is the row's own
#: ``last_search_outcome`` — no extra column, no extra clock — which also makes
#: the reset free: any other verdict in between breaks the streak.
_DEBOUNCED_TERMINAL_OUTCOMES: frozenset[str] = frozenset({"tracker_auth"})


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
        # reswitch #342 (review M1) — exclude releases already grabbed-and-failed
        # for this item so a reswitched row does not count its known-dead release
        # as an « À récupérer » candidate (which would bounce it at 'available'
        # forever). Empty on the ordinary first search.
        tried = frozenset(self._store.wanted.list_tried_hashes(wanted_id))
        verdict = self._orchestrator.search(current, profile, exclude_hashes=tried)

        # R2: episode→season conversion — when filter_to_episode zeroed the
        # results but a whole-season pack is present in the raw results, enqueue
        # a season wanted and absorb the episode (+ live siblings). The season
        # row is enqueued pending, so the next pass evaluates it cleanly.
        if (
            verdict.outcome == "no_matching_episode"
            and current.kind == "episode"
            and current.season is not None
            and verdict.raw_results is not None
        ):
            from personalscraper.acquire.orchestrator import filter_to_season

            # F4 — verify pack coverage against the aired-episode count; an
            # empty cache (or a standalone item) yields None and the filter
            # rejects episode-marker releases conservatively.
            expected_count: int | None = None
            if current.followed_id is not None:
                expected_count = len(self._aired_episodes_for_season(current.followed_id, current.season)) or None
            season_packs = filter_to_season(list(verdict.raw_results), current.season, expected_count=expected_count)
            if season_packs:
                # Record the triggering verdict BEFORE the conversion absorbs
                # the row (verdict-before-status, the #320 order): an absorbed
                # episode must still state WHY its own search concluded
                # (review F12). ``found`` is 0 — 'no_matching_episode' is a
                # concluded not_found, never an outage.
                self._store.wanted.record_search_outcome(wanted_id, verdict.outcome, 0)
                converted = self._enqueue_season_from_conversion(
                    current,
                    list(verdict.raw_results),
                    season_packs,
                    now,
                )
                if converted:
                    # The episode row is absorbed into the season row (R5); the
                    # season is enqueued/reused pending.
                    # _enqueue_season_from_conversion emits WantedEnqueued (if
                    # new) and SeasonAbsorbedEpisodes.
                    return "waiting"
                # Conversion refused (terminal season row — post-R6 fallback):
                # fall through to the ordinary verdict path so the episode row
                # records its verdict and stays live.

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

        # A debounced terminal verdict needs a SECOND consecutive observation
        # before it abandons. ``item`` is the post-claim re-fetch, so
        # ``last_search_outcome`` here is the PREVIOUS search's verdict — the
        # streak counter. Deferring only downgrades the STATUS: the verdict
        # below is still recorded verbatim, so the row states what was actually
        # observed and the next pass can read it as the confirmation.
        if status == "abandoned" and verdict.outcome in _DEBOUNCED_TERMINAL_OUTCOMES:
            if item.last_search_outcome != verdict.outcome:
                log.warning(
                    "acquire.service.terminal_verdict_deferred",
                    wanted_id=wanted_id,
                    outcome=verdict.outcome,
                    previous_outcome=item.last_search_outcome,
                )
                status = "pending"
            else:
                log.warning(
                    "acquire.service.terminal_verdict_confirmed",
                    wanted_id=wanted_id,
                    outcome=verdict.outcome,
                )

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

        # A degraded search never concluded: give back the attempt claim_for_search
        # consumed BEFORE the verdict was known, so ``attempts`` keeps meaning
        # « searches that concluded » — the counter the starvation escalation reads.
        # After the status write, so a crash in between leaves the row queued with a
        # fresh verdict rather than a silently discounted one.
        if verdict.outcome == "trackers_degraded":
            self._store.wanted.refund_search_attempt(wanted_id)

        # not_found concluded « nothing yet » (waiting); everything else did not
        # conclude at all (unverified) — never merge the two.
        return "waiting" if verdict.disposition == "not_found" else "unverified"

    # ------------------------------------------------------------------
    # R2: Episode→Season Conversion
    # ------------------------------------------------------------------

    def _enqueue_season_from_conversion(
        self,
        episode_item: WantedItem,
        raw_results: list[TrackerResult],
        season_packs: list[TrackerResult],
        now: int,
    ) -> bool:
        """Enqueue/reuse a season wanted for the episode's season (R2).

        Called from :meth:`_search_item` when a ``no_matching_episode`` verdict
        reveals a whole-season pack in the raw results. Absorption is idempotent
        — if an OPEN season wanted already exists, only absorption runs.

        The dedup consults the LIVE season row FIRST (counter-review F-A):
        the status-agnostic ``find()`` returns the OLDEST row, so a stale
        terminal season row would otherwise mask a NEWER live one (e.g.
        re-minted by the manual web re-grab, review F5) and starve it of
        absorption. A live row always wins and absorption proceeds onto it.

        Only when NO live row exists does a TERMINAL season row
        (``fallback_episodes`` / ``abandoned`` / ``done``) refuse the
        conversion entirely (review F1): after an R6 fallback the re-enqueued
        episodes must stay live, and absorbing them onto a dead season row
        would empty the queue permanently. Anti ping-pong: the season is
        never re-minted from conversion after a fallback.

        The season wanted is enqueued as ``pending`` (not advanced to available
        in this tick) so the next pass evaluates it cleanly.

        Args:
            episode_item: The episode wanted whose search zeroed on
                ``filter_to_episode``.
            raw_results: The raw tracker results (for logging, unused here).
            season_packs: The results that survived ``filter_to_season``.
            now: Unix epoch seconds (stamps ``enqueued_at``).

        Returns:
            ``True`` when the conversion ran (season enqueued/reused and
            absorption attempted); ``False`` when it was refused because the
            existing season row is terminal — the caller then applies the
            ordinary search verdict so the episode stays live.
        """
        assert episode_item.followed_id is not None  # noqa: S101
        assert episode_item.season is not None  # noqa: S101
        fid = episode_item.followed_id
        season_num = episode_item.season

        # Dedup: one season wanted per follow+season. Consult the LIVE row
        # FIRST (counter-review F-A) — the status-agnostic find() returns the
        # OLDEST row, so an old terminal season row (post-R6 fallback) would
        # mask a newer live one (manual web re-grab, review F5) and the
        # conversion would refuse absorption the live row is entitled to.
        existing = self._store.wanted.find(
            followed_id=fid,
            kind="season",
            season=season_num,
            episode=None,
            statuses=tuple(sorted(OPEN_WANTED_STATUSES)),
        )
        if existing is None:
            # No live row: only now may a terminal row veto the conversion.
            terminal = self._store.wanted.find(
                followed_id=fid,
                kind="season",
                season=season_num,
                episode=None,
            )
            if terminal is not None:
                # Terminal season row (post-R6 fallback, abandon, or done): never
                # absorb live episodes onto a dead row, never re-mint the season.
                log.info(
                    "acquire.service.season_conversion_skipped_terminal",
                    wanted_id=terminal.id,
                    status=terminal.status,
                    season=season_num,
                )
                return False
        season_wid = existing.id if existing is not None else None

        if season_wid is None:
            season_wid = self._store.wanted.add(
                WantedItem(
                    media_ref=episode_item.media_ref,
                    kind="season",
                    status="pending",
                    enqueued_at=now,
                    followed_id=fid,
                    season=season_num,
                    episode=None,
                ),
            )
            self._event_bus.emit(
                WantedEnqueued(
                    media_ref=episode_item.media_ref,
                    kind="season",
                    season=season_num,
                    episode=None,
                ),
            )
            log.info(
                "acquire.service.season_conversion_enqueued",
                wanted_id=episode_item.id,
                season=season_num,
                season_wanted_id=season_wid,
            )

        # Absorb the triggering episode + its live siblings. The statuses
        # filter targets the LIVE row directly: after an R6 fallback an older
        # 'absorbed' row shares the coordinates of the freshly re-enqueued one,
        # and the status-agnostic find would return that dead shadow (review F1).
        live_episode_ids: list[int] = []
        for ep_num in self._aired_episodes_for_season(fid, season_num):
            ep_wanted = self._store.wanted.find(
                followed_id=fid,
                kind="episode",
                season=season_num,
                episode=ep_num,
                statuses=("pending", "searching", "available"),
            )
            if ep_wanted is not None and ep_wanted.id is not None:
                live_episode_ids.append(ep_wanted.id)

        # Always absorb the TRIGGERING episode: it is live by construction (it
        # was just claimed to 'searching'), but an empty aired-episode cache
        # leaves the loop above blind to it — without this it would bounce
        # back through conversion forever with a stale verdict (review F12).
        if episode_item.id is not None and episode_item.id not in live_episode_ids:
            live_episode_ids.append(episode_item.id)

        if live_episode_ids:
            self._store.wanted.absorb_episodes(season_wid, tuple(live_episode_ids))
            self._event_bus.emit(
                SeasonAbsorbedEpisodes(
                    season_wanted_id=season_wid,
                    media_ref=episode_item.media_ref,
                    season=season_num,
                    absorbed_ids=tuple(live_episode_ids),
                ),
            )
            log.info(
                "acquire.service.season_conversion_absorbed",
                episode_count=len(live_episode_ids),
            )

        return True

    def _aired_episodes_for_season(self, followed_id: int, season: int) -> list[int]:
        """Return episode numbers of aired episodes for the given follow+season.

        Reads the ``aired_episode`` catalog cache via :attr:`_store.aired`,
        filtering the full series catalog to the requested season.

        Args:
            followed_id: FK to the ``followed_series`` row.
            season: Season number to filter for.

        Returns:
            Episode numbers of aired episodes in that season (may be empty).
        """
        aired_rows = self._store.aired.list_for_followed(followed_id)
        return [int(r.episode) for r in aired_rows if r.season == season]


__all__ = ["SEARCH_OUTCOME_STATUS", "SearchPassMixin"]
