"""``CatalogueView``: the aired catalogue and the ownership checker, shared by the library services.

The catalogue store (``acquire.db``) and the ownership checker (``library.db``) are shared by
the reads and the sheets, and serialised by one lock, since a web request thread may call
while another runs. The view owns both: :meth:`CatalogueView.close` closes them, once, for
every service holding the view.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from datetime import date

from personalscraper.acquire.catalogue import CatalogueEpisode, CatalogueStore
from personalscraper.app.library.catalogue import Completeness, catalogue_key, completeness
from personalscraper.indexer.library_view import IndexItem, LibraryReader
from personalscraper.indexer.ownership import IndexerOwnershipChecker


class CatalogueView:
    """The aired catalogue crossed with what the library holds."""

    def __init__(self, *, catalogue: CatalogueStore, ownership: IndexerOwnershipChecker) -> None:
        """Hold the stores; nothing is opened yet.

        Args:
            catalogue: The aired catalogue's store (owned: closed by :meth:`close`).
            ownership: The ownership checker over ``library.db`` (owned: closed by :meth:`close`).
        """
        self._catalogue = catalogue
        self._ownership = ownership
        self._lock = threading.Lock()

    def close(self) -> None:
        """Close the catalogue store and the ownership checker (idempotent)."""
        with self._lock:
            self._catalogue.close()
            self._ownership.close()

    def episodes_at(self, key: tuple[str, str]) -> list[CatalogueEpisode] | None:
        """Read the catalogue of one show under a catalogue key.

        Args:
            key: ``(provider, id)`` as :func:`catalogue_key` names it.

        Returns:
            Its episodes, or ``None`` when it was never fetched.
        """
        with self._lock:
            return self._catalogue.episodes(*key)

    def catalogue_of(self, row: IndexItem) -> list[CatalogueEpisode] | None:
        """Read a show's catalogue under the key the refresh writes it at.

        Args:
            row: The show's row.

        Returns:
            Its episodes, or ``None`` when it was never fetched or carries no TVDB/TMDB id.
        """
        key = catalogue_key(row.ids, row.canonical_provider)
        if key is None:
            return None
        with self._lock:
            return self._catalogue.episodes(*key)

    def owned_pairs(self, row: IndexItem) -> set[tuple[int, int]]:
        """The ``(season, episode)`` pairs the library holds under a show's ids.

        Args:
            row: The show's row.

        Returns:
            The held pairs (empty for a row with no id).
        """
        ref = row.media_ref()
        if ref is None:
            return set()
        with self._lock:
            return self._ownership.owned_pairs(ref)

    def completeness(self, row: IndexItem, today: date) -> Completeness | None:
        """How much of what a show has aired the library holds.

        Args:
            row: The show's row.
            today: The reference date.

        Returns:
            The counts, or ``None`` for a movie or a show never catalogued.
        """
        if row.kind != "show":
            return None
        episodes = self.catalogue_of(row)
        if episodes is None:
            return None
        return completeness(episodes, self.owned_pairs(row), today)

    def library_completeness(
        self, reader: LibraryReader, rows: Sequence[IndexItem], today: date
    ) -> dict[int, Completeness]:
        """Measure every catalogued show of the library at once.

        The held episodes are read in one query and united over the rows sharing a
        catalogue key (a duplicate's rows hold one identity); each key's catalogue is read
        once.

        Args:
            reader: The open index.
            rows: The live rows.
            today: The reference date.

        Returns:
            ``{item_id: completeness}`` for the show rows whose catalogue is known.
        """
        held = reader.live_episode_pairs()
        by_key: dict[tuple[str, str], list[IndexItem]] = {}
        for row in rows:
            key = catalogue_key(row.ids, row.canonical_provider) if row.kind == "show" else None
            if key is not None:
                by_key.setdefault(key, []).append(row)
        measured: dict[int, Completeness] = {}
        for key, sharing in by_key.items():
            with self._lock:
                episodes = self._catalogue.episodes(*key)
            if episodes is None:
                continue
            owned = set().union(*(held.get(row.item_id, set()) for row in sharing))
            counts = completeness(episodes, owned, today)
            if counts is not None:
                for row in sharing:
                    measured[row.item_id] = counts
        return measured
