"""Filesystem-backed native board state store (anchor §6, §6.3).

One JSON document per project at ``<store_root>/board.json``.  Every
read-modify-write holds an exclusive advisory ``flock`` for the duration
(the proven discipline from :class:`~kanbanmate.adapters.store.fs_store.FsStateStore._lock`,
``fs_store.py:941-965``).  The new document is written to a temp file,
flushed + fsynced, then replaced atomically via ``os.replace`` (the same
discipline as ``FsStateStore.save``, ``fs_store.py:192-205``).

No new third-party dependency: stdlib ``json`` + ``fcntl`` + ``os.replace``
only (DESIGN §6.4).
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast


_EMPTY_DOC: dict[str, Any] = {
    "version": 0,
    "columns": [],
    "placement": {},
    "order": {},
    # board-sync (hybrid mode) bookkeeping — NEVER bumps ``version`` (no cheap_probe churn):
    #  * ``shadow``  — the last SYNCED forge column key per item (the value where native and GitHub
    #    last agreed). The baseline the reconcile compares against.
    #  * ``pending`` — a divergent forge value seen on the PREVIOUS tick but not yet adopted (the
    #    debounce candidate). A GitHub→native adoption fires only when the SAME divergent value is
    #    seen twice in a row, so GitHub's eventual-consistency echo of our own mirror writes (incl.
    #    an A→B→A bounce) never reverts the card.
    "shadow": {},
    "pending": {},
}


class FsBoardStateStore:
    """Atomic, flock-serialised ``board.json`` adapter (anchor §6.3).

    Attributes:
        root: The per-project store root (the directory that holds ``board.json``).
    """

    def __init__(self, root: Path) -> None:
        """Create the store adapter rooted at ``root``.

        Args:
            root: Directory to hold ``board.json`` (created on first write if absent).
        """
        self.root = root
        self._board_path = root / "board.json"
        self._lock_path = root / "board.lock"

    # ------------------------------------------------------------------
    # BoardStateStore
    # ------------------------------------------------------------------

    def load(self) -> dict[str, Any]:
        """Return the current ``board.json`` document (empty skeleton when absent).

        Returns:
            The parsed document, or a copy of ``_EMPTY_DOC`` when the file does not exist.

        Raises:
            ValueError: When ``board.json`` exists but is not parseable (corrupt / truncated).
        """
        if not self._board_path.exists():
            return dict(_EMPTY_DOC)
        return _parse_board(self._board_path)

    def place_card(
        self,
        item_id: str,
        column_key: str,
        index: int | None = None,
        *,
        if_version: int | None = None,
    ) -> int:
        """Move ``item_id`` to ``column_key`` at ``index`` (tail when ``None``).

        Args:
            item_id: The item to place.
            column_key: The destination column key.
            index: Target position within the column; ``None`` appends.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new version after the write.

        Raises:
            ValueError: Unknown ``column_key``; stale ``if_version``.
        """
        with self._lock():
            doc = self._read()
            _check_version(doc, if_version)
            if column_key not in doc["columns"]:
                raise ValueError(f"unknown column_key {column_key!r}; known: {doc['columns']}")
            # Remove from current column order list (wherever it lives).
            for col in doc["order"]:
                if item_id in doc["order"][col]:
                    doc["order"][col].remove(item_id)
            # Insert into destination order list.
            dest_order: list[str] = doc["order"].setdefault(column_key, [])
            if index is None:
                dest_order.append(item_id)
            else:
                # Validate the index fail-loud (DESIGN §10): ``list.insert`` would otherwise
                # silently clamp out-of-range and treat negatives as offset-from-end. ``bool`` is
                # an ``int`` subclass — reject it so a JSON ``true`` is not read as index 1.
                if isinstance(index, bool) or not isinstance(index, int):
                    raise ValueError(f"index must be an integer, got {index!r}")
                if not 0 <= index <= len(dest_order):
                    raise ValueError(
                        f"index {index} out of range for column {column_key!r} "
                        f"(valid 0..{len(dest_order)})"
                    )
                dest_order.insert(index, item_id)
            doc["placement"][item_id] = column_key
            doc["version"] += 1
            self._write(doc)
            return int(doc["version"])

    def set_sync_state(self, shadow: dict[str, str], pending: dict[str, str]) -> None:
        """Persist the hybrid board-sync bookkeeping (``shadow`` + ``pending``), NO version bump.

        ``shadow`` is the last synced forge column per item; ``pending`` is the debounce candidate
        (a divergent forge value awaiting a second confirming tick). Neither is a placement change,
        so this must NOT bump ``version`` (that would churn ``cheap_probe`` and re-trigger the tick).

        Args:
            shadow: The full ``{item_id: forge_column_key}`` synced map (replaces the prior one).
            pending: The full ``{item_id: forge_column_key}`` debounce-candidate map (replaces prior).
        """
        with self._lock():
            doc = self._read()
            doc["shadow"] = dict(shadow)
            doc["pending"] = dict(pending)
            self._write(doc)

    def reorder_column(
        self,
        column_key: str,
        ordered_item_ids: list[str],
        *,
        if_version: int | None = None,
    ) -> int:
        """Replace ``column_key``'s full ordered item list.

        Args:
            column_key: The column whose order to set.
            ordered_item_ids: The new full ordered list.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new version after the write.

        Raises:
            ValueError: Unknown column; unknown/duplicate/missing item id; stale version.
        """
        with self._lock():
            doc = self._read()
            _check_version(doc, if_version)
            if column_key not in doc["columns"]:
                raise ValueError(f"unknown column_key {column_key!r}; known: {doc['columns']}")
            current = set(doc["order"].get(column_key, []))
            proposed = ordered_item_ids
            # Reject duplicates.
            if len(proposed) != len(set(proposed)):
                raise ValueError("ordered_item_ids contains duplicate item ids")
            # Reject unknown ids (not in this column).
            unknown = set(proposed) - current
            if unknown:
                raise ValueError(f"item ids not in column {column_key!r}: {sorted(unknown)}")
            # Reject missing ids (items currently in the column that are absent).
            missing = current - set(proposed)
            if missing:
                raise ValueError(f"item ids missing from ordered_item_ids: {sorted(missing)}")
            doc["order"][column_key] = list(proposed)
            doc["version"] += 1
            self._write(doc)
            return int(doc["version"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        """Read ``board.json`` WITHOUT acquiring the lock (must be called inside ``_lock``).

        Returns:
            Parsed document, or a copy of ``_EMPTY_DOC`` when the file is absent.

        Raises:
            ValueError: When ``board.json`` exists but is not parseable (corrupt / truncated).
        """
        if not self._board_path.exists():
            return dict(_EMPTY_DOC)
        return _parse_board(self._board_path)

    def _write(self, doc: dict[str, Any]) -> None:
        """Atomically write ``doc`` to ``board.json`` (must be called inside ``_lock``).

        Uses a temp file in the same directory + ``os.replace`` so a concurrent
        reader never observes a torn file (the ``FsStateStore.save`` discipline,
        ``fs_store.py:202-205``).

        Args:
            doc: The document to persist.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self._board_path.with_name(f"board.{os.getpid()}.tmp")
        try:
            tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            tmp_fd = tmp.open("rb")
            try:
                os.fsync(tmp_fd.fileno())
            finally:
                tmp_fd.close()
            os.replace(tmp, self._board_path)
        except OSError:
            # On any I/O failure (disk full, permissions), don't leave a board.<pid>.tmp orphan
            # accumulating in the store root. board.json itself stays intact (os.replace is atomic).
            tmp.unlink(missing_ok=True)
            raise

    @contextmanager
    def _lock(self) -> Generator[None, None, None]:
        """Hold an exclusive advisory ``flock`` on the board lock file.

        Mirrors ``FsStateStore._lock`` (``fs_store.py:940-966``): the lock file
        is opened in append mode, ``LOCK_EX`` acquired, released on exit even on
        exception.

        Yields:
            Nothing — the exclusive lock is held for the duration of the block.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        fh = self._lock_path.open("a+")
        acquired = False
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            acquired = True
            yield
        finally:
            if acquired:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            fh.close()


class VersionConflict(ValueError):
    """Raised when an ``if_version`` optimistic-concurrency precondition fails (anchor §6.2).

    A subclass of ``ValueError`` — so the port's documented ``Raises: ValueError`` contract and any
    existing ``except ValueError`` handler still hold — but a DISTINCT type so the HTTP layer maps
    it to ``409`` by ``isinstance`` rather than a brittle substring match on the message.
    """


def _parse_board(path: Path) -> dict[str, Any]:
    """Parse a ``board.json`` file, failing LOUD with a clear message on corruption.

    Args:
        path: The ``board.json`` path (already checked to exist).

    Returns:
        The parsed document.

    Raises:
        ValueError: When the file is not valid UTF-8 JSON (truncated / hand-edited / torn) — a clear,
            actionable message instead of a raw ``JSONDecodeError`` traceback out of the daemon tick.
    """
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"board.json at {path} is corrupt: {exc} — fix it or re-run 'kanban board import'"
        ) from exc


def _check_version(doc: dict[str, Any], if_version: int | None) -> None:
    """Raise :class:`VersionConflict` when ``if_version`` is set and does not match ``doc["version"]``.

    Args:
        doc: The current board document.
        if_version: The caller's precondition version, or ``None`` to skip.

    Raises:
        VersionConflict: When ``if_version`` is set and differs from ``doc["version"]``.
    """
    if if_version is not None and doc.get("version", 0) != if_version:
        raise VersionConflict(
            f"optimistic concurrency conflict: expected version {if_version}, "
            f"got {doc.get('version', 0)}"
        )


def seed_board(
    store: FsBoardStateStore,
    columns: list[str],
    placement: dict[str, str],
    order: dict[str, list[str]],
    version: int = 1,
) -> None:
    """Seed (or re-seed) ``board.json`` atomically — used by ``board import`` (anchor §8).

    Writes the document in one atomic replace under the lock, bumping version to
    ``version`` (typically 1 on first import, or the existing version + 1 on
    idempotent re-run).

    Args:
        store: The board store to seed.
        columns: Ordered column key list.
        placement: ``{item_id: column_key}`` map.
        order: ``{column_key: [item_id, ...]}`` map.
        version: The version to write (caller controls for idempotent re-run).
    """
    with store._lock():
        # Preserve the hybrid forge ``shadow`` across a re-import: dropping it would reset drift
        # tracking and could let the next tick capture a stale forge value mid mirror-echo. Read it
        # under the lock (the import recomputes placement/order, not the shadow bookkeeping).
        existing = store._read()
        doc: dict[str, Any] = {
            "version": version,
            "columns": list(columns),
            "placement": dict(placement),
            "order": {k: list(v) for k, v in order.items()},
            "shadow": dict(existing.get("shadow", {})),
            "pending": dict(existing.get("pending", {})),
        }
        store._write(doc)
