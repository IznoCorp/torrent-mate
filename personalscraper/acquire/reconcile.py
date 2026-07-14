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
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.core.ownership import OwnershipChecker

log = get_logger("acquire.reconcile")


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
    """

    checked: int = 0
    closed_owned: int = 0
    requeued_missing: int = 0
    still_in_flight: int = 0


def reconcile_wanted(
    store: "AcquireStore",
    ownership: "OwnershipChecker",
    client_hashes: set[str] | None,
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
            vanished-torrent requeue is then skipped (fail-soft: never requeue
            on a blind spot).

    Returns:
        The :class:`ReconcileSummary` counts.
    """
    checked = closed = requeued = in_flight = 0
    for row in [*store.wanted.list_grabbed(), *store.wanted.list_pending()]:
        if row.id is None:  # pragma: no cover — SELECT always carries the id
            continue
        checked += 1
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
                log.info(
                    "acquire.reconcile.closed_owned",
                    wanted_id=row.id,
                    kind=row.kind,
                    season=row.season,
                    episode=row.episode,
                )
            continue

        if row.status != "grabbed":
            # An unowned pending row simply stays queued — the hash logic
            # below only applies to grabbed rows.
            continue

        row_hash = (row.grabbed_hash or "").lower()
        if client_hashes is not None and row_hash and row_hash not in client_hashes:
            if store.wanted.requeue_missing(row.id):
                requeued += 1
                log.warning(
                    "acquire.reconcile.requeued_missing",
                    wanted_id=row.id,
                    info_hash=row_hash,
                )
            continue

        in_flight += 1

    summary = ReconcileSummary(
        checked=checked,
        closed_owned=closed,
        requeued_missing=requeued,
        still_in_flight=in_flight,
    )
    log.info(
        "acquire.reconcile.complete",
        checked=summary.checked,
        closed_owned=summary.closed_owned,
        requeued_missing=summary.requeued_missing,
        still_in_flight=summary.still_in_flight,
    )
    return summary


__all__ = ["ReconcileSummary", "reconcile_wanted"]
