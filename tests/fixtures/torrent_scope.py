"""Shared fixtures of the scoped-readers tests: one shared client, two owners.

The client holds a torrent of the other instance (no category), one filed under
another non-empty category (``prod``) and one of this instance (category
``tm-preprod``); a reader under :data:`SCOPE` must see only the last, so a filter
that merely requires "has a category" is caught.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.api.torrent._base import TorrentItem
from personalscraper.api.torrent.qbittorrent import QBitClient
from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig, TorrentScope

SCOPE = TorrentScope(category="tm-preprod", download_root=Path("/srv/preprod"))
SCOPED_TORRENT_CONFIG = TorrentConfig(active="qbit", clients={"qbit": TorrentClientEntry(scope=SCOPE)})
UNSCOPED_TORRENT_CONFIG = TorrentConfig(active="qbit", clients={"qbit": TorrentClientEntry()})

PROD_HASH = "a" * 40
PREPROD_HASH = "b" * 40
OTHER_CATEGORY_HASH = "c" * 40
OTHER_CATEGORY = "prod"


def torrent(
    hash_: str,
    category: str | None,
    *,
    progress: float = 1.0,
    name: str | None = None,
    tags: list[str] | None = None,
) -> TorrentItem:
    """Build a torrent of the shared client.

    Args:
        hash_: Info hash.
        category: Client category, or ``None`` for the other instance's.
        progress: Download progress; ``1.0`` is completed.
        name: Display name (defaults to ``Movie.<hash prefix>``).
        tags: Tags; defaults to :data:`SCOPE`'s instance tags in its category (a
            torrent this instance added carries them), else none.

    Returns:
        The torrent item.
    """
    if tags is None:
        tags = list(SCOPE.instance_tags) if category == SCOPE.category else []
    return TorrentItem(
        hash=hash_,
        name=name or f"Movie.{hash_[:4]}",
        size_bytes=1_000,
        progress=progress,
        state="uploading" if progress >= 1.0 else "downloading",
        category=category,
        tags=tags,
        ratio=2.0,
    )


def shared_client(*, progress: float = 1.0) -> MagicMock:
    """Build a fake client holding the prod, other-category and preprod torrents.

    Args:
        progress: Progress of both torrents (``1.0`` completed, else downloading).

    Returns:
        A mock of a category-listing client answering the lister contract over the three torrents.
    """
    items = [
        torrent(PROD_HASH, None, progress=progress),
        torrent(OTHER_CATEGORY_HASH, OTHER_CATEGORY, progress=progress),
        torrent(PREPROD_HASH, "tm-preprod", progress=progress),
    ]
    # spec'd so the runtime-checkable capability check sees get_by_category, as it does on the real client
    client = MagicMock(spec=QBitClient)
    client.get_completed.return_value = [i for i in items if i.progress >= 1.0]
    client.get_all_hashes.return_value = {i.hash for i in items}
    client.get_by_hashes.side_effect = lambda hs: [i for i in items if i.hash in hs]
    client.get_by_category.side_effect = lambda category: [i for i in items if i.category == category]
    return client


class HashOnlyClient:
    """A client without categories (Transmission's shape): lists hashes and looks torrents up by hash.

    Attributes:
        by_hashes_calls: The hash sets ``get_by_hashes`` was asked for.
    """

    def __init__(self) -> None:
        """Hold the prod, other-category and preprod torrents."""
        self._items = [
            torrent(PROD_HASH, None),
            torrent(OTHER_CATEGORY_HASH, OTHER_CATEGORY),
            torrent(PREPROD_HASH, "tm-preprod"),
        ]
        self.by_hashes_calls: list[set[str]] = []

    def get_completed(self) -> list[TorrentItem]:
        """Return the completed torrents."""
        return list(self._items)

    def get_all_hashes(self) -> set[str]:
        """Return every hash."""
        return {i.hash for i in self._items}

    def get_by_hashes(self, hashes: set[str]) -> list[TorrentItem]:
        """Record the request and return the torrents of those hashes."""
        self.by_hashes_calls.append(set(hashes))
        return [i for i in self._items if i.hash in hashes]
