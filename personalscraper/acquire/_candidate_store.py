"""``wanted_candidate`` sub-store (K3 P2, migration 027).

The ranked candidates a concluded search found for a wanted row, kept so a read of the
releases needs no tracker call. A concluded search replaces the previous set wholesale.
Nothing writes here yet: the search pass does, in a later phase.

Lives in its own module to keep ``store.py`` from growing — same precedent as
``_aired_store.py`` / ``_wanted_store.py``. Reads are lock-free (WAL); writes use
``BEGIN IMMEDIATE`` via the shared ``_write_tx`` context manager.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager

from personalscraper.acquire._store_rows import _row_to_candidate
from personalscraper.acquire.domain import WantedCandidate


class _CandidateSubStore:
    """Writer + reader for the ``wanted_candidate`` table."""

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

    def replace(self, wanted_id: int, rows: Sequence[WantedCandidate]) -> None:
        """Replace the whole candidate set of one wanted row.

        The delete and the inserts share one transaction: a failure (a duplicate rank, a
        missing wanted row) leaves the previous set as it was. An empty *rows* clears the
        set, which is what a concluded search that found nothing means.

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            rows: The new ranked set; each ``rank`` unique within it.

        Raises:
            sqlite3.IntegrityError: On a duplicate rank, or a missing wanted row (the
                foreign key), after the rollback.
        """
        with self._write_tx(self._conn):
            self._conn.execute("DELETE FROM wanted_candidate WHERE wanted_id = ?", (wanted_id,))
            self._conn.executemany(
                """
                INSERT INTO wanted_candidate
                  (wanted_id, rank, provider, title, info_hash, size_bytes, seeders,
                   resolution, source, language, score, season, episode, searched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        wanted_id,
                        c.rank,
                        c.provider,
                        c.title,
                        c.info_hash,
                        c.size_bytes,
                        c.seeders,
                        c.resolution,
                        c.source,
                        c.language,
                        c.score,
                        c.season,
                        c.episode,
                        c.searched_at,
                    )
                    for c in rows
                ],
            )

    def list_for(self, wanted_id: int) -> list[WantedCandidate]:
        """Return the candidate set of one wanted row, the best rank first.

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            The ranked candidates; empty when no search concluded for the row.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT rank, provider, title, info_hash, size_bytes, seeders, resolution,
                   source, language, score, season, episode, searched_at
            FROM wanted_candidate
            WHERE wanted_id = ?
            ORDER BY rank
            """,
            (wanted_id,),
        ).fetchall()
        return [_row_to_candidate(r) for r in rows]
