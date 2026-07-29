"""Stall classification for grabbed torrents (reswitch #342).

A followed item can be *grabbed* (a release sent to the torrent client) yet never
progress — the swarm is unreachable (tracker announces seeds that never connect),
the magnet's metadata never resolves, or the payload broke on disk. Such an item
is a silent lie: the acquisition card says « en cours » while nothing moves
(product-intent §2). The auto-reswitch reacts to it, but only after a pure,
testable verdict about *why* a download is stuck — this module is that verdict.

``classify_stall`` maps a :class:`TorrentItem` (+ how long ago it was grabbed) to
one of three verdicts:

  * ``HEALTHY`` — progressing or in a non-stalled state; leave it alone.
  * ``STALLED_RECOVERABLE`` — stalled but young and the swarm is alive or unknown;
    give it more time, do not switch yet.
  * ``STALLED_DEAD`` — broken, or stuck past the hard deadline, or provably dead
    swarm (0 connected seeds, 0 % progress); switch to another release now.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.api.torrent._base import TorrentItem


class StallVerdict(str, Enum):
    """Why (or whether) a grabbed torrent is stuck.

    Attributes:
        HEALTHY: Progressing, or in a non-stalled client state.
        STALLED_RECOVERABLE: Stalled but young / swarm alive-or-unknown — wait.
        STALLED_DEAD: Broken, past the hard deadline, or a dead swarm — reswitch.
    """

    HEALTHY = "healthy"
    STALLED_RECOVERABLE = "stalled_recoverable"
    STALLED_DEAD = "stalled_dead"


# qBittorrent download-family states that are NOT making progress: a genuinely
# stalled download (peers list empty) and a magnet whose metadata never resolves.
# Everything else in the download/seed families is either progressing or seeding.
_STALLED_STATES = frozenset({"stalleddl", "metadl"})


def classify_stall(
    item: TorrentItem,
    grabbed_age_s: float,
    *,
    dead_after_s: float,
) -> StallVerdict:
    """Classify why a grabbed torrent is (not) stuck.

    Args:
        item: The torrent as read from the client. ``item.error_reason`` marks a
            broken torrent (qBittorrent ``error`` / ``missingFiles``);
            ``item.progress`` is 0.0–1.0; ``item.swarm_seeds`` is the tracker's
            complete-copies count (``0`` = dead swarm, ``None`` = unknown).
        grabbed_age_s: Seconds since the release was grabbed. Used for the hard
            deadline past which a still-stalled download is declared dead even
            when swarm health is unknown.
        dead_after_s: The hard deadline in seconds. A torrent stalled longer than
            this is ``STALLED_DEAD`` regardless of swarm knowledge.

    Returns:
        The :class:`StallVerdict`.
    """
    # A broken torrent (data vanished, tracker error) never recovers on its own —
    # switch it, UNLESS it already completed. A 100 %-done torrent is the
    # pipeline's / reconciliation's business and may be seeding under a min-seed
    # obligation; the reswitch deletes files, so it must never discard a complete
    # download over a transient error state (review M2). A complete-but-errored
    # torrent falls through to the state check below → HEALTHY (left alone).
    if item.error_reason is not None and item.progress < 1.0:
        return StallVerdict.STALLED_DEAD

    state = item.state.strip().lower()
    if state not in _STALLED_STATES:
        return StallVerdict.HEALTHY

    # Stuck past the hard deadline → dead even if the swarm is unknown.
    if grabbed_age_s > dead_after_s:
        return StallVerdict.STALLED_DEAD

    # Never started AND a provably dead swarm (0 known seeds) → dead now; there is
    # nothing to wait for. ``swarm_seeds is None`` (unknown) does NOT qualify —
    # only a confirmed 0 switches early.
    if item.progress == 0.0 and item.swarm_seeds == 0:
        return StallVerdict.STALLED_DEAD

    # Stalled but young, and the swarm is alive or unknown → give it more time.
    return StallVerdict.STALLED_RECOVERABLE
