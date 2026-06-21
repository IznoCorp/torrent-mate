# Phase 01 — Native board store

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

## Gate

No prior phase required. This is the foundation — zero engine dependency.

## Goal

Create the `BoardStateStore` + `BoardOrdering` port protocols and the `FsBoardStateStore` adapter. This is the I/O primitive every other phase depends on: a JSON file holding ordered columns, placement map, and per-column ordered card list, protected by `fcntl.flock` + `os.replace`.

## Files

- **Create:** `src/kanbanmate/ports/store_board.py` — `BoardStateStore` + `BoardOrdering` Protocols
- **Create:** `src/kanbanmate/adapters/store/fs_board.py` — `FsBoardStateStore` (stdlib json + flock + os.replace)
- **Create:** `tests/adapters/test_fs_board.py` — store unit tests

## Key design facts (grounded)

- Lock discipline: `fcntl.flock(fh.fileno(), fcntl.LOCK_EX)` inside a context manager — identical to `fs_store.py:941-965`.
- Atomic write: write to `<path>.pid.tmp`, then `os.replace(tmp, path)` — identical to `fs_store.py:192-205`.
- `version` is a monotonic int bumped on EVERY mutating write inside the lock.
- `board.json` schema: `{"version": int, "columns": [str, ...], "placement": {item_id: col_key}, "order": {col_key: [item_id, ...]}}`.
- `place_card(item_id, column_key, index=None)`: appends to tail when `index is None`. Cross-column move removes from old column's `order` list, appends/inserts into new column's `order` list.
- `reorder_column(column_key, ordered_item_ids)`: replaces the column's full order list; rejects unknown / duplicate / missing item_ids — fail-loud `ValueError`.
- `if_version` optimistic concurrency: if the caller supplies a version and it doesn't match current, raise `ValueError` with a clear message (HTTP layer maps this to 409).
- Entry column = `columns[0]`.

---

### Task 1: Port protocols (`ports/store_board.py`)

**Files:**
- Create: `src/kanbanmate/ports/store_board.py`

**Interfaces:**
- Produces: `BoardStateStore` Protocol with `load() -> dict`, `place_card(item_id, col_key, index=None, if_version=None) -> int`, `reorder_column(col_key, ordered_item_ids, if_version=None) -> int`
- Produces: `BoardOrdering` Protocol (same `reorder_column` + `place_card` surface, segregated per DESIGN §4.3)

- [ ] **Step 1: Write the file**

```python
"""Port protocols for the native board state store (anchor §6.4).

Defines the read/write surface for the per-project ``board.json`` document:
a placement authority holding ordered columns, item→column mapping, and
per-column ordered item list. Separate from ``ports/board.py`` because this
is a persistence port (I/O), not a board-communication port.

``BoardOrdering`` is interface-segregated (the ``PullRequests``/
``ProjectStatusReporter`` precedent, ``ports/board.py:154,348``) — only the
helm HTTP API and ``kanban board`` CLI need reorder; the daemon tick never does.
"""

from __future__ import annotations

from typing import Any, Protocol


class BoardStateStore(Protocol):
    """Read/write the native board placement document (``board.json``).

    Every mutating call holds an exclusive ``flock`` for the duration of the
    read-modify-write and bumps the monotonic ``version`` counter inside the
    lock. Atomic replace (temp-file + ``os.replace``) ensures a concurrent
    reader never sees a torn file.
    """

    def load(self) -> dict[str, Any]:
        """Return the current ``board.json`` document (or an empty dict when absent).

        Returns:
            The parsed document; ``{}`` when the file does not yet exist.
        """
        ...

    def place_card(
        self,
        item_id: str,
        column_key: str,
        index: int | None = None,
        *,
        if_version: int | None = None,
    ) -> int:
        """Move ``item_id`` to ``column_key`` at ``index`` (tail when ``None``).

        Removes the item from its current column's order list (if present),
        inserts it into ``column_key``'s list at ``index`` or appends to the
        tail, updates ``placement``, bumps ``version``, writes atomically.

        Args:
            item_id: The ``ProjectV2Item`` node id to place.
            column_key: The destination column key (must be in ``columns``).
            index: Position within the column; ``None`` appends to the tail.
            if_version: When set, raises ``ValueError`` if the stored version
                does not match (optimistic concurrency — the HTTP layer maps
                this to ``409``).

        Returns:
            The new ``version`` after the write.

        Raises:
            ValueError: Unknown ``column_key``; stale ``if_version``.
        """
        ...

    def reorder_column(
        self,
        column_key: str,
        ordered_item_ids: list[str],
        *,
        if_version: int | None = None,
    ) -> int:
        """Replace ``column_key``'s full ordered item list.

        Validates that every ``item_id`` in ``ordered_item_ids`` is currently
        in ``column_key`` (no unknown / cross-column / duplicate ids), replaces
        the list, bumps ``version``, writes atomically.

        Args:
            column_key: The column whose order to set.
            ordered_item_ids: The new full ordered list of item ids in this column.
            if_version: Optimistic-concurrency precondition (see :meth:`place_card`).

        Returns:
            The new ``version`` after the write.

        Raises:
            ValueError: Unknown ``column_key``; unknown/duplicate/missing item id;
                stale ``if_version``.
        """
        ...


class BoardOrdering(Protocol):
    """Dedicated reorder/place capability — never on the engine hot path (anchor §4.3).

    Interface-segregated from ``BoardStateStore`` so callers that only need the
    ordering surface (helm HTTP API, ``kanban board`` CLI) do not depend on the
    full store. ``NativeBoardBackend`` satisfies both this protocol and
    ``BoardWriter``.
    """

    def reorder_column(
        self,
        column_key: str,
        ordered_item_ids: list[str],
        *,
        if_version: int | None = None,
    ) -> int:
        """Replace ``column_key``'s full ordered item list; return the new version.

        Args:
            column_key: The column whose order to set.
            ordered_item_ids: Full ordered item id list for the column.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new store version.

        Raises:
            ValueError: Unknown column; unknown/duplicate/missing item id; stale version.
        """
        ...

    def place_card(
        self,
        item_id: str,
        column_key: str,
        index: int | None = None,
        *,
        if_version: int | None = None,
    ) -> int:
        """Place ``item_id`` at ``(column_key, index)``; return the new version.

        Args:
            item_id: The item to place.
            column_key: The destination column key.
            index: Position within the column; ``None`` appends.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new store version.

        Raises:
            ValueError: Unknown column; stale version.
        """
        ...
```

- [ ] **Step 2: Commit**

```bash
git add src/kanbanmate/ports/store_board.py
git commit -m "feat(anchor): BoardStateStore + BoardOrdering port protocols"
```

---

### Task 2: Filesystem adapter (`adapters/store/fs_board.py`)

**Files:**
- Create: `src/kanbanmate/adapters/store/fs_board.py`

**Interfaces:**
- Consumes: `BoardStateStore` Protocol from `ports/store_board.py`
- Produces: `FsBoardStateStore(root: Path)` — satisfies `BoardStateStore` + `BoardOrdering`

- [ ] **Step 1: Write the file**

```python
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
from typing import Any


_EMPTY_DOC: dict[str, Any] = {
    "version": 0,
    "columns": [],
    "placement": {},
    "order": {},
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
        """
        if not self._board_path.exists():
            return dict(_EMPTY_DOC)
        return json.loads(self._board_path.read_text(encoding="utf-8"))

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
                raise ValueError(
                    f"unknown column_key {column_key!r}; known: {doc['columns']}"
                )
            # Remove from current column order list (wherever it lives).
            for col in doc["order"]:
                if item_id in doc["order"][col]:
                    doc["order"][col].remove(item_id)
            # Insert into destination order list.
            dest_order: list[str] = doc["order"].setdefault(column_key, [])
            if index is None:
                dest_order.append(item_id)
            else:
                dest_order.insert(index, item_id)
            doc["placement"][item_id] = column_key
            doc["version"] += 1
            self._write(doc)
            return doc["version"]

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
                raise ValueError(
                    f"unknown column_key {column_key!r}; known: {doc['columns']}"
                )
            current = set(doc["order"].get(column_key, []))
            proposed = ordered_item_ids
            # Reject duplicates.
            if len(proposed) != len(set(proposed)):
                raise ValueError("ordered_item_ids contains duplicate item ids")
            # Reject unknown ids (not in this column).
            unknown = set(proposed) - current
            if unknown:
                raise ValueError(
                    f"item ids not in column {column_key!r}: {sorted(unknown)}"
                )
            # Reject missing ids (items currently in the column that are absent).
            missing = current - set(proposed)
            if missing:
                raise ValueError(
                    f"item ids missing from ordered_item_ids: {sorted(missing)}"
                )
            doc["order"][column_key] = list(proposed)
            doc["version"] += 1
            self._write(doc)
            return doc["version"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        """Read ``board.json`` WITHOUT acquiring the lock (must be called inside ``_lock``).

        Returns:
            Parsed document, or a copy of ``_EMPTY_DOC`` when the file is absent.
        """
        if not self._board_path.exists():
            return {
                "version": 0,
                "columns": [],
                "placement": {},
                "order": {},
            }
        return json.loads(self._board_path.read_text(encoding="utf-8"))

    def _write(self, doc: dict[str, Any]) -> None:
        """Atomically write ``doc`` to ``board.json`` (must be called inside ``_lock``).

        Uses a temp file in the same directory + ``os.replace`` so a concurrent
        reader never observes a torn file (the ``FsStateStore.save`` discipline,
        ``fs_store.py:202-205``).

        Args:
            doc: The document to persist.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self._board_path.with_name(
            f"board.{os.getpid()}.tmp"
        )
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        tmp_fd = tmp.open("rb")
        try:
            os.fsync(tmp_fd.fileno())
        finally:
            tmp_fd.close()
        os.replace(tmp, self._board_path)

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


def _check_version(doc: dict[str, Any], if_version: int | None) -> None:
    """Raise ``ValueError`` when ``if_version`` is set and does not match ``doc["version"]``.

    Args:
        doc: The current board document.
        if_version: The caller's precondition version, or ``None`` to skip.

    Raises:
        ValueError: When ``if_version`` is set and differs from ``doc["version"]``.
    """
    if if_version is not None and doc.get("version", 0) != if_version:
        raise ValueError(
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
        doc: dict[str, Any] = {
            "version": version,
            "columns": list(columns),
            "placement": dict(placement),
            "order": {k: list(v) for k, v in order.items()},
        }
        store._write(doc)
```

- [ ] **Step 2: Run a quick smoke check (no tests yet)**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -c "
from kanbanmate.adapters.store.fs_board import FsBoardStateStore
import tempfile, pathlib
with tempfile.TemporaryDirectory() as d:
    s = FsBoardStateStore(pathlib.Path(d))
    print('load empty:', s.load())
"
```

Expected output: `load empty: {'version': 0, 'columns': [], 'placement': {}, 'order': {}}`

- [ ] **Step 3: Commit**

```bash
git add src/kanbanmate/adapters/store/fs_board.py
git commit -m "feat(anchor): FsBoardStateStore — flock + atomic-replace board.json adapter"
```

---

### Task 3: Store unit tests (`tests/adapters/test_fs_board.py`)

**Files:**
- Create: `tests/adapters/test_fs_board.py`

**Interfaces:**
- Consumes: `FsBoardStateStore`, `seed_board` from `adapters/store/fs_board.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for FsBoardStateStore — round-trip, version monotonicity,
flock concurrency, fail-loud validation, and torn-write safety (anchor §12.1).
"""

from __future__ import annotations

import json
import os
import pathlib
import threading

import pytest

from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board


@pytest.fixture()
def store(tmp_path: pathlib.Path) -> FsBoardStateStore:
    """A fresh store rooted at a temp directory."""
    return FsBoardStateStore(tmp_path)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

def test_load_absent_returns_empty(store: FsBoardStateStore) -> None:
    doc = store.load()
    assert doc == {"version": 0, "columns": [], "placement": {}, "order": {}}


def test_seed_then_load_round_trips(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog", "InProgress", "Done"],
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], "InProgress": [], "Done": []},
    )
    doc = s.load()
    assert doc["version"] == 1
    assert doc["columns"] == ["Backlog", "InProgress", "Done"]
    assert doc["placement"] == {"item1": "Backlog"}
    assert doc["order"]["Backlog"] == ["item1"]


# ---------------------------------------------------------------------------
# place_card — happy path
# ---------------------------------------------------------------------------

def test_place_card_append_to_tail(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog", "InProgress"],
        placement={"a": "Backlog", "b": "Backlog"},
        order={"Backlog": ["a", "b"], "InProgress": []},
    )
    v = s.place_card("a", "InProgress")
    doc = s.load()
    assert doc["placement"]["a"] == "InProgress"
    assert "a" not in doc["order"]["Backlog"]
    assert doc["order"]["InProgress"] == ["a"]
    assert doc["version"] == v == 2


def test_place_card_at_index(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["InProgress"],
        placement={"a": "InProgress", "b": "InProgress"},
        order={"InProgress": ["a", "b"]},
    )
    s.place_card("b", "InProgress", index=0)
    doc = s.load()
    assert doc["order"]["InProgress"] == ["b", "a"]


# ---------------------------------------------------------------------------
# place_card — fail-loud
# ---------------------------------------------------------------------------

def test_place_card_unknown_column_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={}, order={"Backlog": []})
    with pytest.raises(ValueError, match="unknown column_key"):
        s.place_card("item1", "NonExistent")


def test_place_card_stale_if_version_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={"x": "Backlog"}, order={"Backlog": ["x"]})
    with pytest.raises(ValueError, match="optimistic concurrency"):
        s.place_card("x", "Backlog", if_version=99)


# ---------------------------------------------------------------------------
# reorder_column — happy path
# ---------------------------------------------------------------------------

def test_reorder_column_sets_order(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog"],
        placement={"a": "Backlog", "b": "Backlog", "c": "Backlog"},
        order={"Backlog": ["a", "b", "c"]},
    )
    v = s.reorder_column("Backlog", ["c", "a", "b"])
    doc = s.load()
    assert doc["order"]["Backlog"] == ["c", "a", "b"]
    assert doc["version"] == v == 2


# ---------------------------------------------------------------------------
# reorder_column — fail-loud
# ---------------------------------------------------------------------------

def test_reorder_column_unknown_column_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={}, order={"Backlog": []})
    with pytest.raises(ValueError, match="unknown column_key"):
        s.reorder_column("NoSuchCol", [])


def test_reorder_column_duplicate_item_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog"],
        placement={"a": "Backlog"},
        order={"Backlog": ["a"]},
    )
    with pytest.raises(ValueError, match="duplicate"):
        s.reorder_column("Backlog", ["a", "a"])


def test_reorder_column_unknown_item_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={}, order={"Backlog": []})
    with pytest.raises(ValueError, match="not in column"):
        s.reorder_column("Backlog", ["ghost"])


def test_reorder_column_missing_item_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog"],
        placement={"a": "Backlog", "b": "Backlog"},
        order={"Backlog": ["a", "b"]},
    )
    with pytest.raises(ValueError, match="missing"):
        s.reorder_column("Backlog", ["a"])  # missing "b"


# ---------------------------------------------------------------------------
# Version monotonicity across writes
# ---------------------------------------------------------------------------

def test_version_monotonic_across_writes(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog", "InProgress"],
        placement={"a": "Backlog"},
        order={"Backlog": ["a"], "InProgress": []},
    )
    v1 = s.place_card("a", "InProgress")
    v2 = s.reorder_column("InProgress", ["a"])
    assert v1 == 2
    assert v2 == 3


# ---------------------------------------------------------------------------
# Concurrent writers — no lost update (flock serialisation)
# ---------------------------------------------------------------------------

def test_concurrent_writers_no_lost_update(tmp_path: pathlib.Path) -> None:
    """Two threads each place a distinct item; both must land."""
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog", "Done"],
        placement={"a": "Backlog", "b": "Backlog"},
        order={"Backlog": ["a", "b"], "Done": []},
    )

    errors: list[Exception] = []

    def move_a() -> None:
        try:
            s.place_card("a", "Done")
        except Exception as exc:
            errors.append(exc)

    def move_b() -> None:
        try:
            s.place_card("b", "Done")
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=move_a)
    t2 = threading.Thread(target=move_b)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"Concurrent write errors: {errors}"
    doc = s.load()
    assert set(doc["order"]["Done"]) == {"a", "b"}
    assert doc["version"] == 3  # seed=1, move_a=2, move_b=3 (or 3 regardless of order)


# ---------------------------------------------------------------------------
# Torn-write safety — interrupting before os.replace leaves prior file intact
# ---------------------------------------------------------------------------

def test_torn_write_prior_file_intact(tmp_path: pathlib.Path) -> None:
    """If the process is interrupted after writing the tmp but before os.replace,
    the original board.json is untouched."""
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog"],
        placement={"a": "Backlog"},
        order={"Backlog": ["a"]},
    )
    original = s.load()

    # Simulate a torn write: write a corrupt tmp file but do NOT replace.
    tmp = s._board_path.with_name(f"board.{os.getpid()}.tmp")
    tmp.write_text("{corrupt", encoding="utf-8")
    # Do NOT call os.replace — the original must be intact.

    doc = s.load()
    assert doc == original, "board.json must be unchanged after a torn tmp write"
    tmp.unlink(missing_ok=True)
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/adapters/test_fs_board.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run make check**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && make check
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/adapters/test_fs_board.py
git commit -m "test(anchor): FsBoardStateStore — round-trip, concurrency, fail-loud, torn-write"
```
