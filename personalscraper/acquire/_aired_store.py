"""``aired_episode`` catalog-cache sub-store (P0-B.1).

Caches the provider's aired catalog per followed series so the §5 read
surfaces (completeness matrix, series truth-table status) never have to poll
the provider synchronously. ``follow detect`` is the single writer (it polls
the catalog anyway); the web reads the cache lock-free.

Lives in its own module to keep ``store.py`` under the 1000-line ceiling —
same precedent as ``_watch_store.py`` / ``_wanted_store.py``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager

from personalscraper.acquire.domain import AiredEpisodeRow
from personalscraper.logger import get_logger

log = get_logger("acquire.aired_store")


class _AiredSubStore:
    """Writer + reader for the ``aired_episode`` catalog cache."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        write_tx: Callable[[sqlite3.Connection], AbstractContextManager[None]],
    ) -> None:
        """Initialise with the shared connection and write-tx context manager.

        Args:
            conn: Shared :class:`sqlite3.Connection` to ``acquire.db``.
            write_tx: The ``_write_tx`` context manager from
                :mod:`personalscraper.acquire.store` (BEGIN IMMEDIATE
                serialisation), passed as a callable to avoid a circular
                import.
        """
        self._conn = conn
        self._write_tx = write_tx

    def replace_for_followed(
        self,
        followed_id: int,
        episodes: Sequence[tuple[int, int, str | None, str]],
        *,
        now: int,
    ) -> int:
        """Replace the whole cached catalog of one followed series.

        Wholesale replacement keeps the cache exactly equal to the provider's
        latest aired view (a provider correction lands on the next pass).
        Called ONLY when the poll produced at least one episode — an empty
        poll (provider outage / Top Chef-style empty catalog) must NOT wipe a
        previously good cache, so callers skip the call instead.

        Args:
            followed_id: FK to the ``followed_series`` row.
            episodes: ``(season, episode, title, air_date)`` tuples. Duplicate
                ``(season, episode)`` pairs collapse (first wins).
            now: Unix epoch seconds stamped on every row.

        Returns:
            The number of rows written.
        """
        deduped: dict[tuple[int, int], tuple[int, int, str | None, str]] = {}
        for season, episode, title, air_date in episodes:
            deduped.setdefault((season, episode), (season, episode, title, air_date))
        with self._write_tx(self._conn):
            self._conn.execute("DELETE FROM aired_episode WHERE followed_id = ?", (followed_id,))
            self._conn.executemany(
                "INSERT INTO aired_episode (followed_id, season, episode, title, air_date, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(followed_id, s, e, t, d, now) for (s, e, t, d) in deduped.values()],
            )
        return len(deduped)

    def list_for_followed(self, followed_id: int) -> list[AiredEpisodeRow]:
        """Return the cached aired catalog of one followed series.

        Args:
            followed_id: FK to the ``followed_series`` row.

        Returns:
            Rows ordered by ``(season, episode)`` — empty when the series has
            never been cached (callers fall back to a live poll).
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            "SELECT followed_id, season, episode, title, air_date, updated_at "
            "FROM aired_episode WHERE followed_id = ? ORDER BY season, episode",
            (followed_id,),
        ).fetchall()
        return [
            AiredEpisodeRow(
                followed_id=r["followed_id"],
                season=r["season"],
                episode=r["episode"],
                title=r["title"],
                air_date=r["air_date"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]
