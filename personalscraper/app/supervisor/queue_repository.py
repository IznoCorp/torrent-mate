"""The queue of asked runs in ``app.db`` — rows ↔ :class:`~personalscraper.app.supervisor.model.RunRequest`.

Nothing more: no rule lives here (what joins what, which move is legal — those are the model's,
asked by the services). The base keeps its own constraints (the kind, the state and the settlement are
closed sets) and lets them surface as ``sqlite3.IntegrityError``.

The connection is in autocommit mode (``isolation_level=None``): a single statement commits on its
own, and a service that needs several calls to be one act wraps them in
:meth:`~personalscraper.app.store.store.AppStore.immediate`.

The connection is shared by the web's threads: every public method holds the store's lock.
"""

from __future__ import annotations

import sqlite3
import threading
from typing import Any, Final

from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import (
    RequestState,
    RunKind,
    RunRequest,
    RunTrigger,
    Settlement,
    WaitReason,
)
from personalscraper.core.identity import ItemId
from personalscraper.core.sqlite import serialised

_COLUMNS: Final = (
    "uid, kind, trigger, options_json, asked_by, asked_at, state, admitted_at, worker_pid,"
    " heartbeat_at, settled_at, settlement, wait_reason"
)

#: Oldest ask first; the row id breaks a tie in insertion order.
_FIFO: Final = "ORDER BY asked_at, rowid"


def _request(row: tuple[Any, ...]) -> RunRequest:
    """Build a request from a ``run_request`` row selected with ``_COLUMNS``.

    Args:
        row: The row.

    Returns:
        The request.
    """
    (uid, kind, trigger, options_json, asked_by, asked_at, state, admitted_at, worker_pid, heartbeat_at) = row[:10]
    settled_at, settlement, wait_reason = row[10:]
    return RunRequest(
        uid=RunUid(str(uid)),
        kind=RunKind(kind),
        trigger=RunTrigger(trigger),
        options_json=str(options_json),
        asked_by=AccountId(str(asked_by)),
        asked_at=float(asked_at),
        state=RequestState(state),
        admitted_at=None if admitted_at is None else float(admitted_at),
        worker_pid=None if worker_pid is None else int(worker_pid),
        heartbeat_at=None if heartbeat_at is None else float(heartbeat_at),
        settled_at=None if settled_at is None else float(settled_at),
        settlement=None if settlement is None else Settlement(settlement),
        wait_reason=None if wait_reason is None else WaitReason(wait_reason),
    )


def _values(request: RunRequest) -> tuple[object, ...]:
    """The columns of a request, in ``_COLUMNS`` order.

    Args:
        request: The request.

    Returns:
        Its column values.
    """
    return (
        request.uid,
        request.kind.value,
        request.trigger.value,
        request.options_json,
        request.asked_by,
        request.asked_at,
        request.state.value,
        request.admitted_at,
        request.worker_pid,
        request.heartbeat_at,
        request.settled_at,
        None if request.settlement is None else request.settlement.value,
        None if request.wait_reason is None else request.wait_reason.value,
    )


class QueueRepository:
    """The ``run_request`` rows over one ``app.db`` connection it is GIVEN; it opens nothing."""

    def __init__(self, conn: sqlite3.Connection, *, lock: threading.RLock | None = None) -> None:
        """Wrap an open, migrated ``app.db`` connection.

        Args:
            conn: The connection, in autocommit mode.
            lock: The lock every user of ``conn`` holds around it (the store's); a lock of
                its own when ``conn`` is this repository's alone.
        """
        self._conn = conn
        self._lock = lock if lock is not None else threading.RLock()

    @serialised
    def insert(self, request: RunRequest) -> None:
        """Store a new request.

        Args:
            request: The request, as :meth:`RunRequest.ask` made it; it is then read in its stored state.

        Raises:
            sqlite3.IntegrityError: If its uid is already taken.
        """
        self._conn.execute(
            f"INSERT INTO run_request ({_COLUMNS}) VALUES ({', '.join('?' * 13)})",  # noqa: S608 — fixed columns
            _values(request),
        )
        request.read_state = request.state

    @serialised
    def get(self, uid: RunUid) -> RunRequest | None:
        """One request by uid.

        Args:
            uid: Its key.

        Returns:
            The request, or ``None``.
        """
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM run_request WHERE uid = ?",  # noqa: S608 — fixed columns
            (uid,),
        ).fetchone()
        return None if row is None else _request(row)

    @serialised
    def first_queued(self) -> RunRequest | None:
        """The head of the queue: the oldest request still queued.

        Returns:
            The request, or ``None`` when nothing waits.
        """
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM run_request WHERE state = ? {_FIFO} LIMIT 1",  # noqa: S608 — fixed clauses
            (RequestState.QUEUED.value,),
        ).fetchone()
        return None if row is None else _request(row)

    @serialised
    def queued(self) -> tuple[RunRequest, ...]:
        """Every request still queued, in FIFO order (oldest ask first, insertion order on a tie).

        Returns:
            The queued requests; empty when nothing waits.
        """
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM run_request WHERE state = ? {_FIFO}",  # noqa: S608 — fixed clauses
            (RequestState.QUEUED.value,),
        ).fetchall()
        return tuple(_request(row) for row in rows)

    @serialised
    def running(self) -> list[RunRequest]:
        """Every request being run, oldest ask first.

        Returns:
            The running requests.
        """
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM run_request WHERE state = ? {_FIFO}",  # noqa: S608 — fixed clauses
            (RequestState.RUNNING.value,),
        ).fetchall()
        return [_request(row) for row in rows]

    @serialised
    def queued_like(self, kind: RunKind, options_json: str, item_id: ItemId | None) -> RunRequest | None:
        """The oldest queued request an ask of this kind and options could join.

        A rescrape is matched on its item; a pipeline run on its canonical options. The model's
        :meth:`RunRequest.joins` stays the rule: this only narrows the rows it is asked about.

        Args:
            kind: The kind of the ask.
            options_json: Its canonical options.
            item_id: Its item, for a rescrape; ``None`` for a pipeline run.

        Returns:
            The request, or ``None`` (always, for a rescrape with no item: it joins nothing).
        """
        if kind is RunKind.RESCRAPE and item_id is None:
            return None
        params: tuple[str | int, ...]
        if item_id is None:
            clause, params = "options_json = ?", (options_json,)
        else:
            clause, params = "json_extract(options_json, '$.item_id') = ?", (item_id,)
        row = self._conn.execute(
            f"SELECT {_COLUMNS} FROM run_request WHERE state = ? AND kind = ? AND {clause} {_FIFO} LIMIT 1",  # noqa: S608
            (RequestState.QUEUED.value, kind.value, *params),
        ).fetchone()
        return None if row is None else _request(row)

    @serialised
    def touch_heartbeat(self, uid: RunUid, now: float) -> bool:
        """Record a sign of life of a running request's worker; a request that is not running is left alone.

        Args:
            uid: The request's key.
            now: The epoch of the heartbeat.

        Returns:
            ``True`` when a running request's heartbeat was written; ``False`` when nothing matched
            (unknown, queued or settled).
        """
        cursor = self._conn.execute(
            "UPDATE run_request SET heartbeat_at = ? WHERE uid = ? AND state = ?",
            (now, uid, RequestState.RUNNING.value),
        )
        return cursor.rowcount == 1

    @serialised
    def save(self, request: RunRequest) -> bool:
        """Write a request's every field back, if its row is still in the state it was read in.

        A compare-and-set on :attr:`RunRequest.read_state`: a copy read before another writer moved
        the request (a worker settled it, the supervisor killed it) writes nothing, so it cannot
        resurrect it.

        Args:
            request: A request that was inserted.

        Returns:
            ``True`` when it was written (it is then read in its new state); ``False`` when the
            row's state moved meanwhile and nothing was written.

        Raises:
            LookupError: If no row has its uid.
        """
        assignments = ", ".join(f"{column.strip()} = ?" for column in _COLUMNS.split(",")[1:])
        cursor = self._conn.execute(
            f"UPDATE run_request SET {assignments} WHERE uid = ? AND state = ?",  # noqa: S608 — fixed columns
            (*_values(request)[1:], request.uid, request.read_state.value),
        )
        if cursor.rowcount == 1:
            request.read_state = request.state
            return True
        if self._conn.execute("SELECT 1 FROM run_request WHERE uid = ?", (request.uid,)).fetchone() is None:
            raise LookupError(f"no run request {request.uid}")
        return False
