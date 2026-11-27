"""``suggestion`` sub-store (K3 P11c, migration 028).

The deck of titles worth following that ``acquisition-suggestions-refresh`` builds from the
providers' recommendations. A refresh replaces the whole deck in one transaction; a read pages
it by the row's own rising key.

Lives in its own module to keep ``store.py`` from growing — same pattern as
``_candidate_store.py``. Reads are lock-free (WAL); writes use ``BEGIN IMMEDIATE`` via the
shared ``_write_tx`` context manager.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from typing import cast

from personalscraper.acquire.domain import FollowKind, SuggestionReason, SuggestionRow

_COLUMNS = "id, provider, provider_id, kind, title, year, rating, poster, reason, seed_key, refreshed_at, external_ids"


class _SuggestionSubStore:
    """Writer + reader for the ``suggestion`` table."""

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

    def replace_deck(self, rows: Sequence[SuggestionRow], *, asked_seeds: Mapping[str, int] | None = None) -> None:
        """Replace the whole deck with ``rows`` and note the seeds asked, in one transaction.

        The rows take rising keys in the order given, all later than any key a previous deck
        held (the key is never reused), so a cursor of an older deck lands before every row of
        this one.

        Args:
            rows: The new deck, in the order it is shown; each ``(provider, provider_id, kind)``
                unique within it. An empty sequence clears the deck.
            asked_seeds: The seeds this refresh asked, ``seed_key`` → unix time, written over what
                the table held for them; the seeds not named keep their time. ``None`` or empty
                writes none.

        Raises:
            sqlite3.IntegrityError: On a duplicate title or a value the table refuses, after the
                rollback: the previous deck stands.
        """
        with self._write_tx(self._conn):
            self._conn.execute("DELETE FROM suggestion")
            self._conn.executemany(
                """
                INSERT INTO suggestion
                  (provider, provider_id, kind, title, year, rating, poster, reason, seed_key, refreshed_at,
                   external_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.provider,
                        r.provider_id,
                        r.kind,
                        r.title,
                        r.year,
                        r.rating,
                        r.poster,
                        r.reason,
                        r.seed_key,
                        r.refreshed_at,
                        json.dumps(r.external_ids, sort_keys=True),
                    )
                    for r in rows
                ],
            )
            if asked_seeds:
                self._conn.executemany(
                    "INSERT OR REPLACE INTO suggestion_seed (seed_key, asked_at) VALUES (?, ?)",
                    list(asked_seeds.items()),
                )

    def seeds_asked_at(self) -> dict[str, int]:
        """Return when each seed was last asked.

        Returns:
            ``seed_key`` → the unix time of the last refresh in which a provider answered for the
            seed; a seed never asked is absent.
        """
        rows = self._conn.execute("SELECT seed_key, asked_at FROM suggestion_seed").fetchall()
        return {str(key): int(asked_at) for key, asked_at in rows}

    def after(self, cursor: int | None, limit: int) -> list[SuggestionRow]:
        """Return the deck's rows past a key, in the order they are shown.

        Args:
            cursor: The key of the last row already read, ``None`` to start at the head.
            limit: The most rows to return.

        Returns:
            At most ``limit`` rows with a key above ``cursor`` (``id`` populated), oldest key
            first; empty at the end of the deck, or when no refresh ever ran.
        """
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM suggestion WHERE id > ? ORDER BY id LIMIT ?",  # noqa: S608 — a constant column list
            (-1 if cursor is None else cursor, limit),
        ).fetchall()
        return [_to_row(r) for r in rows]

    def holds(self, provider: str, provider_id: str, kind: str) -> bool:
        """Whether the deck holds a title.

        Args:
            provider: The provider that recommended it.
            provider_id: Its id at that provider.
            kind: ``"movie"`` or ``"show"``.

        Returns:
            ``True`` when a row of the deck bears the three.
        """
        row = self._conn.execute(
            "SELECT 1 FROM suggestion WHERE provider = ? AND provider_id = ? AND kind = ?",
            (provider, provider_id, kind),
        ).fetchone()
        return row is not None

    def refreshed_at(self) -> int | None:
        """Return when the deck was last refreshed.

        Returns:
            The unix time of the refresh that wrote the deck; ``None`` when the deck is empty
            (never refreshed, or a refresh that found nothing).
        """
        value = self._conn.execute("SELECT MAX(refreshed_at) FROM suggestion").fetchone()[0]
        return None if value is None else int(value)


def _to_row(row: tuple[object, ...]) -> SuggestionRow:
    """Map a ``suggestion`` row, columns in :data:`_COLUMNS` order, to a :class:`SuggestionRow`.

    Args:
        row: The selected columns.

    Returns:
        The frozen row, its ``id`` set.
    """
    (
        row_id,
        provider,
        provider_id,
        kind,
        title,
        year,
        rating,
        poster,
        reason,
        seed_key,
        refreshed_at,
        external_ids,
    ) = row
    return SuggestionRow(
        id=cast(int, row_id),
        provider=cast(str, provider),
        provider_id=cast(str, provider_id),
        kind=cast(FollowKind, kind),
        title=cast(str, title),
        year=cast("int | None", year),
        rating=cast("float | None", rating),
        poster=cast("str | None", poster),
        reason=cast(SuggestionReason, reason),
        seed_key=cast(str, seed_key),
        refreshed_at=cast(int, refreshed_at),
        external_ids=cast("dict[str, str]", json.loads(cast(str, external_ids))),
    )
