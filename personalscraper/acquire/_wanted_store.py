"""``wanted`` table sub-store (queue of episodes/movies to acquire).

Lives in its own module (not in ``store.py``) to keep the concrete store under
the 1000-line module-size hard ceiling — same precedent as ``_watch_store.py``.
Reads are lock-free (WAL); writes use ``BEGIN IMMEDIATE`` via the shared
``_write_tx`` context manager injected by :mod:`personalscraper.acquire.store`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager

from personalscraper.acquire._store_rows import (
    _media_ref_to_json,
    _row_to_wanted,
)
from personalscraper.acquire.domain import WantedItem, WantedKind, WantedStatus
from personalscraper.logger import get_logger

log = get_logger("acquire.wanted_store")


class _WantedSubStore:
    """Writer + reader for the ``wanted`` table."""

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

    def add(self, item: WantedItem) -> int:
        """Insert a :class:`WantedItem` row and return its rowid.

        Args:
            item: The :class:`WantedItem` to persist.

        Returns:
            The rowid of the newly inserted row.
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                INSERT INTO wanted
                  (followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.followed_id,
                    _media_ref_to_json(item.media_ref),
                    item.kind,
                    item.season,
                    item.episode,
                    item.status,
                    item.criteria_json,
                    item.enqueued_at,
                    item.last_search_at,
                    item.attempts,
                ),
            )
            row_id = cur.lastrowid
        assert row_id is not None  # noqa: S101 — INSERT always sets lastrowid
        return row_id

    def get(self, wanted_id: int) -> WantedItem | None:
        """Return the :class:`WantedItem` for *wanted_id*, or ``None``.

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            The :class:`WantedItem` if present, else ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            """
            SELECT id, followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts,
                   grabbed_hash
            FROM wanted WHERE id = ?
            """,
            (wanted_id,),
        ).fetchone()
        return _row_to_wanted(row) if row is not None else None

    def set_status(self, wanted_id: int, status: WantedStatus) -> None:
        """Transition the ``status`` column of a ``wanted`` row.

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            status: Target status (one of the CHECK-constrained enum values).
        """
        with self._write_tx(self._conn):
            self._conn.execute(
                "UPDATE wanted SET status = ? WHERE id = ?",
                (status, wanted_id),
            )

    def _list_wanted_by_status(self, status: str, order_by: str) -> list[WantedItem]:
        """Return ``wanted`` rows with *status*, ordered by *order_by*.

        Args:
            status: ``wanted.status`` to match (bound parameter — no injection).
            order_by: Trusted ORDER BY clause (internal literal — never user input).

        Returns:
            A list of :class:`WantedItem`, possibly empty.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            "SELECT id, followed_id, media_ref_json, kind, season, episode, "
            "status, criteria_json, enqueued_at, last_search_at, attempts, grabbed_hash "
            "FROM wanted WHERE status = ? ORDER BY " + order_by,  # noqa: S608 — order_by is an internal literal
            (status,),
        ).fetchall()
        return [_row_to_wanted(r) for r in rows]

    def list_pending(self) -> list[WantedItem]:
        """Return all ``wanted`` rows with ``status='pending'`` (idx_wanted_pending path)."""
        return self._list_wanted_by_status("pending", "id")

    def list_grabbed(self) -> list[WantedItem]:
        """Return all ``wanted`` rows with ``status='grabbed'`` (downloads read-model, A4)."""
        return self._list_wanted_by_status("grabbed", "last_search_at DESC, id")

    def claim_for_search(self, wanted_id: int, now: int) -> bool:
        """Atomically claim a pending item for searching.

        Runs one ``UPDATE … WHERE id=? AND status='pending'`` inside a single
        ``BEGIN IMMEDIATE`` transaction — the SINGLE serialisation point for
        concurrent grabbers (closes the TOCTOU race that ``get``-then-``set``
        left open). Stamps ``attempts + 1`` and ``last_search_at = now``
        atomically. Returns ``True`` iff this call won the claim
        (``cur.rowcount == 1``); a concurrent loser (or an already-claimed /
        non-pending row) gets ``False`` and must skip.

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            now: Unix epoch seconds (stamps ``last_search_at``).

        Returns:
            ``True`` if this caller won the claim; ``False`` otherwise.
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET status = 'searching',
                    attempts = attempts + 1,
                    last_search_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, wanted_id),
            )
            return cur.rowcount == 1

    def mark_grabbed(self, wanted_id: int, info_hash: str) -> None:
        """Persist ``status='grabbed'`` AND the ``info_hash`` (idempotence guard).

        Persisting the hash means a crash between ``add()`` and this write does
        NOT double-emit ``GrabSucceeded`` on re-run: the re-run sees the
        persisted hash / grabbed status and short-circuits (DESIGN §7).

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            info_hash: Torrent info-hash returned by ``TorrentAdder.add()``.
        """
        with self._write_tx(self._conn):
            self._conn.execute(
                """
                UPDATE wanted
                SET status = 'grabbed', grabbed_hash = ?
                WHERE id = ?
                """,
                (info_hash, wanted_id),
            )

    def mark_done_by_hash(self, info_hash: str) -> list[WantedItem]:
        """Close ``grabbed`` rows whose torrent was DISPATCHED — return what closed.

        The §5 closure the lifecycle was missing: ``done`` existed in the status
        CHECK but had zero writers, so every grabbed row froze at ``grabbed`` and
        a followed FILM could never be auto-removed once acquired. Called from
        the dispatch-time correlation (the same info-hash match that writes the
        seed obligation), this flips every ``grabbed`` row carrying *info_hash*
        to ``done`` and returns the closed rows so the caller can unfollow
        acquired movies and emit the visible trace.

        Args:
            info_hash: The dispatched torrent's info-hash (case-insensitive —
                normalized to the stored lowercase form).

        Returns:
            The rows that were transitioned (possibly empty), read back BEFORE
            the update so ``followed_id``/``kind`` are available to the caller.
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts,
                   grabbed_hash
            FROM wanted
            WHERE status = 'grabbed' AND lower(grabbed_hash) = lower(?)
            """,
            (info_hash,),
        ).fetchall()
        if not rows:
            return []
        with self._write_tx(self._conn):
            self._conn.execute(
                "UPDATE wanted SET status = 'done' WHERE status = 'grabbed' AND lower(grabbed_hash) = lower(?)",
                (info_hash,),
            )
        return [_row_to_wanted(r) for r in rows]

    def mark_done(self, wanted_id: int) -> bool:
        """Close ONE open row whose work the library owns (reconciliation).

        The ownership half of the B.3 reconciliation: when the library owns the
        episode/movie an open row was tracking, the row closes ``done``
        regardless of the info-hash path (which misses historical dispatches
        and renamed content). Covers every OPEN status — ``grabbed`` (the
        classic closure) and ``pending``/``searching`` (an owned work must
        never be searched again: the resurrected-then-indexed shape, e.g. an
        episode whose file predated its indexing). Never touches ``abandoned``
        or ``done`` (idempotent).

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            ``True`` iff the row transitioned (was still open).
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                "UPDATE wanted SET status = 'done' WHERE id = ? AND status IN ('pending', 'searching', 'grabbed')",
                (wanted_id,),
            )
            return cur.rowcount == 1

    def requeue_missing(self, wanted_id: int) -> bool:
        """Requeue a ``grabbed`` row whose torrent vanished from the client.

        The torrent is gone and the library does not own the work (the caller
        checked both): the grab never really landed, so the row goes back to
        ``pending`` (hash cleared) and the normal cadence/cutoff pacing takes
        over again. Guarded on ``status='grabbed'`` (idempotent).

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            ``True`` iff the row transitioned.
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                "UPDATE wanted SET status = 'pending', grabbed_hash = NULL WHERE id = ? AND status = 'grabbed'",
                (wanted_id,),
            )
            return cur.rowcount == 1

    def resurrect(self, wanted_id: int, now: int) -> bool:
        """Re-open an ``abandoned`` row for an episode that is still missing.

        B.4 repair: an abandon that fired while the episode simply was not on
        the trackers YET (the terminal ``no_candidates`` bug) must not be a
        life sentence. Detect calls this for aired-but-unowned episodes whose
        row is ``abandoned`` and still within the cadence cutoff window. The
        clock restarts (``enqueued_at = now``, ``attempts = 0``) because the
        original abandon was wrongful.

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            now: Unix epoch seconds (new ``enqueued_at``).

        Returns:
            ``True`` iff the row transitioned (was ``abandoned``).
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET status = 'pending', attempts = 0, enqueued_at = ?,
                    last_search_at = NULL, grabbed_hash = NULL
                WHERE id = ? AND status = 'abandoned'
                """,
                (now, wanted_id),
            )
            return cur.rowcount == 1

    def list_stale_searching(self, older_than: int) -> list[WantedItem]:
        """Return ``wanted`` rows stuck in 'searching' with ``last_search_at < older_than``.

        Feeds back into the run loop alongside :meth:`list_pending` to recover
        items whose process was killed mid-grab before any status write (no
        stuck-'searching' orphan — :meth:`list_pending` only returns 'pending').

        Args:
            older_than: Unix epoch seconds threshold (exclusive).

        Returns:
            A list of :class:`WantedItem` (possibly empty).
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts,
                   grabbed_hash
            FROM wanted
            WHERE status = 'searching' AND last_search_at < ?
            ORDER BY id
            """,
            (older_than,),
        ).fetchall()
        return [_row_to_wanted(r) for r in rows]

    def find(
        self,
        *,
        followed_id: int | None,
        kind: WantedKind,
        season: int | None,
        episode: int | None,
    ) -> WantedItem | None:
        """Return the first matching wanted row, or None (soft dedup guard).

        Uses ``IS`` for NULL-safe season/episode comparison to avoid false
        matches between episode rows (season/episode non-NULL) and future movie
        rows (season/episode NULL).

        Args:
            followed_id: FK to ``followed_series`` row, or ``None``.
            kind: ``"movie"`` or ``"episode"``.
            season: Season number, or ``None``.
            episode: Episode number, or ``None``.

        Returns:
            The first matching :class:`WantedItem` if found, else ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            """
            SELECT id, followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts,
                   grabbed_hash
            FROM wanted
            WHERE followed_id IS ?
              AND kind = ?
              AND season IS ?
              AND episode IS ?
            ORDER BY id
            LIMIT 1
            """,
            (followed_id, kind, season, episode),
        ).fetchone()
        return _row_to_wanted(row) if row is not None else None
