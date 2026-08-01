"""Wanted ↔ library ↔ torrent-client reconciliation (P0-B.3).

The missing §5 link: a ``grabbed`` wanted row used to freeze forever — nothing
ever compared it back to the library (is the episode/movie actually THERE?)
or to the torrent client (is the torrent even still around?). This module is
the single reconciliation pass, pure over the acquire ports:

- ``grabbed``/``pending``/``searching`` + the library owns the work → ``done``
  (an owned work must never be searched or re-fetched — covers the
  resurrected-then-indexed shape);
- ``grabbed`` + torrent vanished + NOT owned     → back to ``pending``
  (the grab never landed; cadence/cutoff pacing takes over again);
- ``grabbed`` + torrent still present            → left alone (downloading /
  seeding — the pipeline will land it, then the next pass closes it).

Season rows (``kind == "season"``) go through the SAME sweep. Their ownership
answer cannot come from the per-file ``ownership.owns`` port (it has no
season-level notion), so it is derived from the aired catalog instead: a season
row is « owned » iff its follow's cached catalog lists at least one aired
episode for that season AND every one of them is owned. Any blind spot — no
``followed_id``, an unreadable or empty catalog, partial ownership — answers
« not owned », so the row falls through to the hash paths (vanished → requeue,
intent → confirm, else in flight) rather than being mis-closed. Skipping season
rows wholesale was the original bug: a ``grabbed`` season could never close
``done``, a vanished season torrent was never requeued, and a crash-window
``searching`` season was never confirmed.

Import direction: acquire/ downward only — ownership arrives through the
``core.ownership.OwnershipChecker`` port (never the indexer implementation),
client hashes as a plain set gathered by the caller. Called from the
``follow detect`` and ``grab`` CLIs (commands/ composition layer), and its
counts land in their observable run rows (``steps_json.counts``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.core.ownership import OwnershipChecker

log = get_logger("acquire.reconcile")


def _season_fully_owned(
    store: "AcquireStore",
    ownership: "OwnershipChecker",
    row: "WantedItem",
) -> bool:
    """Answer ownership for a SEASON wanted row from the aired catalog.

    The per-file ownership port has no season-level answer, so a season is
    « owned » iff the follow's cached aired catalog lists at least one episode
    for ``row.season`` AND :meth:`ownership.owns` holds for every one of them.
    Every blind spot answers ``False`` — a missing ``followed_id``, an
    unreadable or empty catalog, or partial ownership — so the caller never
    mis-closes a season row on missing knowledge; the row simply falls through
    to the hash-based paths.

    Args:
        store: The acquire store (``aired`` catalog-cache sub-store).
        ownership: The library ownership port (fail-soft ``False`` per episode).
        row: The ``kind == "season"`` wanted row.

    Returns:
        ``True`` iff the catalog is non-empty for the season and every aired
        episode of it is owned.
    """
    if row.followed_id is None or row.season is None:
        return False
    try:
        aired = store.aired.list_for_followed(row.followed_id)
    except Exception as exc:  # noqa: BLE001 — fail-soft: no catalog is no answer
        log.warning("acquire.reconcile.season_catalog_error", wanted_id=row.id, error=str(exc))
        return False
    episodes = [r.episode for r in aired if r.season == row.season]
    if not episodes:
        return False
    for episode in episodes:
        try:
            if not ownership.owns(row.media_ref, kind="episode", season=row.season, episode=episode):
                return False
        except Exception as exc:  # noqa: BLE001 — fail-soft: treat as not owned
            log.warning(
                "acquire.reconcile.ownership_error",
                wanted_id=row.id,
                season=row.season,
                episode=episode,
                error=str(exc),
            )
            return False
    return True


@dataclass(frozen=True)
class ReconcileSummary:
    """Counts of one reconciliation pass (feeds the run row / CLI output).

    Attributes:
        checked: How many ``grabbed`` rows were examined.
        closed_owned: Rows closed ``done`` because the library owns the work.
        requeued_missing: Rows requeued ``pending`` because the torrent
            vanished from the client and the work is not owned.
        still_in_flight: Rows left ``grabbed`` (torrent still known to the
            client, work not owned yet — download/seed in progress).
        closed_movie_followed_ids: ``followed_id`` of every ``kind == "movie"``
            row this pass ACTUALLY transitioned to ``done`` (mark_done returned
            ``True``). The D2-A retirement rule — a followed film leaves the
            follow list once its media lands — reads this to retire the follow
            and emit ``FilmAcquired``. Populated only for movie rows carrying a
            ``followed_id``; empty for episode rows (a series continues). Kept as
            a plain tuple so ``reconcile_wanted`` stays pure over the ports (no
            bus, no follow mutation): the caller owns the retirement + emission.
    """

    checked: int = 0
    closed_owned: int = 0
    requeued_missing: int = 0
    confirmed_grabbed: int = 0
    still_in_flight: int = 0
    closed_movie_followed_ids: tuple[int, ...] = ()


def reconcile_wanted(
    store: "AcquireStore",
    ownership: "OwnershipChecker",
    client_hashes: set[str] | None,
    *,
    record_obligation: "Callable[[str], bool] | None" = None,
) -> ReconcileSummary:
    """Reconcile every ``grabbed`` wanted row against library + client truth.

    Idempotent: every transition is guarded on the current status in SQL, so a
    concurrent pass (web-triggered detect vs cron grab) can never double-apply.
    Fail-soft per row — one bad row never aborts the sweep.

    Args:
        store: The acquire store (single-writer discipline via its sub-stores).
        ownership: The library ownership port (provider-ID keyed, live files
            only; fail-soft ``False`` — a locked/stale index leaves rows
            in flight rather than mis-closing them).
        client_hashes: Lowercase info-hashes currently known to the torrent
            client, or ``None`` when the client is unavailable — the
            vanished-torrent requeue AND the intent confirmation are then both
            skipped (fail-soft: never decide on a blind spot). Callers must
            build this set from ``store.wanted.hashes_in_flight()``, not from
            the grabbed rows alone: a pre-add intent hash sits on a 'searching' row
            and an unasked hash would read as « vanished ».
        record_obligation: Optional writer invoked with the info-hash of a grab
            confirmed out of the add→confirm crash window, so the seed obligation the
            grab-time writer never got to record lands now
            (``DeleteAuthority.record_grab_obligation``). Fail-soft — it returns
            a bool and never raises into the sweep.

    Returns:
        The :class:`ReconcileSummary` counts.
    """
    checked = closed = requeued = confirmed = in_flight = 0
    closed_movie_followed_ids: list[int] = []
    # EVERY open status (OPEN_WANTED_STATUSES), because ownership — the file is
    # ON DISK — outranks whatever the queue thinks, whichever state the row is in:
    #
    #   * 'searching' — a row can hold a ``grabbed_hash`` while still reading
    #     'searching' (the §11(d) crash window between ``mark_grabbed`` and the
    #     next status write). ``reclaim_stale_searching`` deliberately refuses to
    #     revert that row (re-grabbing an already-added torrent would be worse),
    #     which leaves THIS sweep as the only thing that can close or requeue it.
    #   * 'available' — an owned row marked « À récupérer » is a standing order to
    #     re-download media the library already has. Skipping this status left
    #     exactly that order in place.
    #   * season rows walk the sweep too — their ownership answer comes from the
    #     aired catalog (see _season_fully_owned), and the hash paths below apply
    #     to them unchanged (vanished → requeue, intent → confirm, else in flight).
    for row in [
        *store.wanted.list_grabbed(),
        *store.wanted.list_searching(),
        *store.wanted.list_available(),
        *store.wanted.list_pending(),
    ]:
        if row.id is None:  # pragma: no cover — SELECT always carries the id
            continue
        checked += 1
        if row.kind == "season":
            # Per-file ownership has no season-level answer, so a season row's
            # ownership is derived from the aired catalog: non-empty for the
            # season AND every aired episode owned. Any blind spot (no
            # followed_id, empty/unreadable catalog, partial ownership) reads
            # « not owned » and the row falls through to the hash paths — a
            # season is never mis-closed on missing knowledge.
            owned = _season_fully_owned(store, ownership, row)
        else:
            try:
                owned = ownership.owns(
                    row.media_ref,
                    kind=row.kind,
                    season=row.season,
                    episode=row.episode,
                )
            except Exception as exc:  # noqa: BLE001 — fail-soft: treat as not owned
                log.warning("acquire.reconcile.ownership_error", wanted_id=row.id, error=str(exc))
                owned = False

        if owned:
            if store.wanted.mark_done(row.id):
                closed += 1
                # D2-A — a followed FILM whose media just landed is retired by
                # the caller (subscriber / detect CLI). Surface only rows this
                # pass ACTUALLY transitioned (mark_done returned True) so a
                # second, idempotent pass never re-emits FilmAcquired.
                if row.kind == "movie" and row.followed_id is not None:
                    closed_movie_followed_ids.append(row.followed_id)
                log.info(
                    "acquire.reconcile.closed_owned",
                    wanted_id=row.id,
                    kind=row.kind,
                    season=row.season,
                    episode=row.episode,
                )
            continue

        row_hash = (row.grabbed_hash or "").lower()
        if not row_hash:
            # An unowned row that never carried a grab simply stays queued — the
            # vanished-torrent logic below only applies to rows holding a hash.
            # Keyed on the HASH, not on ``status == 'grabbed'``: the hash is what
            # says « a torrent was added for this row », and it outlives the
            # status (crash window, legacy rows).
            continue

        if client_hashes is not None and row_hash not in client_hashes:
            if store.wanted.requeue_missing(row.id):
                requeued += 1
                log.warning(
                    "acquire.reconcile.requeued_missing",
                    wanted_id=row.id,
                    info_hash=row_hash,
                )
            continue

        # D2 — the row holds an INTENT (hash written before ``add()``) and the
        # torrent really is in the client: the add landed and only the status
        # write was lost. Confirm it as a REPLAY of the decision already taken,
        # then record the seed obligation the grab-time writer never reached.
        # Nothing here re-decides anything: an unconfirmed row would stay
        # 'searching' forever (``reclaim_stale_searching`` refuses a
        # hash-carrying row) with an unprotected torrent seeding on the side.
        if client_hashes is not None and row.status == "searching":
            if store.wanted.confirm_grab_intent(row.id, row_hash):
                confirmed += 1
                log.info(
                    "acquire.reconcile.confirmed_grabbed",
                    wanted_id=row.id,
                    info_hash=row_hash,
                )
                if record_obligation is not None:
                    try:
                        record_obligation(row_hash)
                    except Exception as exc:  # noqa: BLE001 — fail-soft: advisory write
                        log.warning(
                            "acquire.reconcile.obligation_failed",
                            wanted_id=row.id,
                            info_hash=row_hash,
                            error=str(exc),
                        )
            continue

        in_flight += 1

    summary = ReconcileSummary(
        checked=checked,
        closed_owned=closed,
        requeued_missing=requeued,
        confirmed_grabbed=confirmed,
        still_in_flight=in_flight,
        closed_movie_followed_ids=tuple(closed_movie_followed_ids),
    )
    log.info(
        "acquire.reconcile.complete",
        checked=summary.checked,
        closed_owned=summary.closed_owned,
        requeued_missing=summary.requeued_missing,
        confirmed_grabbed=summary.confirmed_grabbed,
        still_in_flight=summary.still_in_flight,
    )
    return summary


__all__ = ["ReconcileSummary", "reconcile_wanted"]
