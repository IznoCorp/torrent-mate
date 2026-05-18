"""Torrent family base — TorrentItem dataclass and TorrentClient Protocol.

Implements DESIGN §5.1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class TorrentItem:
    """A torrent tracked by a torrent client.

    Attributes:
        hash: Torrent info hash.
        name: Torrent display name.
        size_bytes: Total size in bytes.
        progress: Download progress (0.0 to 1.0).
        state: Current torrent state (e.g. "uploading", "pausedUP").
        content_path: Filesystem path to torrent content.
        category: Torrent category label, if any.
        added_on: Timestamp when the torrent was added.
        ratio: Seed ratio (uploaded / downloaded). 0.0 if never seeded.
            Used by ``ingest`` to enforce ``config.ingest.min_ratio``.
    """

    hash: str
    name: str
    size_bytes: int
    progress: float
    state: str
    content_path: Path | None = None
    category: str | None = None
    added_on: datetime | None = None
    ratio: float = 0.0


# NOTE — provider-ids feature, sub-phase 13.1 :
# The historical monolithic ``TorrentClient(Protocol)`` defined here
# was dropped in favour of the 5 atomic capability protocols hosted in
# ``personalscraper.api.torrent._contracts``. The factory now returns
# the composite ``TorrentClientFull`` Protocol ; callers that need
# authentication widen with an ``isinstance(..., AuthenticatedClient)``
# check at the call site (DESIGN §4 — Composition par client).
