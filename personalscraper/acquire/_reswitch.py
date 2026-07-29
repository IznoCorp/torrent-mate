"""Auto-reswitch of a dead-stalled grab (reswitch #342).

A grabbed torrent that never progresses — the swarm is unreachable, the payload
broke, or it has been stuck past the deadline — leaves the acquisition card
claiming « en cours » while nothing moves (product-intent §2, a silent lie).
This pass reacts to it:

  * classify every ``grabbed`` row against its live torrent-client state
    (:func:`~personalscraper.acquire._stall.classify_stall`);
  * for each ``STALLED_DEAD`` verdict — atomically remember the dead release AND
    requeue the row (:meth:`requeue_for_reswitch`), remove the dead torrent from
    the client, and emit :class:`~personalscraper.acquire.events.GrabReswitched`.

The next SEARCH+GRAB cycle then re-searches, ranks EXCLUDING the remembered hash
(the exclusion is threaded into BOTH passes), and grabs a DIFFERENT release —
the requeued ``pending`` row is promoted by the search pass first, then grabbed.
A row whose torrent has *vanished* is NOT our job — that is the reconciliation's
``requeue_missing`` (absence, not stall) — so we skip any grabbed hash the client
no longer reports.

Ordering is load-bearing: ``requeue_for_reswitch`` (append-hash + requeue, one
transaction) runs BEFORE the delete, so a delete failure can never strand a row
that cleared its hash without recording it — which would let the reswitch loop
straight back onto the same dead release.

Import direction: acquire/ only. The torrent client arrives through a narrow
structural :class:`_StallClient` port so this module stays testable without a
real qBittorrent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from personalscraper.acquire._stall import StallVerdict, classify_stall
from personalscraper.acquire.events import GrabReswitched
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.reswitch")

# Default hard deadline: a torrent stalled longer than this is declared dead even
# when swarm health is unknown. A dead swarm (0 known seeds, 0 % progress) is
# switched immediately regardless — this only bounds the "stuck despite a swarm"
# case so a genuinely slow-but-alive download is given real time first.
DEFAULT_DEAD_AFTER_S = 2 * 60 * 60  # 2 hours


class _StallClient(Protocol):
    """The torrent-client surface the reswitch pass needs (structural)."""

    def get_by_hashes(self, hashes: set[str]) -> "list[TorrentItem]":
        """Return the client's records for a specific hash set."""
        ...

    def delete(self, hash: str, *, delete_files: bool = False) -> None:  # noqa: A002 — matches client API
        """Remove a torrent (optionally its files) from the client."""
        ...


@dataclass(frozen=True)
class ReswitchSummary:
    """Counts of one reswitch pass (feeds the run row / CLI output).

    Attributes:
        checked: How many ``grabbed`` rows with a live torrent were classified.
        reswitched: How many were dead-stalled and switched to another release.
    """

    checked: int = 0
    reswitched: int = 0


def _dead_reason(item: "TorrentItem") -> str:
    """Name why a torrent was declared dead (machine-stable token for the event)."""
    if item.error_reason is not None:
        return "broken"
    if item.progress == 0.0 and item.swarm_seeds == 0:
        return "dead_swarm"
    return "deadline"


def _grabbed_age_s(item: "TorrentItem", fallback_ts: int | None, now: float) -> float:
    """Seconds since the torrent was grabbed.

    Prefers the torrent's own ``added_on`` (the authoritative grab time from the
    client); falls back to the wanted row's last claim / enqueue timestamp when
    the client does not report an add time.

    Args:
        item: The torrent as read from the client.
        fallback_ts: The row's ``last_search_at`` or ``enqueued_at`` (Unix epoch).
        now: Current Unix epoch seconds.

    Returns:
        Age in seconds (never negative).
    """
    added = item.added_on.timestamp() if item.added_on is not None else fallback_ts
    if added is None:
        return 0.0
    return max(0.0, now - added)


def reswitch_stalled(
    store: "AcquireStore",
    torrent_client: _StallClient,
    now: float,
    *,
    event_bus: "EventBus",
    dead_after_s: float = DEFAULT_DEAD_AFTER_S,
) -> ReswitchSummary:
    """Switch every dead-stalled grabbed release for a fresh one (reswitch #342).

    Args:
        store: The acquire store (reads ``list_grabbed``; writes via
            ``requeue_for_reswitch``).
        torrent_client: The torrent client (``get_by_hashes`` + ``delete``).
        now: Current Unix epoch seconds (injected for determinism/testing).
        event_bus: The event bus — REQUIRED (a ``GrabReswitched`` is a visible
            trace, never optional).
        dead_after_s: Hard deadline past which a still-stalled torrent is dead
            even with an unknown swarm.

    Returns:
        A :class:`ReswitchSummary` with the checked / reswitched counts.
    """
    grabbed = store.wanted.list_grabbed()
    hashes = {row.grabbed_hash.lower() for row in grabbed if row.grabbed_hash}
    if not hashes:
        return ReswitchSummary()

    try:
        by_hash = {t.hash.lower(): t for t in torrent_client.get_by_hashes(hashes)}
    except Exception as exc:  # noqa: BLE001 — fail-soft: an unreachable client is not our error
        log.warning("acquire.reswitch.client_unavailable", error=str(exc))
        return ReswitchSummary()

    checked = 0
    reswitched = 0
    for row in grabbed:
        if row.grabbed_hash is None or row.id is None:
            continue
        item = by_hash.get(row.grabbed_hash.lower())
        # Absence is the reconciliation's job (requeue_missing), not ours: a
        # vanished torrent is not a stall.
        if item is None:
            continue
        checked += 1
        age = _grabbed_age_s(item, row.last_search_at or row.enqueued_at, now)
        if classify_stall(item, age, dead_after_s=dead_after_s) is not StallVerdict.STALLED_DEAD:
            continue

        reason = _dead_reason(item)
        # Atomic append-hash + requeue FIRST — a delete failure afterwards can
        # never leave the hash unrecorded (which would loop back onto it). The
        # clock is reset (enqueued_at = now) so the cutoff does not abandon the
        # reswitched item before it can be re-grabbed (review L1).
        if not store.wanted.requeue_for_reswitch(row.id, row.grabbed_hash, int(now)):
            continue
        try:
            torrent_client.delete(row.grabbed_hash, delete_files=True)
        except Exception as exc:  # noqa: BLE001 — the requeue already happened; a lingering dead torrent is harmless
            log.warning(
                "acquire.reswitch.delete_failed",
                info_hash=row.grabbed_hash,
                error=str(exc),
            )
        event_bus.emit(GrabReswitched(media_ref=row.media_ref, old_hash=row.grabbed_hash, reason=reason))
        reswitched += 1
        log.info(
            "acquire.reswitch.switched",
            wanted_id=row.id,
            old_hash=row.grabbed_hash,
            reason=reason,
        )

    return ReswitchSummary(checked=checked, reswitched=reswitched)
