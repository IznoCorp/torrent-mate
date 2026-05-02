# Phase 3 — Indexer CLI decomposition

**Goal:** Split `personalscraper/indexer/cli.py` (1389 LOC) into focused modules under `personalscraper/indexer/commands/`. The CLI shell (`cli.py`) keeps only the Typer sub-app instance + wiring.

**Risk:** Medium. Touches every `personalscraper library-*` command path that delegates to indexer/cli.py command functions, but the contract surface is small (each command function is a `*_command()` callable with a stable signature).

**Files affected (estimate):**

- Create: `personalscraper/indexer/commands/__init__.py`, `personalscraper/indexer/commands/{scan,query,repair,diagnose}.py`
- Modify: `personalscraper/indexer/cli.py` (shrink), `personalscraper/commands/library.py` (import paths if any), `tests/indexer/test_cli*.py` (import path updates)

## Pre-flight inventory

```bash
grep -nE '^def [a-z_]+_command\(' personalscraper/indexer/cli.py
```

Expected (verified):

- `library_status_command` → query
- `library_index_command` → scan
- `library_verify_command` → query (or diagnose)
- `library_search_command` → query
- `library_reconcile_command` → scan (or repair)
- `library_repair_command` → repair
- `library_show_command` → query
- `config_migrate_category_command` → diagnose (or moved to phase 2's `commands/config.py`)

Also extract:

- `_bootstrap_disks_from_config` → `personalscraper/indexer/commands/_bootstrap.py` (shared helper)

## Sub-phases

### 3.1 — Extract bootstrap helper

**Files:**

- Create: `personalscraper/indexer/commands/__init__.py` (empty)
- Create: `personalscraper/indexer/commands/_bootstrap.py`
- Modify: `personalscraper/indexer/cli.py` (delete `_bootstrap_disks_from_config`, import from new location)

- [ ] **Step 1: Create `_bootstrap.py`**

```python
# personalscraper/indexer/commands/_bootstrap.py
"""Shared indexer-CLI bootstrap helpers.

Extracted from indexer/cli.py during arch-cleanup phase 3.
"""

from __future__ import annotations

# ... exact body of _bootstrap_disks_from_config from indexer/cli.py:44-110 ...
```

- [ ] **Step 2: Delete from `indexer/cli.py`, replace with `from personalscraper.indexer.commands._bootstrap import _bootstrap_disks_from_config`.**

- [ ] **Step 3: Test**

```bash
pytest tests/indexer/ -v
```

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor(arch-cleanup): extract indexer CLI bootstrap helper"
```

### 3.2 — Extract `commands/scan.py`

**Files:**

- Create: `personalscraper/indexer/commands/scan.py` containing `library_index_command`, `library_reconcile_command` (and any scan-related sub-helpers used only by these).

- [ ] **Step 1: Move command functions verbatim.** Imports follow.
- [ ] **Step 2: Update `personalscraper/indexer/cli.py`** to `from personalscraper.indexer.commands.scan import library_index_command, library_reconcile_command`.
- [ ] **Step 3: Update any `personalscraper/cli.py` (or `commands/library.py` after phase 2) imports** to point at the new path.
- [ ] **Step 4: Test:** `pytest tests/indexer/test_cli.py -v -k "index or reconcile"` (or the closest matching subset discovered by `pytest --collect-only`). The current repository uses `tests/indexer/test_cli.py`, not split `test_cli_scan.py` / `test_cli_index.py` files.
- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(arch-cleanup): extract indexer scan commands"
```

### 3.3 — Extract `commands/query.py`

`library_status_command`, `library_search_command`, `library_show_command`, `library_verify_command`.

- [ ] **Step 1-5**: Same pattern as 3.2.

```bash
git commit -m "refactor(arch-cleanup): extract indexer query commands"
```

### 3.4 — Extract `commands/repair.py`

`library_repair_command` and any verify-integrity / rebuild-merkle helpers if present.

- [ ] **Step 1-5**: Same pattern.

```bash
git commit -m "refactor(arch-cleanup): extract indexer repair commands"
```

### 3.5 — Extract `commands/diagnose.py`

Any remaining commands: dump-config, show-migrations, `config_migrate_category_command` if not already moved by phase 2 to `personalscraper/commands/config.py`.

- [ ] **Step 1: Decide placement of `config_migrate_category_command`**. If phase 2 already moved it to `personalscraper/commands/config.py`, delete it from `indexer/cli.py` and skip here. Otherwise move to `indexer/commands/diagnose.py`.
- [ ] **Step 2-5**: Same pattern.

```bash
git commit -m "refactor(arch-cleanup): extract indexer diagnose commands"
```

### 3.6 — Shrink `indexer/cli.py` to wiring

After 3.1-3.5, `indexer/cli.py` should contain only:

- Module docstring
- Imports
- The Typer sub-app instance (if any)
- Re-exports for backward compatibility (`from personalscraper.indexer.commands.scan import library_index_command  # re-export`)

- [ ] **Step 1: Verify LOC**

```bash
wc -l personalscraper/indexer/cli.py
```

Expected: ≤ 400.

- [ ] **Step 2: Verify command signatures unchanged**

```bash
python3 -c "from personalscraper.indexer.cli import library_index_command, library_search_command; print('ok')"
```

Expected: `ok`. Re-exports keep the public API stable.

- [ ] **Step 3: Final test pass**

```bash
make check
pytest tests/indexer/ -v
```

- [ ] **Step 4: Phase milestone commit**

```bash
git commit --allow-empty -m "chore(arch-cleanup): phase 3 gate — indexer CLI decomposition complete"
```

## Quality gate

```bash
make check
pytest tests/indexer/ -v
personalscraper library-index --help    # output unchanged
personalscraper library-search --help   # output unchanged
```

## Success criteria

- `indexer/cli.py` ≤ 400 LOC
- `indexer/commands/scan.py`, `query.py`, `repair.py`, `diagnose.py` exist; each ≤ 800 LOC
- All `library_*_command` functions importable from both `indexer.cli` (re-export) and `indexer.commands.<group>` (canonical)
- All indexer tests pass
- `python3 scripts/check-module-size.py`: `indexer/cli.py` no longer flagged

## Rollback plan

Each sub-phase is one commit, independently revertable. The `from personalscraper.indexer.commands.<group> import <fn>` re-exports in `indexer/cli.py` keep the import contract stable, so reverting any single sub-phase only requires a single `git revert`.

## Estimated effort

4-6 commits, ~4 hours.
