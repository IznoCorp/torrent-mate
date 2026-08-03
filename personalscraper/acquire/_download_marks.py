"""Download-event emission marks (O4/D7).

One advisory row per grabbed torrent hash. The reconcile pass reads the mark,
emits only the transitions not yet recorded (started / 25-50-75 thresholds /
completed), and persists the mark BEFORE emitting (emit-after-persist: a crash
between persist and emit loses that emit rather than duplicating it — download
events are advisory). Marks are pruned when the hash no longer belongs to any
OPEN wanted row.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from personalscraper.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class DownloadMark:
    """One advisory download-emission mark keyed on torrent info-hash.

    Records which download-progress transitions have already been emitted
    for exactly-once event semantics (O4/D7).
    """

    info_hash: str
    started_emitted: bool
    last_threshold: int  # 0 | 25 | 50 | 75
    completed_emitted: bool


def _row_to_mark(row: sqlite3.Row) -> DownloadMark:
    """Decode a ``download_marks`` row into a :class:`DownloadMark`.

    Args:
        row: A :class:`sqlite3.Row` from the ``download_marks`` table.

    Returns:
        The decoded :class:`DownloadMark`.
    """
    return DownloadMark(
        info_hash=row["info_hash"],
        started_emitted=bool(row["started_emitted"]),
        last_threshold=row["last_threshold"],
        completed_emitted=bool(row["completed_emitted"]),
    )


class DownloadMarksStore:
    """Advisory store for download-progress emission marks (O4/D7).

    One row per grabbed torrent info-hash. The reconcile pass reads the mark
    before emitting any download event to ensure exactly-once semantics: the
    guarded ``try_*`` transitions persist the mark FIRST and answer whether
    THIS caller won the transition (rowcount discipline, like
    ``mark_done``) — so a crash never duplicates an event and two concurrent
    passes can never double-emit.

    Writes are wrapped in explicit ``BEGIN IMMEDIATE`` / ``COMMIT`` /
    ``ROLLBACK`` transactions, matching the acquire sub-store convention.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialise with the shared ``acquire.db`` connection.

        Args:
            conn: Shared :class:`sqlite3.Connection` to ``acquire.db``.
        """
        self._conn = conn

    def get(self, info_hash: str) -> DownloadMark | None:
        """Return the download mark for *info_hash*, or ``None``.

        Args:
            info_hash: Torrent info-hash (case-insensitive — stored lowercase).

        Returns:
            The :class:`DownloadMark` if present, else ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            "SELECT info_hash, started_emitted, last_threshold, completed_emitted "
            "FROM download_marks WHERE info_hash = ?",
            (info_hash.lower(),),
        ).fetchone()
        return _row_to_mark(row) if row is not None else None

    def upsert(
        self,
        info_hash: str,
        *,
        started: bool | None = None,
        threshold: int | None = None,
        completed: bool | None = None,
    ) -> None:
        """Insert or partially update a download mark.

        Only the non-None keyword arguments are written — a caller that passes
        only ``threshold=50`` leaves ``started_emitted`` and
        ``completed_emitted`` untouched. ``updated_at`` is always refreshed to
        the current epoch.

        Args:
            info_hash: Torrent info-hash (stored lowercase).
            started: If set, write ``started_emitted`` column.
            threshold: If set, write ``last_threshold`` column (0/25/50/75).
            completed: If set, write ``completed_emitted`` column.
        """
        insert_cols: list[str] = ["info_hash"]
        insert_vals: list[str] = ["?"]
        do_update: list[str] = []
        insert_params: list[object] = [info_hash.lower()]
        update_params: list[object] = []

        if started is not None:
            val = 1 if started else 0
            insert_cols.append("started_emitted")
            insert_vals.append("?")
            insert_params.append(val)
            do_update.append("started_emitted = ?")
            update_params.append(val)
        if threshold is not None:
            insert_cols.append("last_threshold")
            insert_vals.append("?")
            insert_params.append(threshold)
            do_update.append("last_threshold = ?")
            update_params.append(threshold)
        if completed is not None:
            val = 1 if completed else 0
            insert_cols.append("completed_emitted")
            insert_vals.append("?")
            insert_params.append(val)
            do_update.append("completed_emitted = ?")
            update_params.append(val)

        # updated_at is always refreshed — use SQL expression for INSERT, param for UPDATE.
        insert_cols.append("updated_at")
        insert_vals.append("CAST(strftime('%s', 'now') AS REAL)")
        do_update.append("updated_at = CAST(strftime('%s', 'now') AS REAL)")

        cols_clause = ", ".join(insert_cols)
        vals_clause = ", ".join(insert_vals)
        sets_clause = ", ".join(do_update)

        all_params = insert_params + update_params

        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                f"INSERT INTO download_marks ({cols_clause}) VALUES ({vals_clause}) "
                f"ON CONFLICT(info_hash) DO UPDATE SET {sets_clause}",
                all_params,
            )
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    def _claim(self, info_hash: str, update_sql: str, params: tuple[object, ...]) -> bool:
        """Run one guarded transition: ensure the row exists, then the guarded UPDATE.

        The ``INSERT OR IGNORE`` materialises a default row (all flags 0) so
        the guarded UPDATE always has a target; the UPDATE's ``WHERE`` clause
        carries the transition guard and its ``rowcount`` is the verdict —
        exactly ONE caller can win a given transition (mark_done rowcount
        discipline). Runs in a single ``BEGIN IMMEDIATE`` transaction so two
        concurrent passes serialize on the write.

        Args:
            info_hash: Torrent info-hash, already lowercased by the caller.
            update_sql: Guarded UPDATE statement (must touch ``updated_at``).
            params: Parameters for *update_sql*.

        Returns:
            ``True`` iff the guarded UPDATE changed exactly one row.
        """
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute("INSERT OR IGNORE INTO download_marks (info_hash) VALUES (?)", (info_hash,))
            cur = self._conn.execute(update_sql, params)
            claimed = cur.rowcount == 1
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")
        return claimed

    def try_mark_started(self, info_hash: str) -> bool:
        """Atomically claim the ``DownloadStarted`` emission for *info_hash*.

        Guarded on ``started_emitted = 0``: of two concurrent passes that both
        read « no mark », only the one whose UPDATE lands emits — the loser
        gets ``False`` and stays silent (exactly-once under concurrency).

        Args:
            info_hash: Torrent info-hash (case-insensitive — stored lowercase).

        Returns:
            ``True`` iff THIS call transitioned ``started_emitted`` 0 → 1.
        """
        h = info_hash.lower()
        return self._claim(
            h,
            "UPDATE download_marks SET started_emitted = 1, "
            "updated_at = CAST(strftime('%s', 'now') AS REAL) "
            "WHERE info_hash = ? AND started_emitted = 0",
            (h,),
        )

    def try_mark_completed(self, info_hash: str) -> bool:
        """Atomically claim the ``DownloadCompleted`` emission for *info_hash*.

        Guarded on ``completed_emitted = 0``; also sets ``started_emitted``
        (completion subsumes the start, matching the upsert the emission pass
        previously wrote).

        Args:
            info_hash: Torrent info-hash (case-insensitive — stored lowercase).

        Returns:
            ``True`` iff THIS call transitioned ``completed_emitted`` 0 → 1.
        """
        h = info_hash.lower()
        return self._claim(
            h,
            "UPDATE download_marks SET started_emitted = 1, completed_emitted = 1, "
            "updated_at = CAST(strftime('%s', 'now') AS REAL) "
            "WHERE info_hash = ? AND completed_emitted = 0",
            (h,),
        )

    def try_advance_threshold(self, info_hash: str, threshold: int) -> bool:
        """Atomically advance ``last_threshold`` to *threshold* (forward only).

        Guarded on ``last_threshold < threshold``: a concurrent pass that
        already advanced to (or past) *threshold* makes this call answer
        ``False``, and the mark can never move backwards.

        Args:
            info_hash: Torrent info-hash (case-insensitive — stored lowercase).
            threshold: The crossed threshold to claim (25/50/75).

        Returns:
            ``True`` iff THIS call advanced the threshold.
        """
        h = info_hash.lower()
        return self._claim(
            h,
            "UPDATE download_marks SET last_threshold = ?, "
            "updated_at = CAST(strftime('%s', 'now') AS REAL) "
            "WHERE info_hash = ? AND last_threshold < ?",
            (threshold, h, threshold),
        )

    def prune_stale(self, active_hashes: Iterable[str]) -> int:
        """Delete marks whose info-hash is not in *active_hashes*.

        Called after reconciliation to remove marks for torrents that are no
        longer tracked by any OPEN wanted row. All work runs in a single
        ``BEGIN IMMEDIATE`` transaction.

        Args:
            active_hashes: The set of info-hashes still referenced by at least
                one OPEN wanted row.

        Returns:
            The number of rows deleted.
        """
        active_set = {h.lower() for h in active_hashes}

        self._conn.row_factory = sqlite3.Row
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            if not active_set:
                cur = self._conn.execute("DELETE FROM download_marks")
                count = cur.rowcount
            else:
                all_rows = self._conn.execute("SELECT info_hash FROM download_marks").fetchall()
                stale = [r["info_hash"] for r in all_rows if r["info_hash"] not in active_set]
                for h in stale:
                    self._conn.execute("DELETE FROM download_marks WHERE info_hash = ?", (h,))
                count = len(stale)
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

        return count


__all__ = ["DownloadMark", "DownloadMarksStore"]
