"""Shared fixtures of the scoped-readers tests: one shared client, two owners.

The client holds a torrent of the other instance (no category) and one of this
instance (category ``tm-preprod``); a reader under :data:`SCOPE` must see only
the second.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.api.torrent._base import TorrentItem
from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig, TorrentScope

SCOPE = TorrentScope(category="tm-preprod", download_root=Path("/srv/preprod"))
SCOPED_TORRENT_CONFIG = TorrentConfig(active="qbit", clients={"qbit": TorrentClientEntry(scope=SCOPE)})
UNSCOPED_TORRENT_CONFIG = TorrentConfig(active="qbit", clients={"qbit": TorrentClientEntry()})

PROD_HASH = "a" * 40
PREPROD_HASH = "b" * 40


def torrent(hash_: str, category: str | None, *, progress: float = 1.0, name: str | None = None) -> TorrentItem:
    """Build a torrent of the shared client.

    Args:
        hash_: Info hash.
        category: Client category, or ``None`` for the other instance's.
        progress: Download progress; ``1.0`` is completed.
        name: Display name (defaults to ``Movie.<hash prefix>``).

    Returns:
        The torrent item.
    """
    return TorrentItem(
        hash=hash_,
        name=name or f"Movie.{hash_[:4]}",
        size_bytes=1_000,
        progress=progress,
        state="uploading" if progress >= 1.0 else "downloading",
        category=category,
        tags=[],
        ratio=2.0,
    )


def shared_client(*, progress: float = 1.0) -> MagicMock:
    """Build a fake client holding the prod torrent and the preprod torrent.

    Args:
        progress: Progress of both torrents (``1.0`` completed, else downloading).

    Returns:
        A mock answering the lister contract over the two torrents.
    """
    items = [torrent(PROD_HASH, None, progress=progress), torrent(PREPROD_HASH, "tm-preprod", progress=progress)]
    client = MagicMock()
    client.get_completed.return_value = [i for i in items if i.progress >= 1.0]
    client.get_all_hashes.return_value = {i.hash for i in items}
    client.get_by_hashes.side_effect = lambda hs: [i for i in items if i.hash in hs]
    return client
