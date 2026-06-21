# Phase 02 — NativeBoardBackend decorator

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

## Gate

Phase 01 must be complete and `make check` green:
- `src/kanbanmate/ports/store_board.py` exists with `BoardStateStore` + `BoardOrdering` Protocols.
- `src/kanbanmate/adapters/store/fs_board.py` exists with `FsBoardStateStore` + `seed_board`.
- `tests/adapters/test_fs_board.py` passes.

## Goal

Create the `NativeBoardBackend` adapter: a decorator over `GithubClient` that satisfies `BoardReader` + `BoardWriter` by overriding `cheap_probe`, `snapshot`, `move_card` against the native store while delegating all forge ops (`comment`, `issue_state`, `issue_context`, etc.) to the composed `GithubClient`. Also add the `BoardOrdering` Protocol to `ports/board.py`.

## Files

- **Modify:** `src/kanbanmate/ports/board.py` — add `BoardOrdering` re-export (import from `store_board`)
- **Create:** `src/kanbanmate/adapters/board/__init__.py` — empty package marker
- **Create:** `src/kanbanmate/adapters/board/native.py` — `NativeBoardBackend`
- **Create:** `tests/adapters/test_native_backend.py` — snapshot JOIN, cheap_probe, move+mirror tests

## Key design facts (grounded)

- `GithubClient.cheap_probe` signature: `cheap_probe(self) -> str` (`client.py:157`). The combined probe: `f"{store_version}:{forge_probe}"`.
- `GithubClient.snapshot` returns `BoardSnapshot(tickets=tuple[Ticket,...], fetched_at=float)` (`client.py:167-203`). Ticket fields: `item_id`, `issue_number`, `title`, `column_key`, `body` (`domain.py:76-80`).
- `GithubClient.move_card(item_id, column_key)` resolves `column_key` as a Status option **name** (not a key) via `field.options[column_key]` (`client.py:240-245`). So the mirror call must pass the **display name**, not the column key.
- The `option_name_for_key` callable injected at construction resolves `column_key → display name` for the mirror.
- `BoardSnapshot` and `Ticket` are in `core/domain.py` — `NativeBoardBackend` imports them from there (adapter → core is allowed).
- First-sight auto-registration: an issue present in the forge snapshot but absent from the native store is placed at `columns[0]` (entry column), via a single `store.place_card(item_id, columns[0])` inside `snapshot()`.
- Mirror failure is logged and swallowed (fail-soft, DESIGN §5.2).
- `reorder_column` and `place_card` on the backend call through to the `store` and do NOT call the mirror (order is never mirrored).

---

### Task 1: Add `BoardOrdering` to `ports/board.py`

**Files:**
- Modify: `src/kanbanmate/ports/board.py` (add import + re-export at the bottom)

- [ ] **Step 1: Write a failing test confirming `BoardOrdering` is importable from `ports.board`**

```python
# In tests/adapters/test_native_backend.py — add this first
def test_board_ordering_importable_from_ports_board() -> None:
    from kanbanmate.ports.board import BoardOrdering  # noqa: F401
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/adapters/test_native_backend.py::test_board_ordering_importable_from_ports_board -v
```

Expected: `ImportError` — `cannot import name 'BoardOrdering' from 'kanbanmate.ports.board'`.

- [ ] **Step 3: Add the re-export to `ports/board.py`**

Append at the bottom of `src/kanbanmate/ports/board.py` (after the last class, before the final newline):

```python
# Re-export for callers that access the ordering Protocol via the board port namespace.
# The definition lives in ``ports/store_board.py`` (interface segregation: the store
# port and the board-communication port are separate files — ``PullRequests`` precedent).
from kanbanmate.ports.store_board import BoardOrdering as BoardOrdering  # noqa: F401
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/adapters/test_native_backend.py::test_board_ordering_importable_from_ports_board -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/ports/board.py tests/adapters/test_native_backend.py
git commit -m "feat(anchor): re-export BoardOrdering from ports.board (interface segregation)"
```

---

### Task 2: `NativeBoardBackend` implementation (`adapters/board/native.py`)

**Files:**
- Create: `src/kanbanmate/adapters/board/__init__.py`
- Create: `src/kanbanmate/adapters/board/native.py`

**Interfaces:**
- Consumes: `FsBoardStateStore` + `seed_board` from `adapters.store.fs_board`
- Consumes: `GithubClient` from `adapters.github.client` (for forge delegation)
- Produces: `NativeBoardBackend(forge, store, columns, option_name_for_key, mirror=None)` — satisfies `BoardReader` + `BoardWriter` + `BoardOrdering`

- [ ] **Step 1: Create the package `__init__.py`**

```python
# src/kanbanmate/adapters/board/__init__.py
"""Native board backend adapter package (anchor §4.3)."""
```

- [ ] **Step 2: Write `adapters/board/native.py`**

```python
"""NativeBoardBackend: a decorator that repatriates board placement off GitHub (anchor §4.3).

Composes a forge client (``GithubClient``) for forge ops — issue state, comments,
PRs — and a ``FsBoardStateStore`` for placement authority. Only ``cheap_probe``,
``snapshot``, and ``move_card`` are overridden; every other ``BoardReader`` /
``BoardWriter`` method delegates to the forge client so the daemon tick sees a
structurally identical interface regardless of the selected backend.

The one-way GitHub mirror (§5): on ``move_card`` the native placement is written
first (authority), then mirrored to GitHub via the forge client's ``move_card``
with the **display name** (Status option name) resolved via ``option_name_for_key``.
A mirror failure is logged and swallowed — the native store is already updated.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from kanbanmate.adapters.github.types import CommentRef, IssueContext, IssueRef
from kanbanmate.adapters.store.fs_board import FsBoardStateStore
from kanbanmate.core.domain import BoardSnapshot, Ticket

logger = logging.getLogger(__name__)


class NativeBoardBackend:
    """Decorator over GithubClient — placement authority is the native store (anchor §4.3).

    Satisfies ``BoardReader``, ``BoardWriter``, and ``BoardOrdering``.

    Attributes:
        _forge: The underlying GithubClient (comment/issue/PR ops).
        _store: The native placement store (``FsBoardStateStore``).
        _columns: Ordered column key list (seeded from ``columns.yml`` order).
        _option_name_for_key: Callable resolving a column key → GitHub Status display name.
        _mirror: Optional forge client to mirror placements to GitHub (same as ``_forge``
            when enabled; ``None`` when ``board_mirror=False``).
    """

    def __init__(
        self,
        forge: Any,
        store: FsBoardStateStore,
        columns: list[str],
        option_name_for_key: Callable[[str], str],
        mirror: Any | None = None,
    ) -> None:
        """Construct the native backend.

        Args:
            forge: The GithubClient satisfying ``BoardReader``+``BoardWriter`` for forge ops.
            store: The native placement store.
            columns: Ordered column key list (entry column = ``columns[0]``).
            option_name_for_key: Maps a column key to the GitHub Status option display name.
            mirror: When non-``None``, move operations also call ``mirror.move_card``
                with the resolved display name (one-way mirror, §5).
        """
        self._forge = forge
        self._store = store
        self._columns = columns
        self._option_name_for_key = option_name_for_key
        self._mirror = mirror

    # ------------------------------------------------------------------
    # BoardReader — overridden
    # ------------------------------------------------------------------

    def cheap_probe(self) -> str:
        """Combined change-detection token: native store version + forge issue probe (anchor §4.4).

        Returns:
            ``"{store_version}:{forge_probe}"`` — changes when the native store is mutated
            (any move/reorder/import) OR when a GitHub issue is created or closed.
        """
        doc = self._store.load()
        store_version = doc.get("version", 0)
        forge_probe = self._forge.cheap_probe()
        return f"{store_version}:{forge_probe}"

    def snapshot(self) -> BoardSnapshot:
        """JOIN the forge issue set with the native placement store (anchor §4.5).

        Rules:
        - Issue in forge + in store → ``Ticket(column_key = store placement)``.
        - Issue in forge, NOT in store → register at entry column (``columns[0]``), emit there.
        - Issue closed on GitHub → reflected via forge's closed state (placement irrelevant).
        - Item in store but gone from GitHub → silently dropped (GC'd lazily).

        Returns:
            A ``BoardSnapshot`` structurally identical to the GitHub path so ``diff``/
            ``decide``/``tick`` consume it unchanged.
        """
        # Fetch the forge issue set (identity + open/closed + body). We call the forge's
        # own snapshot to reuse its pagination logic, then DISCARD the column_key (we only
        # want the identity fields). Under native, GitHub's Status is not authoritative.
        forge_snap = self._forge.snapshot()
        doc = self._store.load()
        placement: dict[str, str] = doc.get("placement", {})
        entry_col = self._columns[0] if self._columns else ""

        tickets: list[Ticket] = []
        for ft in forge_snap.tickets:
            col_key = placement.get(ft.item_id)
            if col_key is None:
                # First-sight: register at entry column, emit there.
                if entry_col:
                    self._store.place_card(ft.item_id, entry_col)
                    col_key = entry_col
                else:
                    col_key = ft.column_key  # fallback: use GitHub's value
            tickets.append(
                Ticket(
                    item_id=ft.item_id,
                    issue_number=ft.issue_number,
                    title=ft.title,
                    column_key=col_key,
                    body=ft.body,
                )
            )
        return BoardSnapshot(tickets=tuple(tickets), fetched_at=time.time())

    # ------------------------------------------------------------------
    # BoardReader — delegated to forge
    # ------------------------------------------------------------------

    def issue_state(self, number: int) -> bool:
        """Delegate to forge — open/closed is GitHub's (anchor §4.3).

        Args:
            number: The issue number whose open/closed state to probe.

        Returns:
            ``True`` when the issue is closed/merged; ``False`` otherwise.
        """
        return self._forge.issue_state(number)

    def issue_context(self, number: int) -> IssueContext:
        """Delegate to forge — body/comments are GitHub's (anchor §4.3).

        Args:
            number: The GitHub issue number whose rich context to fetch.

        Returns:
            An ``IssueContext`` from the forge client.
        """
        return self._forge.issue_context(number)

    # ------------------------------------------------------------------
    # BoardWriter — overridden
    # ------------------------------------------------------------------

    def move_card(self, item_id: str, column_key: str) -> None:
        """Write native placement (tail append) and optionally mirror to GitHub (anchor §5).

        Args:
            item_id: The ``ProjectV2Item`` node id to move.
            column_key: The destination column key.
        """
        self._store.place_card(item_id, column_key)
        if self._mirror is not None:
            try:
                display_name = self._option_name_for_key(column_key)
                self._mirror.move_card(item_id, display_name)
            except Exception:  # noqa: BLE001
                # Mirror failure is observability, not a board-authority failure (§5.2).
                logger.warning(
                    "anchor mirror: failed to mirror move %s → %s to GitHub",
                    item_id,
                    column_key,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # BoardWriter — delegated to forge
    # ------------------------------------------------------------------

    def comment(self, issue_number: int, body: str) -> None:
        """Delegate to forge (anchor §4.3).

        Args:
            issue_number: The GitHub issue number to comment on.
            body: The markdown comment body.
        """
        self._forge.comment(issue_number, body)

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        """Delegate to forge (anchor §4.3).

        Args:
            issue_number: The GitHub issue number whose comments to list.

        Returns:
            Comment refs from the forge client.
        """
        return self._forge.list_issue_comments(issue_number)

    def update_comment(self, comment_id: int, body: str) -> None:
        """Delegate to forge (anchor §4.3).

        Args:
            comment_id: The integer REST comment id to edit.
            body: The new markdown comment body.
        """
        self._forge.update_comment(comment_id, body)

    # ------------------------------------------------------------------
    # BoardOrdering — native only, NOT mirrored
    # ------------------------------------------------------------------

    def reorder_column(
        self,
        column_key: str,
        ordered_item_ids: list[str],
        *,
        if_version: int | None = None,
    ) -> int:
        """Delegate to the native store — order is NEVER mirrored (anchor §4.6).

        Args:
            column_key: The column whose order to set.
            ordered_item_ids: The new full ordered item id list.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new store version.
        """
        return self._store.reorder_column(
            column_key, ordered_item_ids, if_version=if_version
        )

    def place_card(
        self,
        item_id: str,
        column_key: str,
        index: int | None = None,
        *,
        if_version: int | None = None,
    ) -> int:
        """Place card at an explicit ``(column, index)`` — native only (anchor §4.6).

        Args:
            item_id: The item to place.
            column_key: The destination column key.
            index: Position within the column; ``None`` appends.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new store version.
        """
        return self._store.place_card(
            item_id, column_key, index, if_version=if_version
        )
```

- [ ] **Step 3: Commit**

```bash
git add src/kanbanmate/adapters/board/__init__.py src/kanbanmate/adapters/board/native.py
git commit -m "feat(anchor): NativeBoardBackend — snapshot JOIN, combined probe, move+mirror"
```

---

### Task 3: Backend tests (`tests/adapters/test_native_backend.py`)

**Files:**
- Modify: `tests/adapters/test_native_backend.py` (add tests after the existing import test)

**Interfaces:**
- Consumes: `NativeBoardBackend`, `FsBoardStateStore`, `seed_board`
- Uses real HYBRID column keys: `"Backlog"`, `"InProgress"`, `"Done"`

- [ ] **Step 1: Add tests for snapshot JOIN, cheap_probe, move+mirror**

Append to `tests/adapters/test_native_backend.py`:

```python
"""Tests for NativeBoardBackend — snapshot JOIN, combined probe, move+mirror (anchor §12.2-4)."""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock, call

import pytest

from kanbanmate.adapters.board.native import NativeBoardBackend
from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board
from kanbanmate.core.domain import BoardSnapshot, Ticket


def _forge_snapshot(*tickets: Ticket) -> MagicMock:
    """Return a fake forge client whose snapshot() returns the given tickets."""
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(
        tickets=tuple(tickets), fetched_at=0.0
    )
    return forge


def _ticket(item_id: str, col: str = "Backlog") -> Ticket:
    return Ticket(item_id=item_id, issue_number=1, title="T", column_key=col, body="")


COLUMNS = ["Backlog", "Brainstorming", "Spec", "Plan", "Planned",
           "ReadyToDev", "PrepareFeature", "InProgress", "PRCI",
           "Review", "Merge", "Done", "Cancel", "Blocked"]


def _make_backend(
    tmp_path: pathlib.Path,
    forge: MagicMock,
    mirror: MagicMock | None = None,
) -> NativeBoardBackend:
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    return NativeBoardBackend(
        forge=forge,
        store=store,
        columns=COLUMNS,
        option_name_for_key=lambda key: key,  # identity for tests
        mirror=mirror,
    )


# ---------------------------------------------------------------------------
# §12.2 — snapshot JOIN
# ---------------------------------------------------------------------------

def test_snapshot_uses_native_column_not_forge(tmp_path: pathlib.Path) -> None:
    """The snapshot uses the NATIVE column_key, not the forge's GitHub Status."""
    forge = _forge_snapshot(
        # forge says "InProgress" but native store has "Backlog"
        Ticket(item_id="item1", issue_number=1, title="T", column_key="InProgress", body="")
    )
    backend = _make_backend(tmp_path, forge)
    snap = backend.snapshot()
    assert len(snap.tickets) == 1
    assert snap.tickets[0].column_key == "Backlog", "native placement must win over forge Status"


def test_snapshot_new_issue_lands_in_entry_column(tmp_path: pathlib.Path) -> None:
    """A forge issue absent from the native store is registered at columns[0] = 'Backlog'."""
    forge = _forge_snapshot(
        _ticket("item1"),          # already in store
        _ticket("brand_new"),      # NOT in store
    )
    backend = _make_backend(tmp_path, forge)
    snap = backend.snapshot()
    by_id = {t.item_id: t for t in snap.tickets}
    assert "brand_new" in by_id
    assert by_id["brand_new"].column_key == "Backlog", "new issue must land at entry column"


def test_snapshot_store_only_item_dropped(tmp_path: pathlib.Path) -> None:
    """An item in the native store but absent from GitHub is dropped from the snapshot."""
    # Forge only returns one ticket; native store has "item1" but forge has "item2" only.
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},  # in store, NOT in forge
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    forge = _forge_snapshot(_ticket("item2", "Done"))  # only item2 in forge
    backend = NativeBoardBackend(
        forge=forge, store=store, columns=COLUMNS,
        option_name_for_key=lambda k: k,
    )
    snap = backend.snapshot()
    item_ids = {t.item_id for t in snap.tickets}
    assert "item1" not in item_ids, "store-only item must be dropped (GC'd lazily)"
    assert "item2" in item_ids


# ---------------------------------------------------------------------------
# §12.3 — combined cheap_probe
# ---------------------------------------------------------------------------

def test_cheap_probe_changes_on_native_move(tmp_path: pathlib.Path) -> None:
    """A native move (store version bump) changes the probe; forge probe unchanged."""
    forge = MagicMock()
    forge.cheap_probe.return_value = "frozen-forge-token"
    forge.snapshot.return_value = BoardSnapshot(tickets=(), fetched_at=0.0)

    store = FsBoardStateStore(tmp_path)
    seed_board(
        store, columns=COLUMNS,
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    backend = NativeBoardBackend(
        forge=forge, store=store, columns=COLUMNS,
        option_name_for_key=lambda k: k,
    )
    probe_before = backend.cheap_probe()
    store.place_card("item1", "InProgress")  # native move
    probe_after = backend.cheap_probe()
    assert probe_before != probe_after, "native move must change the combined probe"
    assert "frozen-forge-token" in probe_after


def test_cheap_probe_stable_when_nothing_changes(tmp_path: pathlib.Path) -> None:
    """When neither store nor forge changes, the combined probe is stable."""
    forge = MagicMock()
    forge.cheap_probe.return_value = "stable"
    forge.snapshot.return_value = BoardSnapshot(tickets=(), fetched_at=0.0)

    store = FsBoardStateStore(tmp_path)
    seed_board(store, columns=COLUMNS, placement={}, order={c: [] for c in COLUMNS})
    backend = NativeBoardBackend(
        forge=forge, store=store, columns=COLUMNS,
        option_name_for_key=lambda k: k,
    )
    assert backend.cheap_probe() == backend.cheap_probe()


# ---------------------------------------------------------------------------
# §12.4 — move_card + mirror
# ---------------------------------------------------------------------------

def test_move_card_writes_native_and_mirrors(tmp_path: pathlib.Path) -> None:
    """move_card writes native placement AND calls forge.move_card with the option NAME."""
    mirror = MagicMock()
    forge = _forge_snapshot(_ticket("item1"))
    backend = _make_backend(tmp_path, forge, mirror=mirror)

    backend.move_card("item1", "InProgress")

    doc = backend._store.load()
    assert doc["placement"]["item1"] == "InProgress"
    # Mirror must receive the display name (identity for this test)
    mirror.move_card.assert_called_once_with("item1", "InProgress")


def test_move_card_mirror_error_swallowed_native_lands(tmp_path: pathlib.Path) -> None:
    """A mirror write error is swallowed; native placement is already correct (§5.2)."""
    mirror = MagicMock()
    mirror.move_card.side_effect = RuntimeError("GitHub down")

    forge = _forge_snapshot(_ticket("item1"))
    backend = _make_backend(tmp_path, forge, mirror=mirror)

    backend.move_card("item1", "Done")  # must NOT raise

    doc = backend._store.load()
    assert doc["placement"]["item1"] == "Done", "native must be updated despite mirror failure"


def test_reorder_does_not_call_mirror(tmp_path: pathlib.Path) -> None:
    """reorder_column is native-only; the mirror must never be called (anchor §4.6)."""
    mirror = MagicMock()
    forge = MagicMock()
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=["Backlog", "InProgress"],
        placement={"a": "Backlog", "b": "Backlog"},
        order={"Backlog": ["a", "b"], "InProgress": []},
    )
    backend = NativeBoardBackend(
        forge=forge, store=store, columns=["Backlog", "InProgress"],
        option_name_for_key=lambda k: k,
        mirror=mirror,
    )
    backend.reorder_column("Backlog", ["b", "a"])
    mirror.move_card.assert_not_called()
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/adapters/test_native_backend.py -v
```

Expected: all PASS.

- [ ] **Step 3: Run make check**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && make check
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/adapters/test_native_backend.py
git commit -m "test(anchor): NativeBoardBackend — snapshot JOIN, combined probe, move+mirror"
```
