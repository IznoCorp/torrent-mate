"""The titles the library holds, read through the indexer (K3 P11c).

The suggestions refresh seeds the providers' recommendations with them. The library is read
through ``LibraryIndex.reader()`` → ``LibraryReader.live_items()``, each ``IndexItem.media_ref()``
(DESIGN § 2.11), never ``library.db`` by SQL.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Protocol

from personalscraper.indexer.library_view import IndexUnavailable
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.suggestions_refresh import HeldTitle
    from personalscraper.indexer.library_view import IndexItem

log = get_logger("app.acquisition.held_titles")

__all__ = ["held_titles"]


class _Reader(Protocol):
    """What is read of the library index."""

    def live_items(self) -> list[IndexItem]:
        """Read every live, identified row, the most recently added first."""
        ...


class _Index(Protocol):
    """The library index: :class:`~personalscraper.indexer.library_view.LibraryIndex`, or a test's."""

    def reader(self) -> AbstractContextManager[_Reader]:
        """Open a reader; raises ``IndexUnavailable`` when the index cannot be read."""
        ...


def held_titles(index: _Index) -> list[HeldTitle]:
    """Read the titles the library holds that carry a provider id.

    Args:
        index: The library index.

    Returns:
        Each title's provider ids and kind, the most recently added first; empty when the index
        cannot be read (the refresh then seeds from the follows alone).
    """
    try:
        with index.reader() as reader:
            items = reader.live_items()
    except IndexUnavailable:
        log.warning("app.acquisition.held_titles.index_unavailable")
        return []
    titles: list[HeldTitle] = []
    for item in items:
        ref = item.media_ref()
        if ref is not None:
            titles.append((ref, item.kind))
    return titles
