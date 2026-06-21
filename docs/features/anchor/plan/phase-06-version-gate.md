# Phase 06 — Version bump + final gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

## Gate

All prior phases must be complete and `make check` green:
- `src/kanbanmate/http/board_routes.py` exists.
- `tests/http/test_board_routes.py` passes.
- All phase 01–05 tests pass.

## Goal

Bump the version to 0.11.0, mark the ROADMAP.md row for helm PR 3 as implemented, verify the layering guard covers the new modules, and run the final `make check` gate.

## Files

- **Modify:** `src/kanbanmate/__init__.py` — bump `__version__` from `"0.10.0"` to `"0.11.0"`
- **Modify:** `ROADMAP.md` — mark the anchor / helm PR 3 row as implemented
- **Verify:** `tests/test_layering.py` — confirm existing guard covers new modules (no change needed unless the guard is path-based and must enumerate new modules)

## Key design facts (grounded)

- `__version__` is at `src/kanbanmate/__init__.py:11` per the design.
- `tests/test_layering.py` already exists in the repo — check that it covers `adapters/board/` and `ports/store_board.py` (if it enumerates paths, add them; if it sweeps all modules, no change needed).
- Do NOT edit `IMPLEMENTATION.md` (managed by the create-branch stage).
- `ROADMAP.md` edit: find the `anchor` / `[helm-pr3]` row and mark it implemented (typically change `[ ]` to `[x]` or add a shipped date — follow the existing row format in the file).

---

### Task 1: Version bump

**Files:**
- Modify: `src/kanbanmate/__init__.py`

- [ ] **Step 1: Confirm current version**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -c "import kanbanmate; print(kanbanmate.__version__)"
```

Expected: `0.10.0`.

- [ ] **Step 2: Update `__init__.py`**

In `src/kanbanmate/__init__.py`, change:

```python
__version__ = "0.10.0"
```

to:

```python
__version__ = "0.11.0"
```

- [ ] **Step 3: Verify**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -c "import kanbanmate; print(kanbanmate.__version__)"
```

Expected: `0.11.0`.

- [ ] **Step 4: Commit**

```bash
git add src/kanbanmate/__init__.py
git commit -m "chore(anchor): bump version 0.10.0 → 0.11.0"
```

---

### Task 2: ROADMAP.md — mark helm PR 3 implemented

**Files:**
- Modify: `ROADMAP.md`

- [ ] **Step 1: Find the anchor / helm PR 3 row**

```bash
grep -n "anchor\|helm.*pr3\|helm.*PR3\|helm-pr3\|\[helm-pr3\]" /Users/izno/dev/worktrees/ticket-43/ROADMAP.md
```

- [ ] **Step 2: Update the row**

Open `ROADMAP.md` and update the anchor row to mark it implemented. Follow the EXACT format of other completed rows in the file (e.g., add a shipped date, change `[ ]` to `[x]`, etc.). Example — if the row looks like:

```
| #43 | anchor (helm PR 3) | Board repatriation | [ ] | kanban/ticket-43 |
```

Change it to match the completed rows' format (look at #5 / #33 rows as a reference).

- [ ] **Step 3: Commit**

```bash
git add ROADMAP.md
git commit -m "docs(anchor): mark helm PR3 (anchor) implemented in ROADMAP.md"
```

---

### Task 3: Layering guard verification

**Files:**
- Verify (possibly modify): `tests/test_layering.py`

- [ ] **Step 1: Read the layering guard**

```bash
cat /Users/izno/dev/worktrees/ticket-43/tests/test_layering.py
```

- [ ] **Step 2: Determine if new modules need to be added**

If `test_layering.py` sweeps all importable modules dynamically (e.g., discovers `kanbanmate.**`), no change is needed.

If it enumerates specific paths, verify that these are covered:
- `kanbanmate.ports.store_board` — must not import from `core`, `adapters`, `app`, `cli`, or `daemon`.
- `kanbanmate.adapters.board.native` — must not import from `app`, `cli`, or `daemon`.
- `kanbanmate.adapters.store.fs_board` — must not import from `app`, `cli`, or `daemon`.
- `kanbanmate.app.board_import` — must not import from `cli` or `daemon`.
- `kanbanmate.http.board_routes` — must not import from `daemon` at module scope.

If the guard enumerates paths and misses these, add them.

- [ ] **Step 3: Run the layering guard test**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -m pytest tests/test_layering.py -v
```

Expected: all PASS. If any fail, fix the import that violates the layering rule (typically a missing lazy import or an accidental top-level import).

- [ ] **Step 4: Commit (only if changes were made)**

```bash
git add tests/test_layering.py
git commit -m "test(anchor): extend layering guard to cover new anchor modules"
```

---

### Task 4: Full final gate

- [ ] **Step 1: Full test suite**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && make test
```

Expected: all PASS. Check the summary line — any `ERROR` means a collection crash; fix imports first.

- [ ] **Step 2: Lint + type check**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && make lint
```

Expected: zero errors.

- [ ] **Step 3: Module-size guard**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && make check
```

Expected: green (all lint + test + module-size guards pass).

- [ ] **Step 4: Smoke test**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && python -c "
import kanbanmate
from kanbanmate.ports.store_board import BoardStateStore, BoardOrdering
from kanbanmate.adapters.store.fs_board import FsBoardStateStore
from kanbanmate.adapters.board.native import NativeBoardBackend
from kanbanmate.app.board_import import import_board
from kanbanmate.cli.board import board_app
print('version:', kanbanmate.__version__)
print('smoke: OK')
"
```

Expected:
```
version: 0.11.0
smoke: OK
```

- [ ] **Step 5: Residual-import check (no stale references)**

```bash
cd /Users/izno/dev/worktrees/ticket-43 && rg --type py "from kanbanmate.adapters.board" src/ tests/
```

Verify that every import resolves to the actual `adapters/board/native.py` (no phantom module refs).

- [ ] **Step 6: Commit if any last-minute fixes**

If any minor fix was needed (import typo, missing `__all__`, etc.), commit it:

```bash
git add <changed files>
git commit -m "fix(anchor): <describe the fix>"
```

---

## Phase 06 is done when

- `python -c "import kanbanmate; print(kanbanmate.__version__)"` prints `0.11.0`.
- `make check` exits 0 — all lint + all tests + module-size guards green.
- `tests/test_layering.py` passes covering the new modules.
- ROADMAP.md has the anchor row marked implemented.
- No `IMPLEMENTATION.md` edit was made (it is managed externally).
