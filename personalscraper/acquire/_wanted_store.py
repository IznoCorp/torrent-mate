"""``wanted`` table sub-store (queue of episodes/movies to acquire).

Lives in its own module (not in ``store.py``) to keep the concrete store under
the 1000-line module-size hard ceiling — same precedent as ``_watch_store.py``.
Reads are lock-free (WAL); writes use ``BEGIN IMMEDIATE`` via the shared
``_write_tx`` context manager injected by :mod:`personalscraper.acquire.store`.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager

from personalscraper.acquire._store_rows import (
    _media_ref_to_json,
    _row_to_wanted,
    decode_tried_hashes,
)
from personalscraper.acquire.domain import (
    OPEN_WANTED_STATUSES,
    WantedItem,
    WantedKind,
    WantedStatus,
)
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
                   status, criteria_json, enqueued_at, last_search_at, attempts,
                   last_search_outcome, last_search_found, absorbed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    item.last_search_outcome,
                    item.last_search_found,
                    item.absorbed_by,
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
                   grabbed_hash, last_search_outcome, last_search_found,
                   tried_hashes_json, absorbed_by
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
            "status, criteria_json, enqueued_at, last_search_at, attempts, grabbed_hash, "
            "last_search_outcome, last_search_found, tried_hashes_json, absorbed_by "
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

    def list_searching(self) -> list[WantedItem]:
        """Return all ``wanted`` rows with ``status='searching'`` (reconciliation input).

        Unlike :meth:`list_stale_searching` this applies NO age threshold: the
        reconciliation sweep judges a row on library ownership and torrent-client
        truth, not on how long it has been claimed. It exists because a row can
        legitimately sit at 'searching' while holding a ``grabbed_hash`` — the
        §11(d) crash window between ``mark_grabbed`` and the next status write.
        :meth:`reclaim_stale_searching` refuses to revert that row (it would
        re-grab a torrent already added), so reconciliation is the ONLY path that
        can close it and it has to be able to see it.

        Returns:
            The 'searching' rows ordered by id (FIFO, like the other queues).
        """
        return self._list_wanted_by_status("searching", "id")

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

    def refund_search_attempt(self, wanted_id: int) -> bool:
        """Give back the attempt consumed by a claim whose search never concluded.

        :meth:`claim_for_search` stamps ``attempts + 1`` atomically with the transition
        to 'searching', i.e. BEFORE the verdict is known. A search that ends on a
        tracker outage must not count toward the starvation-escalation threshold, so
        the attempt is refunded explicitly here rather than conditionally skipped at
        claim time (which would reopen the TOCTOU race the atomic claim closed).

        Clamped at zero: a refund never drives ``attempts`` negative, whatever the
        interleaving.

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            ``True`` if the row existed and was updated; ``False`` otherwise.
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET attempts = MAX(attempts - 1, 0)
                WHERE id = ?
                """,
                (wanted_id,),
            )
            return cur.rowcount == 1

    def claim_for_grab(self, wanted_id: int, now: int) -> bool:
        """Atomically claim an AVAILABLE item for grabbing.

        Mirrors :meth:`claim_for_search` exactly, one guard apart: the ``WHERE``
        matches ``status='available'`` instead of ``'pending'``. That is what
        keeps the two passes from stealing each other's rows — the search pass
        only ever claims a queued item, the grab pass only ever claims an item a
        search already concluded takeable. One ``UPDATE`` inside a single
        ``BEGIN IMMEDIATE`` transaction is the SINGLE serialisation point for
        concurrent grabbers; ``attempts + 1`` and ``last_search_at = now`` are
        stamped atomically (``attempts`` counts every tracker interaction).

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            now: Unix epoch seconds (stamps ``last_search_at``).

        Returns:
            ``True`` if this caller won the claim; ``False`` otherwise (a
            concurrent winner, or a row that is no longer 'available').
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET status = 'searching',
                    attempts = attempts + 1,
                    last_search_at = ?
                WHERE id = ? AND status = 'available'
                """,
                (now, wanted_id),
            )
            return cur.rowcount == 1

    def reclaim_stale_searching(self, wanted_id: int, older_than: int) -> bool:
        """Atomically recover ONE stale 'searching' row back to 'pending'.

        Mirrors :meth:`claim_for_search`'s shape — a single rowcount-gated
        ``UPDATE`` inside one ``BEGIN IMMEDIATE`` transaction — because the
        recovery has exactly the same TOCTOU exposure the claim had. The
        previous get-then-set form read ``status`` from a row listed at the top
        of the pass and blindly wrote ``'pending'`` seconds later: by then the
        row could already have been grabbed by a concurrent runner, and the
        write silently reverted a COMPLETED grab (dropping its ``grabbed``
        status) or handed the same item to two passes at once.

        The ``grabbed_hash IS NULL`` guard is the second half of that safety:
        a 'searching' row that already carries a hash is the §11(d) crash
        window (``mark_grabbed`` persisted the hash, the process died before the
        next write). Such a row is NEVER reverted — reverting it would re-grab
        an already-added torrent. It belongs to the reconciliation path
        (:meth:`mark_done_by_hash` / :meth:`mark_done`), which closes it on the
        dispatch correlation.

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            older_than: Unix epoch seconds threshold (exclusive) — the row only
                recovers when ``last_search_at`` predates it, the SAME staleness
                predicate :meth:`list_stale_searching` applies.

        Returns:
            ``True`` iff this call recovered the row; ``False`` when it is no
            longer a hash-less stale 'searching' row (concurrent winner, a
            completed grab, or a fresher claim).
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET status = 'pending'
                WHERE id = ?
                  AND status = 'searching'
                  AND last_search_at < ?
                  AND grabbed_hash IS NULL
                """,
                (wanted_id, older_than),
            )
            return cur.rowcount == 1

    def record_grab_intent(self, wanted_id: int, info_hash: str) -> bool:
        """Reserve the chosen hash on a claimed row BEFORE the torrent is added (D2).

        The first half of the two-phase claim that closes the ``add()`` →
        ``mark_grabbed`` window. The row keeps ``status='searching'``: this is an
        *intention*, not a grab. If the process dies right after the add, the
        hash is already on the row, so the recovery is a REPLAY (confirm the
        torrent the client holds, record its seed obligation) instead of a fresh
        search that could add a second torrent for the same item.

        Guarded exactly like the claims — one rowcount-gated ``UPDATE`` inside a
        single ``BEGIN IMMEDIATE`` transaction:

        * ``status = 'searching'`` — only the runner holding the claim may write
          an intent;
        * ``grabbed_hash IS NULL`` — a row already carrying an intent belongs to
          the add that reserved it; a second writer must not clobber it (that
          would strand the first torrent with no row pointing at it).

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            info_hash: Info-hash of the release the grab is about to add.

        Returns:
            ``True`` iff this call reserved the row.
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET grabbed_hash = ?
                WHERE id = ?
                  AND status = 'searching'
                  AND grabbed_hash IS NULL
                """,
                (info_hash, wanted_id),
            )
            return cur.rowcount == 1

    def confirm_grab_intent(self, wanted_id: int, info_hash: str) -> bool:
        """Confirm an intent row whose torrent the client really holds (D2).

        The recovery counterpart of :meth:`record_grab_intent`: a 'searching' row
        carrying a hash that the torrent client still knows means the ``add()``
        DID land and only the status write was lost. This promotes it to
        'grabbed' — a replay of the decision already taken, never a new one.

        Guarded on ``status='searching'`` AND ``grabbed_hash IS NOT NULL`` so it
        is idempotent (a second sweep returns ``False``) and can never invent a
        grab for a row that holds no intent — that row is the stale sweep's.

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            info_hash: The confirmed info-hash (the client's value wins, so a
                case difference or a client-side normalisation is persisted).

        Returns:
            ``True`` iff this call confirmed the row.
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET status = 'grabbed', grabbed_hash = ?
                WHERE id = ?
                  AND status = 'searching'
                  AND grabbed_hash IS NOT NULL
                """,
                (info_hash, wanted_id),
            )
            return cur.rowcount == 1

    def clear_grab_intent(self, wanted_id: int) -> bool:
        """Release the reserved hash of a grab that never reached the client (D2).

        The counterpart of :meth:`record_grab_intent`, for the ordinary failure
        path rather than the crash path: ``resolve_source`` succeeded, the hash
        was reserved, and then ``add()`` returned a FAILURE. Nothing was handed
        to the torrent client, so the reservation must be given back.

        Left in place, that hash makes the row unreachable to every actor:
        :meth:`reclaim_stale_searching` refuses a hash-carrying row, the grab
        pass's hash guard short-circuits any re-claim, and the search pass only
        walks 'pending'. The pre-claim gate then returns ``"skipped"`` BEFORE it
        ever reaches the cutoff check, so the row is not even aged out — it
        stops moving entirely, and the only actor left able to free it is
        ``reconcile_wanted`` with a REACHABLE torrent client, i.e. exactly what
        is missing when the add failed because the client was down.

        Guarded on ``status = 'searching'`` — the row must still be the claim
        this runner holds. That guard is what makes it impossible to disarm a
        CONFIRMED grab: once :meth:`mark_grabbed` (or
        :meth:`confirm_grab_intent`) promoted the row to 'grabbed', its hash
        points at a live torrent and this call becomes a no-op ``False``.
        Idempotent for the same reason plus ``grabbed_hash IS NOT NULL``.

        Args:
            wanted_id: Rowid of the claimed ``wanted`` row.

        Returns:
            ``True`` iff this call released a reserved hash.
        """
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET grabbed_hash = NULL
                WHERE id = ?
                  AND status = 'searching'
                  AND grabbed_hash IS NOT NULL
                """,
                (wanted_id,),
            )
            return cur.rowcount == 1

    def hashes_in_flight(self) -> set[str]:
        """Return the lowercase hashes of every OPEN row carrying one.

        The probe set the reconciliation asks the torrent client about. It spans
        :data:`~personalscraper.acquire.domain.OPEN_WANTED_STATUSES`, NOT just
        ``'grabbed'``: since D2 a 'searching' row can hold a pre-add intent, and
        probing only the grabbed rows would leave the client unasked about it —
        reconciliation would then read « absent from the client » and requeue a
        row whose torrent is very much alive, i.e. re-grab a duplicate.

        Returns:
            Lowercase info-hashes of the open rows that carry one (possibly empty).
        """
        open_statuses = tuple(sorted(OPEN_WANTED_STATUSES))
        placeholders = ", ".join("?" for _ in open_statuses)
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            f"SELECT lower(grabbed_hash) AS h FROM wanted "  # noqa: S608 — internal placeholders
            f"WHERE status IN ({placeholders}) AND grabbed_hash IS NOT NULL AND grabbed_hash != ''",
            open_statuses,
        ).fetchall()
        return {row["h"] for row in rows}

    def mark_grabbed(self, wanted_id: int, info_hash: str) -> None:
        """Persist ``status='grabbed'`` AND the ``info_hash`` (idempotence guard).

        Since D2 this is the CONFIRMATION half of the two-phase claim: the
        hash was already reserved by :meth:`record_grab_intent` before the add,
        and this write promotes the row to 'grabbed' with the client's
        authoritative hash.

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
        """Close every OPEN row carrying *info_hash* — return what closed.

        The §5 closure the lifecycle was missing: ``done`` existed in the status
        CHECK but had zero writers, so every grabbed row froze at ``grabbed`` and
        a followed FILM could never be auto-removed once acquired. This flips
        every OPEN row carrying *info_hash* to ``done`` and returns the closed
        rows so the caller can unfollow acquired movies and emit the visible
        trace.

        Caller status (stated plainly — the previous docstring claimed a
        dispatch-time correlation that does not exist): nothing in the package
        calls this today. The closure that actually runs is
        :func:`~personalscraper.acquire.reconcile.reconcile_wanted`, which works
        from library OWNERSHIP (:meth:`mark_done`) because a name+size
        correlation can never match a renamed or aggregated TV-show folder. This
        method is the by-hash counterpart, kept correct and tested for the
        callers that will use it — it is not dead-code-by-accident, and the
        distinction matters when reading a frozen row's history.

        The status filter is derived from
        :data:`~personalscraper.acquire.domain.OPEN_WANTED_STATUSES` — the SINGLE
        source of « which statuses are still open » — rather than a literal
        tuple that silently drifts each time a state ships. Two open states
        besides ``grabbed`` genuinely carry a hash: ``searching`` (the §11(d)
        crash window between ``mark_grabbed`` and the next status write) and
        ``available`` (a row force-reset while retaining ``grabbed_hash``).
        Omitting them left rows the pipeline had already dispatched frozen
        forever.

        The SELECT runs INSIDE the write transaction, before the UPDATE. Outside
        it, the read is unserialised: a concurrent writer could add, close or
        re-status a matching row in the gap, and the returned list would then
        describe a state that never existed — the caller would unfollow a film
        on the strength of a row somebody else had already closed, or miss one
        this call actually transitioned. ``BEGIN IMMEDIATE`` takes the writer
        lock for both statements, so the returned rows are exactly the rows the
        UPDATE touched.

        Args:
            info_hash: The dispatched torrent's info-hash (case-insensitive —
                normalized to the stored lowercase form).

        Returns:
            The rows that were transitioned (possibly empty), read back BEFORE
            the update so ``followed_id``/``kind`` are available to the caller.
        """
        # Sorted for a stable, deterministic SQL string (and stable test asserts).
        open_statuses = tuple(sorted(OPEN_WANTED_STATUSES))
        placeholders = ", ".join("?" for _ in open_statuses)
        self._conn.row_factory = sqlite3.Row
        with self._write_tx(self._conn):
            rows = self._conn.execute(
                f"""
                SELECT id, followed_id, media_ref_json, kind, season, episode,
                       status, criteria_json, enqueued_at, last_search_at, attempts,
                       grabbed_hash, last_search_outcome, last_search_found, absorbed_by
                FROM wanted
                WHERE status IN ({placeholders}) AND lower(grabbed_hash) = lower(?)
                """,  # noqa: S608 — placeholders are generated from an internal frozenset
                (*open_statuses, info_hash),
            ).fetchall()
            if rows:
                self._conn.execute(
                    f"UPDATE wanted SET status = 'done' "  # noqa: S608 — same internal placeholders
                    f"WHERE status IN ({placeholders}) AND lower(grabbed_hash) = lower(?)",
                    (*open_statuses, info_hash),
                )
        return [_row_to_wanted(r) for r in rows]

    def mark_done(self, wanted_id: int) -> bool:
        """Close ONE open row whose work the library owns (reconciliation).

        The ownership half of the B.3 reconciliation: when the library owns the
        episode/movie an open row was tracking, the row closes ``done``
        regardless of the info-hash path (which misses historical dispatches
        and renamed content). Never touches ``abandoned`` or ``done``
        (idempotent).

        « Open » is derived from
        :data:`~personalscraper.acquire.domain.OPEN_WANTED_STATUSES` — the SINGLE
        source — and not from a hand-written tuple. The literal it replaced said
        ``('pending', 'searching', 'grabbed')``: it predated the ``available``
        state and was never updated, so an owned row sitting at ``available``
        silently refused to close. Ownership is the strongest signal there is
        (the file is ON DISK), and it was being ignored for one whole state —
        the row stayed « À récupérer » and the grab pass would happily
        re-download media the library already had.

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            ``True`` iff the row transitioned (was still open).
        """
        open_statuses = tuple(sorted(OPEN_WANTED_STATUSES))
        placeholders = ", ".join("?" for _ in open_statuses)
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                f"UPDATE wanted SET status = 'done' "  # noqa: S608 — placeholders from an internal frozenset
                f"WHERE id = ? AND status IN ({placeholders})",
                (wanted_id, *open_statuses),
            )
            return cur.rowcount == 1

    def requeue_missing(self, wanted_id: int) -> bool:
        """Requeue an OPEN row carrying a hash whose torrent vanished from the client.

        The torrent is gone and the library does not own the work (the caller
        checked both): the grab never really landed, so the row goes back to
        ``pending`` (hash cleared) and the normal cadence/cutoff pacing takes
        over again.

        Guarded on ``grabbed_hash IS NOT NULL`` (there is nothing to requeue
        otherwise, and the guard makes a second call a no-op — idempotent) plus
        the OPEN statuses, derived from
        :data:`~personalscraper.acquire.domain.OPEN_WANTED_STATUSES` rather than
        the ``'grabbed'`` literal it used to carry. A hash-carrying row is not
        always 'grabbed': the §11(d) crash window leaves it at 'searching', and
        rows predating the atomic stale-recovery fix sit at 'pending' with a
        stale hash. Both were unreachable — the vanished torrent could never be
        requeued and the row never progressed again.

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            ``True`` iff the row transitioned.
        """
        open_statuses = tuple(sorted(OPEN_WANTED_STATUSES))
        placeholders = ", ".join("?" for _ in open_statuses)
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                f"UPDATE wanted SET status = 'pending', grabbed_hash = NULL "  # noqa: S608 — internal placeholders
                f"WHERE id = ? AND status IN ({placeholders}) AND grabbed_hash IS NOT NULL",
                (wanted_id, *open_statuses),
            )
            return cur.rowcount == 1

    def list_tried_hashes(self, wanted_id: int) -> tuple[str, ...]:
        """Return the info-hashes already grabbed-and-failed for this item.

        The grab path passes these as the ranking exclusion set so a re-search
        never re-picks a known-dead release (reswitch #342). Read-only; empty
        tuple when the row is gone or nothing has been tried.

        Args:
            wanted_id: Rowid of the ``wanted`` row.

        Returns:
            The tried info-hashes (lowercase), order-stable.
        """
        self._conn.row_factory = sqlite3.Row
        row = self._conn.execute(
            "SELECT tried_hashes_json FROM wanted WHERE id = ?",
            (wanted_id,),
        ).fetchone()
        return decode_tried_hashes(row["tried_hashes_json"]) if row is not None else ()

    def append_tried_hash(self, wanted_id: int, info_hash: str) -> None:
        """Remember *info_hash* as a release already grabbed-and-failed for this item.

        Idempotent: a hash already recorded is not duplicated. Hashes are stored
        lowercase. A blank hash or a missing row is a no-op.

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            info_hash: The failed release's info-hash.
        """
        normalized = info_hash.strip().lower()
        if not normalized:
            return
        with self._write_tx(self._conn):
            self._conn.row_factory = sqlite3.Row
            row = self._conn.execute(
                "SELECT tried_hashes_json FROM wanted WHERE id = ?",
                (wanted_id,),
            ).fetchone()
            if row is None:
                return
            existing = decode_tried_hashes(row["tried_hashes_json"])
            if normalized in existing:
                return
            self._conn.execute(
                "UPDATE wanted SET tried_hashes_json = ? WHERE id = ?",
                (json.dumps([*existing, normalized]), wanted_id),
            )

    def requeue_for_reswitch(self, wanted_id: int, failed_hash: str, now: int) -> bool:
        """Atomically remember the failed release AND requeue the row for a re-grab.

        The auto-reswitch (reswitch #342) calls this when a grabbed torrent is
        declared dead: *failed_hash* is appended to ``tried_hashes`` (so the next
        search excludes it) and the row goes back to ``pending`` with its
        ``grabbed_hash`` cleared — all in one transaction so a crash can never
        clear the hash without recording it (which would let the reswitch loop
        back to the same dead release). ``tried_hashes`` is preserved across the
        requeue; only ``grabbed_hash`` is cleared.

        The VERDICT is cleared too (``last_search_outcome`` / ``last_search_found``
        to NULL): it described the release just declared DEAD and excluded, so
        keeping it would let a surface read « À récupérer » — « a takeable candidate
        is known » — about the one candidate that is now on the exclusion list.
        Status and verdict stay in sync, as everywhere else.

        The cadence clock is RESET (``enqueued_at = now``, ``attempts = 0``,
        ``last_search_at = NULL``) — like :meth:`resurrect` — because the original
        clock is no longer fair: without it the cutoff gate would abandon a
        reswitched item whose original enqueue predates the cadence window on the
        very next pass, before it could be re-grabbed (review L1). The
        ``tried_hashes`` exclusion, not the attempt counter, is the loop guard, so
        resetting ``attempts`` cannot cause an infinite reswitch.

        Guarded on ``grabbed_hash IS NOT NULL`` + the OPEN statuses, mirroring
        :meth:`requeue_missing`, so a second call is a no-op (idempotent).

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            failed_hash: The stalled release's info-hash (appended to tried_hashes).
            now: Unix epoch seconds — the reswitched row's fresh ``enqueued_at``.

        Returns:
            ``True`` iff the row transitioned.
        """
        normalized = failed_hash.strip().lower()
        open_statuses = tuple(sorted(OPEN_WANTED_STATUSES))
        placeholders = ", ".join("?" for _ in open_statuses)
        with self._write_tx(self._conn):
            self._conn.row_factory = sqlite3.Row
            row = self._conn.execute(
                "SELECT tried_hashes_json FROM wanted WHERE id = ?",
                (wanted_id,),
            ).fetchone()
            if row is None:
                return False
            existing = decode_tried_hashes(row["tried_hashes_json"])
            merged = existing if (not normalized or normalized in existing) else (*existing, normalized)
            cur = self._conn.execute(
                f"UPDATE wanted SET status = 'pending', grabbed_hash = NULL, tried_hashes_json = ?, "  # noqa: S608
                f"enqueued_at = ?, attempts = 0, last_search_at = NULL, "
                f"last_search_outcome = NULL, last_search_found = NULL "
                f"WHERE id = ? AND status IN ({placeholders}) AND grabbed_hash IS NOT NULL",
                (json.dumps(list(merged)), now, wanted_id, *open_statuses),
            )
            return cur.rowcount == 1

    def absorb_episodes(self, season_wanted_id: int, episode_ids: tuple[int, ...]) -> int:
        """Transition episode wanteds to ``absorbed``, linking them to the season row.

        Called when a season wanted absorbs its live episode siblings (R5).
        Runs inside a single ``BEGIN IMMEDIATE`` transaction.

        Args:
            season_wanted_id: Rowid of the absorbing season ``wanted`` row.
            episode_ids: Rowids of the episode rows to absorb.

        Returns:
            Number of rows actually transitioned (may be less than len(episode_ids)
            if some were already absorbed/closed).
        """
        if not episode_ids:
            return 0
        placeholders = ", ".join("?" for _ in episode_ids)
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                f"UPDATE wanted SET status = 'absorbed', absorbed_by = ? "
                f"WHERE id IN ({placeholders}) AND status IN ('pending', 'searching', 'available')",
                (season_wanted_id, *episode_ids),
            )
            return cur.rowcount

    def fallback_season(self, season_wanted_id: int) -> bool:
        """Transition a season row to ``fallback_episodes`` — the cutoff path (R6).

        Guarded on ``kind='season'`` and OPEN_WANTED_STATUSES.

        Args:
            season_wanted_id: Rowid of the season ``wanted`` row.

        Returns:
            ``True`` iff the row transitioned.
        """
        open_statuses = tuple(sorted(OPEN_WANTED_STATUSES))
        placeholders = ", ".join("?" for _ in open_statuses)
        with self._write_tx(self._conn):
            cur = self._conn.execute(
                f"UPDATE wanted SET status = 'fallback_episodes' "
                f"WHERE id = ? AND kind = 'season' AND status IN ({placeholders})",
                (season_wanted_id, *open_statuses),
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

    def record_search_outcome(self, wanted_id: int, outcome: str, found: int | None) -> None:
        """Persist the verdict of the search that just ran for this item.

        Called once per search attempt, at EVERY exit path — including failures
        and outages. A path that forgets to call this leaves the item reading
        « Non vérifié » forever, a lie by omission of exactly the kind this
        feature removes.

        Status transitions are NOT this method's job — the orchestrator owns
        the status column. This method ONLY records what happened.

        Args:
            wanted_id: The ``wanted`` row that was searched.
            outcome: The named outcome (``no_candidates``, ``all_filtered``,
                ``trackers_unavailable``, ``available``, …). The full set is
                defined by the orchestrator's exit-path taxonomy (DESIGN §3.3).
            found: Number of TAKEABLE candidates — survivors of the
                exact-episode filter, the hard profile filters and the
                ``min_seeders`` floor. ``None`` when the search did NOT
                conclude (outage, open circuit, dead swarm): zero would
                falsely claim « I looked, there is nothing ».
        """
        with self._write_tx(self._conn):
            self._conn.execute(
                "UPDATE wanted SET last_search_outcome = ?, last_search_found = ? WHERE id = ?",
                (outcome, found, wanted_id),
            )

    def list_available(self) -> list[WantedItem]:
        """Items a search found takeable but the grab pass has not taken yet.

        This is the ONLY queue the grab pass walks. Bounding grab to this
        subset is what keeps its re-search cheap: it re-queries a handful of
        known-available items, never the whole pending backlog
        (NE-DOIT-PAS-8).

        Returns:
            The available items, ordered by id (same order as
            :meth:`list_pending` — FIFO fairness).
        """
        return self._list_wanted_by_status("available", "id")

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
                   grabbed_hash, last_search_outcome, last_search_found, absorbed_by
            FROM wanted
            WHERE status = 'searching' AND last_search_at < ?
            ORDER BY id
            """,
            (older_than,),
        ).fetchall()
        return [_row_to_wanted(r) for r in rows]

    def list_for_followed(self, followed_id: int, *, kind: WantedKind) -> list[WantedItem]:
        """Return EVERY ``wanted`` row of one follow, any status, ordered by id.

        Read-model support: a per-episode reader needs all the rows of a follow
        in ONE query (rather than one lookup per episode) AND it needs the
        closed rows too, because the « which row governs » rule is applied by
        the caller — :func:`~personalscraper.web.acquisition.states.select_wanted_facts`
        — not by a WHERE clause that each caller would have to re-invent.

        Args:
            followed_id: FK to the ``followed_series`` row.
            kind: ``"movie"`` or ``"episode"`` — the row family to return.

        Returns:
            The matching rows ordered by id ascending (oldest first, so the
            governing row is the last one a caller sees).
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts,
                   grabbed_hash, last_search_outcome, last_search_found, absorbed_by
            FROM wanted
            WHERE followed_id IS ? AND kind = ?
            ORDER BY id
            """,
            (followed_id, kind),
        ).fetchall()
        return [_row_to_wanted(r) for r in rows]

    def find(
        self,
        *,
        followed_id: int | None,
        kind: WantedKind,
        season: int | None,
        episode: int | None,
        statuses: tuple[str, ...] | None = None,
    ) -> WantedItem | None:
        """Return the first matching wanted row, or None (soft dedup guard).

        Uses ``IS`` for NULL-safe season/episode comparison to avoid false
        matches between episode rows (season/episode non-NULL) and future movie
        rows (season/episode NULL).

        Without ``statuses`` the lookup is status-agnostic and returns the
        OLDEST matching row — which is what callers deduplicating « does ANY
        row exist » want, but the wrong answer for callers that need the LIVE
        row when an older terminal one (``absorbed`` / ``fallback_episodes``)
        shares the same coordinates.

        Args:
            followed_id: FK to ``followed_series`` row, or ``None``.
            kind: ``"movie"``, ``"episode"`` or ``"season"``.
            season: Season number, or ``None``.
            episode: Episode number, or ``None``.
            statuses: When given, only rows whose ``status`` is in this tuple
                match — e.g. pass the open statuses to find the LIVE row and
                skip older closed rows with the same coordinates.

        Returns:
            The first matching :class:`WantedItem` if found, else ``None``.
        """
        self._conn.row_factory = sqlite3.Row
        query = """
            SELECT id, followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts,
                   grabbed_hash, last_search_outcome, last_search_found, absorbed_by
            FROM wanted
            WHERE followed_id IS ?
              AND kind = ?
              AND season IS ?
              AND episode IS ?
            """
        params: tuple[object, ...] = (followed_id, kind, season, episode)
        if statuses is not None:
            placeholders = ", ".join("?" for _ in statuses)
            query += f" AND status IN ({placeholders})"
            params += tuple(statuses)
        query += " ORDER BY id LIMIT 1"
        row = self._conn.execute(query, params).fetchone()
        return _row_to_wanted(row) if row is not None else None
