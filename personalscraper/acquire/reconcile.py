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

Download events (O4, seed-caps D6-D9): the same sweep is the single truthful
observation point for download progress, so it also emits ``DownloadStarted``
/ ``DownloadProgressed`` / ``DownloadCompleted`` for every open hash-carrying
row present in the client. Exactly-once semantics come from the advisory
``download_marks`` table: the mark is persisted BEFORE the emit
(emit-after-persist — a crash between persist and emit loses that emit rather
than duplicating it), and marks are pruned when the hash leaves the open set.

Import direction: acquire/ downward only — ownership arrives through the
``core.ownership.OwnershipChecker`` port (never the indexer implementation),
client state as a ``{hash: TorrentItem}`` mapping gathered by the caller.
Called from the ``follow detect`` and ``grab`` CLIs (commands/ composition
layer), and its counts land in their observable run rows
(``steps_json.counts``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.acquire.events import DownloadCompleted, DownloadProgressed, DownloadStarted
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import WantedItem
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.core.event_bus import EventBus
    from personalscraper.core.ownership import OwnershipChecker

log = get_logger("acquire.reconcile")

# D8 — DownloadProgressed fires on these crossings only, highest-first so a
# single pass emits at most ONE Progressed (a 0 → 0.60 jump emits 50, never
# 25 then 50).
_PROGRESS_THRESHOLDS: tuple[int, ...] = (75, 50, 25)


def _list_open_rows(store: "AcquireStore") -> "list[WantedItem]":
    """Return every OPEN wanted row (grabbed / searching / available / pending).

    The four statuses of ``OPEN_WANTED_STATUSES``, fetched through the
    per-status listers — the single row set both the reconciliation sweep and
    the download-event emission pass walk.

    Args:
        store: The acquire store.

    Returns:
        The open rows, grabbed first (sweep-order is not semantic).
    """
    return [
        *store.wanted.list_grabbed(),
        *store.wanted.list_searching(),
        *store.wanted.list_available(),
        *store.wanted.list_pending(),
    ]


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


def _resolve_provider(store: "AcquireStore", row_hash: str) -> str:
    """Resolve the tracker a grabbed release came from (truthful, fail-soft).

    The wanted row carries no tracker field; the seed obligation recorded at
    grab time (keyed on the info-hash, tracker read from the torrent's own
    tag) is the tracker of record. Answers ``"unknown"`` when no active
    obligation exists (manual grab, or a crash before the obligation write) —
    an honest miss, never an invented name.

    Args:
        store: The acquire store (``seed`` sub-store).
        row_hash: Lowercase info-hash of the grabbed release.

    Returns:
        The recorded tracker wire name, or ``"unknown"``.
    """
    try:
        obligation = store.seed.find_active_by_hash(row_hash)
    except Exception as exc:  # noqa: BLE001 — fail-soft: advisory read
        log.warning("acquire.reconcile.provider_lookup_failed", info_hash=row_hash, error=str(exc))
        return "unknown"
    return obligation.source_tracker if obligation is not None else "unknown"


def _emit_for_row(
    store: "AcquireStore",
    row: "WantedItem",
    row_hash: str,
    item: "TorrentItem",
    title_by_id: dict[int, str],
    event_bus: "EventBus",
) -> None:
    """Emit the download transitions not yet recorded for one row (D6-D9).

    Reads the row's :class:`~personalscraper.acquire._download_marks.DownloadMark`,
    compares the observed :attr:`TorrentItem.progress` against it and, for each
    transition not yet emitted, persists the mark FIRST then emits
    (emit-after-persist — exactly-once across passes, D7):

    - ``progress >= 1.0`` and not yet completed → ``DownloadCompleted`` only.
      An already-complete first sighting gets NO synthetic Started/Progressed
      backfill (events are observations, not history).
    - Otherwise: ``DownloadStarted`` if not yet started, then at most ONE
      ``DownloadProgressed`` for the highest 25/50/75 crossing above the
      persisted ``last_threshold`` (D8). Progress regressions (qBittorrent
      recheck) never re-emit lower thresholds — the mark only moves forward.

    Args:
        store: The acquire store (``download_marks`` + ``seed`` sub-stores).
        row: The open hash-carrying wanted row.
        row_hash: Lowercase info-hash of the row's grabbed release.
        item: The torrent client's live state for that hash.
        title_by_id: ``{followed_id: title}`` snapshot for the feed title.
        event_bus: The bus the download events fire on.
    """
    marks = store.download_marks
    mark = marks.get(row_hash)
    started = mark.started_emitted if mark is not None else False
    last_threshold = mark.last_threshold if mark is not None else 0
    completed = mark.completed_emitted if mark is not None else False

    # Feed title: the follow's title when the row belongs to one, else the
    # client's own display name — a real observation, never an invented label.
    title = title_by_id.get(row.followed_id, "") if row.followed_id is not None else ""
    if not title:
        title = item.name
    provider = _resolve_provider(store, row_hash)

    if item.progress >= 1.0:
        if not completed:
            marks.upsert(row_hash, started=True, completed=True)
            event_bus.emit(DownloadCompleted(info_hash=row_hash, title=title, provider=provider, kind=row.kind))
            log.info("acquire.reconcile.download_completed", wanted_id=row.id, info_hash=row_hash)
        return

    # A completed mark is FINAL. A qBittorrent recheck routinely drops the
    # observed progress back below 1.0 while the row is still open, and the
    # completed branch never advances ``last_threshold`` — without this guard
    # the sweep emitted phantom Started/Progressed AFTER the Completed (up to
    # one per remaining threshold). Completion is the last word (D7).
    if completed:
        return

    if not started:
        marks.upsert(row_hash, started=True)
        event_bus.emit(DownloadStarted(info_hash=row_hash, title=title, provider=provider, kind=row.kind))
        log.info("acquire.reconcile.download_started", wanted_id=row.id, info_hash=row_hash)

    crossed = next(
        (t for t in _PROGRESS_THRESHOLDS if item.progress * 100.0 >= t and t > last_threshold),
        None,
    )
    if crossed is not None:
        marks.upsert(row_hash, threshold=crossed)
        event_bus.emit(
            DownloadProgressed(info_hash=row_hash, title=title, progress=item.progress, threshold_pct=crossed)
        )
        log.info(
            "acquire.reconcile.download_progressed",
            wanted_id=row.id,
            info_hash=row_hash,
            threshold_pct=crossed,
        )


def _emit_download_events(
    store: "AcquireStore",
    client_items: "dict[str, TorrentItem]",
    event_bus: "EventBus",
) -> None:
    """Emit download events for every open hash-carrying row seen in the client.

    Runs AFTER the reconciliation sweep, over a fresh fetch of the open rows —
    a row the sweep just closed (owned) or requeued (hash cleared) is out of
    the set, so no event ever fires for a row that already left the open set.
    Fail-soft per row: one bad row (marks write, provider lookup, a raising
    subscriber) never aborts the others (DESIGN §4 — the event is skipped this
    pass, the persisted mark bounds the retry).

    Args:
        store: The acquire store.
        client_items: ``{lowercase info-hash: TorrentItem}`` from the caller.
        event_bus: The bus the download events fire on.
    """
    targets: list[tuple[WantedItem, str]] = []
    for row in _list_open_rows(store):
        row_hash = (row.grabbed_hash or "").lower()
        if row_hash and row_hash in client_items:
            targets.append((row, row_hash))
    if not targets:
        return

    try:
        title_by_id = {f.id: f.title for f in store.follow.list_all() if f.id is not None}
    except Exception as exc:  # noqa: BLE001 — fail-soft: titles degrade to the client name
        log.warning("acquire.reconcile.download_titles_unavailable", error=str(exc))
        title_by_id = {}

    for row, row_hash in targets:
        try:
            _emit_for_row(store, row, row_hash, client_items[row_hash], title_by_id, event_bus)
        except Exception as exc:  # noqa: BLE001 — fail-soft: one bad row never aborts the sweep
            log.warning(
                "acquire.reconcile.download_events_failed",
                wanted_id=row.id,
                info_hash=row_hash,
                error=str(exc),
            )


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
    client_items: "dict[str, TorrentItem] | None",
    *,
    event_bus: "EventBus",
    record_obligation: "Callable[[str], bool] | None" = None,
) -> ReconcileSummary:
    """Reconcile every ``grabbed`` wanted row against library + client truth.

    Idempotent: every transition is guarded on the current status in SQL, so a
    concurrent pass (web-triggered detect vs cron grab) can never double-apply.
    Fail-soft per row — one bad row never aborts the sweep. When the caller
    provides the client's live items, the pass also emits the download
    lifecycle events (Started / Progressed / Completed) with exactly-once
    marks (O4/D6-D9 — see :func:`_emit_for_row`).

    Args:
        store: The acquire store (single-writer discipline via its sub-stores).
        ownership: The library ownership port (provider-ID keyed, live files
            only; fail-soft ``False`` — a locked/stale index leaves rows
            in flight rather than mis-closing them).
        client_items: ``{lowercase info-hash: TorrentItem}`` for every torrent
            currently known to the client, or ``None`` when the client is
            unavailable — the vanished-torrent requeue, the intent confirmation
            AND the download-event emission are then all skipped (fail-soft:
            never decide on a blind spot). Callers must build this mapping from
            ``store.wanted.hashes_in_flight()``, not from the grabbed rows
            alone: a pre-add intent hash sits on a 'searching' row and an
            unasked hash would read as « vanished ».
        event_bus: The bus the download events fire on (REQUIRED — project
            contract: every emission site takes the bus explicitly).
        record_obligation: Optional writer invoked with the info-hash of a grab
            confirmed out of the add→confirm crash window, so the seed obligation the
            grab-time writer never got to record lands now
            (``DeleteAuthority.record_grab_obligation``). Fail-soft — it returns
            a bool and never raises into the sweep.

    Returns:
        The :class:`ReconcileSummary` counts.
    """
    # Every existing presence check below runs on the derived hash set — the
    # mapping's values only feed the download-event emission pass.
    client_hashes = set(client_items) if client_items is not None else None

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
    for row in _list_open_rows(store):
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

    # O4/D6 — the emission pass runs over a FRESH fetch of the open rows, so a
    # row the sweep just closed or requeued never fires an event. Skipped
    # entirely on a client blind spot (client_items is None): no observation,
    # no event.
    if client_items is not None:
        _emit_download_events(store, client_items, event_bus)

    # D7 — a mark lives only as long as its hash belongs to an OPEN wanted
    # row; the SAME sweep that closes/requeues a row prunes its mark. Advisory:
    # a prune failure never aborts the sweep.
    try:
        store.download_marks.prune_stale(store.wanted.hashes_in_flight())
    except Exception as exc:  # noqa: BLE001 — fail-soft: advisory prune
        log.warning("acquire.reconcile.marks_prune_failed", error=str(exc))

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
