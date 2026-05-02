# Phase 4 — Indexer scanner modes split

**Goal:** Split `personalscraper/indexer/scanner/_modes.py` (1900 LOC, the largest single module in the codebase) into a `_modes/` package with one file per scan mode.

**Risk:** High. This module is the execution engine of every `library-index` invocation. Any logic drift surfaces as data corruption in the SQLite index. Mitigated by: (1) inventory-first sub-phase, (2) git-mv-equivalent extraction with zero logic edits per move commit, (3) integration tests under `tests/indexer/` covering each mode.

**Files affected (estimate):**

- Create: `personalscraper/indexer/scanner/_modes/__init__.py`, `_modes/full.py`, `_modes/incremental.py`, `_modes/repair.py`, `_modes/freeze.py` (and any 5th mode discovered in inventory)
- Delete: `personalscraper/indexer/scanner/_modes.py` (replaced by the package)
- Modify: any consumer importing from `_modes.py` (`indexer/scanner/__init__.py`, scan workers)

## Pre-flight inventory

This is the most important step of the phase. Without a complete mode inventory, the split risks silently dropping or merging modes.

```bash
# List public symbols (functions, classes, constants) in _modes.py
grep -nE '^(def |class |[A-Z_][A-Z0-9_]+\s*=)' personalscraper/indexer/scanner/_modes.py | head -80

# List dispatch entry points (functions called from outside _modes.py)
grep -rn "from personalscraper.indexer.scanner._modes" personalscraper/ tests/
grep -rn "from personalscraper.indexer.scanner import _modes" personalscraper/ tests/

# Identify mode boundaries (per-mode function clusters)
grep -nE '^def (run_|scan_|_)?(full|incremental|repair|freeze|spotlight|drift|reconcile)' personalscraper/indexer/scanner/_modes.py
```

Produce a written inventory in `docs/superpowers/roadmap/arch-cleanup/plan/phase-04-inventory.md` listing:

- Each public function and its mode classification
- Shared helpers (used by ≥ 2 modes)
- Module-level constants (move to `_modes/__init__.py` or a `_modes/_shared.py`)
- External consumers (every importer of `_modes`)

This is sub-phase 4.0 — produce the inventory file before any code change.

## Sub-phases

### 4.0 — Mode inventory

**Files:**

- Create: `docs/superpowers/roadmap/arch-cleanup/plan/phase-04-inventory.md`

- [ ] **Step 1: Run the inventory greps above**, copy output into the file.
- [ ] **Step 2: For each function in the file, classify**:
  - `full` (full rescan logic)
  - `incremental` (drift / partial rescan)
  - `repair` (repair-queue-driven)
  - `freeze` (bulk freeze)
  - `spotlight` (macOS Spotlight integration — if present)
  - `_shared` (helper used by 2+ modes)
- [ ] **Step 3: Commit the inventory**

```bash
git add docs/superpowers/roadmap/arch-cleanup/plan/phase-04-inventory.md
git commit -m "docs(arch-cleanup): scanner mode inventory before split"
```

### 4.1 — Create `_modes/` package skeleton + extract shared helpers

**Files:**

- Create: `personalscraper/indexer/scanner/_modes_pkg/__init__.py` (temporary name to avoid collision with the existing file)
- Create: `personalscraper/indexer/scanner/_modes_pkg/_shared.py`

> **Constraint**: Python doesn't let `_modes.py` and `_modes/` coexist. We stage in `_modes_pkg/` first, switch consumers, then rename the package once `_modes.py` is empty/deleted.

- [ ] **Step 1: Create `_modes_pkg/__init__.py`** with re-exports:

```python
# personalscraper/indexer/scanner/_modes_pkg/__init__.py
"""Indexer scanner modes — package layout.

Replaces the monolithic _modes.py. Public API is preserved via re-exports.
"""

from __future__ import annotations

from ._shared import *  # noqa: F401, F403  (re-exported helpers)
from .full import *  # noqa: F401, F403
from .incremental import *  # noqa: F401, F403
from .repair import *  # noqa: F401, F403
from .freeze import *  # noqa: F401, F403

# Each per-mode module declares __all__ to control re-exports.
```

- [ ] **Step 2: Move shared helpers to `_shared.py`** based on the 4.0 inventory.
- [ ] **Step 3: Delete the moved helpers from `_modes.py`.** Replace with `from personalscraper.indexer.scanner._modes_pkg._shared import <names>` to keep `_modes.py` consumers working.
- [ ] **Step 4: Test**

```bash
pytest tests/indexer/ -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(arch-cleanup): scaffold _modes package + extract shared helpers"
```

### 4.2 — Extract full-scan mode

**Files:**

- Create: `personalscraper/indexer/scanner/_modes_pkg/full.py`
- Modify: `personalscraper/indexer/scanner/_modes.py` (delete moved code, add re-exports)

- [ ] **Step 1: Move full-scan functions** verbatim from `_modes.py` to `_modes_pkg/full.py`.
- [ ] **Step 2: Declare `__all__`** in `full.py` listing the public symbols.
- [ ] **Step 3: In `_modes.py`, replace deleted bodies with re-exports**:

```python
# personalscraper/indexer/scanner/_modes.py (transitional)
from personalscraper.indexer.scanner._modes_pkg.full import (  # noqa: F401
    scan_full,
    # ...
)
```

- [ ] **Step 4: Run full-scan integration test**

```bash
pytest tests/indexer/scanner/test_full_scan.py -v
# or, if that path is different, find it:
find tests/indexer -name 'test_*full*.py'
```

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(arch-cleanup): extract full scan mode into _modes_pkg/full.py"
```

### 4.3 — Extract incremental-scan mode

Same pattern as 4.2 for incremental / drift logic.

```bash
git commit -m "refactor(arch-cleanup): extract incremental scan mode"
```

### 4.4 — Extract repair-scan mode

Same pattern for repair-queue-driven scans.

```bash
git commit -m "refactor(arch-cleanup): extract repair scan mode"
```

### 4.5 — Extract freeze mode

Same pattern for bulk freeze.

```bash
git commit -m "refactor(arch-cleanup): extract freeze mode"
```

### 4.6 — Extract any remaining modes

If 4.0 inventory found a 5th mode (e.g., spotlight, drift-only), extract it now.

```bash
git commit -m "refactor(arch-cleanup): extract <mode> mode"
```

### 4.7 — Rename `_modes_pkg/` → `_modes/`

After 4.2-4.6 complete and `_modes.py` contains only re-exports:

- [ ] **Step 1: Verify `_modes.py` is now ≤ 50 LOC of re-exports** (no logic).
- [ ] **Step 2: Delete `_modes.py`**.
- [ ] **Step 3: Rename the package directory**

```bash
git mv personalscraper/indexer/scanner/_modes_pkg personalscraper/indexer/scanner/_modes
```

- [ ] **Step 4: Update consumers** that imported from `_modes_pkg`:

```bash
grep -rn "_modes_pkg" personalscraper/ tests/
# rewrite each match to _modes
```

- [ ] **Step 5: Verify imports**

```bash
python3 -c "from personalscraper.indexer.scanner._modes import scan_full; print('ok')"
```

- [ ] **Step 6: Full indexer test pass**

```bash
pytest tests/indexer/ -v
```

- [ ] **Step 7: Commit**

```bash
git commit -m "refactor(arch-cleanup): rename _modes_pkg to _modes (replaces monolithic file)"
```

### 4.8 — Phase gate

- [ ] **Step 1: Verify per-file LOC**

```bash
wc -l personalscraper/indexer/scanner/_modes/*.py
```

Expected: each ≤ 700 LOC, none ≥ 1000.

- [ ] **Step 2: Module-size script**

```bash
python3 scripts/check-module-size.py
```

Expected: no `_modes/*.py` flagged.

- [ ] **Step 3: Phase milestone commit**

```bash
git commit --allow-empty -m "chore(arch-cleanup): phase 4 gate — scanner modes split complete"
```

## Quality gate

```bash
make check
pytest tests/indexer/ -v
# and for each mode integration:
pytest tests/indexer/scanner/ -v --maxfail=1
```

## Success criteria

- `personalscraper/indexer/scanner/_modes.py` no longer exists (replaced by `_modes/` package)
- Each `_modes/*.py` ≤ 700 LOC
- All indexer tests green; coverage delta ≥ 0
- Public import surface unchanged: `from personalscraper.indexer.scanner._modes import <X>` works for every X that previously existed
- A `personalscraper library-index` end-to-end run reproduces a known scan output on a test fixture

## Rollback plan

Each sub-phase is one commit. Critical guardrail: the rename in 4.7 is the riskiest single step — if it goes wrong, immediate revert is safe because the staged `_modes_pkg` and the original `_modes.py` re-exports kept everything dual-reachable until that point.

```bash
# If 4.7 broke something:
git revert <4.7-sha>
# _modes_pkg/ is restored; _modes.py is back as the re-export shell; consumers work.
```

## Estimated effort

5-7 commits (plus the 4.0 inventory commit = 6-8 total), ~8 hours. The inventory step (4.0) takes ~1 hour and saves the rest of the phase from drift.
