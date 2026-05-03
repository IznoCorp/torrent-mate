# Phase 2 — CLI decomposition

**Goal:** Split `personalscraper/cli.py` (1648 LOC) into focused command modules under `personalscraper/commands/`. `cli.py` retains only the Typer `app` instance, global option wiring, exception-handling decorator, and bootstrap glue (target ≤ 400 LOC).

**Risk:** Medium — touches the entry point used by every CLI invocation. Mitigated by behaviour-preserving extraction (no logic edits in move commits) and the existing CLI tests (`tests/test_cli.py`, `tests/commands/`, plus command-specific domain tests).

**Files affected (estimate):**

- Create: `personalscraper/commands/pipeline.py`, `personalscraper/commands/library.py`, `personalscraper/commands/config.py` (extending or replacing `commands/init_config.py`), `personalscraper/commands/info.py`, `personalscraper/commands/diagnose.py`, `personalscraper/commands/__init__.py` (already exists, may need exports)
- Modify: `personalscraper/cli.py` (shrink), command tests only if imports reference moved helpers (`tests/test_cli.py`, `tests/commands/`, domain CLI tests). Import-path updates only — no test logic changes.

## Pre-flight inventory

```bash
# List every Typer command currently in cli.py
grep -nE '@app\.command' personalscraper/cli.py
# Map each command body line range
grep -nE '^def [a-z_]+\(' personalscraper/cli.py
```

Expected commands (verified from current code):

**Pipeline group** (→ `commands/pipeline.py`):

- `ingest`, `sort`, `scrape`, `verify`, `enforce`, `dispatch`, `process`, `run` (the orchestrator)

**Library group** (→ `commands/library.py`):

- `library_scan` (legacy), `library_status`, `library_index`, `library_verify`, `library_search`, `library_repair`, `library_reconcile`, `library_show`, `library_clean`, `library_validate`, `library_analyze`, `library_recommend`, `library_rescrape`, `library_report`

**Config group** (→ `commands/config.py`):

- `init_config` (already in `commands/init_config.py`), `config_migrate_category`, any `validate-config` / `show-config` if present

**Info group** (→ `commands/info.py`):

- `version`, `info`, `paths`, `disks` (audit which exist)

**Diagnose group** (→ `commands/diagnose.py`):

- `doctor`-style commands if any (audit before extraction)

## Sub-phases

### 2.1 — Extract `commands/pipeline.py`

**Files:**

- Create: `personalscraper/commands/pipeline.py`
- Modify: `personalscraper/cli.py` (delete extracted bodies, import + re-register)

- [ ] **Step 1: Create new module with extracted command bodies**

The pattern for each command is to register against the **same** Typer `app` instance imported from `cli.py`:

```python
# personalscraper/commands/pipeline.py
"""Pipeline-related Typer commands.

Extracted from personalscraper/cli.py during arch-cleanup phase 2.
Behaviour-preserving — no logic changes in this commit.
"""

from __future__ import annotations

import typer

from personalscraper.cli_app import app   # see step 2 below
from personalscraper.cli_helpers import handle_cli_errors  # extracted helper
from personalscraper.cli_state import state  # extracted global CLI state


@app.command()
@handle_cli_errors
def ingest(
    # ... exact signature from cli.py:200-220 ...
) -> None:
    """[Original docstring verbatim]"""
    # ... exact body from cli.py:200-220 ...
```

Repeat for: `sort`, `scrape`, `verify`, `enforce`, `dispatch`, `process`, `run`.

- [ ] **Step 2: Extract Typer `app` instance to `personalscraper/cli_app.py`**

To avoid circular imports between `cli.py` (which currently _defines_ `app`) and `commands/*.py` (which need to _register against_ `app`), move the `app = typer.Typer(...)` line to a tiny module:

```python
# personalscraper/cli_app.py
"""The single Typer app instance shared by all command modules.

Extracted during arch-cleanup phase 2 to break the cli.py → commands/*
circular dependency.
"""

import typer

app = typer.Typer(help="PersonalScraper — Media pipeline automation.", invoke_without_command=True)
```

`cli.py` and every `commands/*.py` import `app` from here. The legacy `app` symbol re-exported from `cli.py` is kept (`from personalscraper.cli_app import app`) for any external imports.

- [ ] **Step 3: Extract shared helpers/state to `personalscraper/cli_helpers.py` and `personalscraper/cli_state.py`**

Move `_format_validation`, `handle_cli_errors`, `_bootstrap_staging`, `_resolve_category` from `cli.py` to a new `cli_helpers.py`.

Move the `_State` TypedDict and the `state` singleton to `cli_state.py` so `cli.py` and `commands/*` can share console/verbose/quiet without circular imports. `cli.py` re-exports `state` if existing tests import it from `personalscraper.cli`.

- [ ] **Step 4: Delete extracted command bodies from `cli.py`**

`cli.py` now imports the command modules to trigger their `@app.command()` registration:

```python
# personalscraper/cli.py — at the bottom, after main()
import personalscraper.commands.pipeline  # noqa: F401  (registers commands)
```

- [ ] **Step 5: Run the test suite**

```bash
pytest tests/test_cli.py tests/commands/ -v
make lint
```

Expected: all CLI tests still pass; the command surface visible to `personalscraper --help` is unchanged.

- [ ] **Step 6: Verify command list unchanged**

```bash
personalscraper --help > /tmp/personalscraper-help.after
# Compare against a pre-phase snapshot captured before edits, if available:
# diff -u /tmp/personalscraper-help.before /tmp/personalscraper-help.after
```

Expected: empty diff when a pre-phase snapshot was captured. Do not use `git stash` for this check; the feature docs and roadmap may already be uncommitted.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/cli.py personalscraper/cli_app.py personalscraper/cli_helpers.py personalscraper/commands/pipeline.py
git commit -m "refactor(arch-cleanup): extract pipeline commands into commands/pipeline.py"
```

### 2.2 — Extract `commands/library.py`

Same pattern as 2.1. Move all 14 `library_*` command bodies to `personalscraper/commands/library.py`.

- [ ] **Step 1: Create `commands/library.py`**, import `app` from `cli_app`, register each library command identically to original.
- [ ] **Step 2: Delete extracted bodies from `cli.py`**, add `import personalscraper.commands.library` trigger.
- [ ] **Step 3: Run** `pytest tests/test_cli.py tests/library/ tests/indexer/test_cli.py -v` (or a narrower matching subset) — all green.
- [ ] **Step 4: Verify** `personalscraper library-scan --help`, `personalscraper library-index --help`, etc., produce unchanged output.
- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(arch-cleanup): extract library commands into commands/library.py"
```

### 2.3 — Extract `commands/config.py`

`commands/init_config.py` already exists. Either:

- (a) Rename it to `commands/config.py` and add `config_migrate_category` and any other config commands.
- (b) Keep `init_config.py` and add a separate `config.py` for non-init operations.

Decision: **(a)** — single module per command group is cleaner. Use `git mv personalscraper/commands/init_config.py personalscraper/commands/config.py` then update imports.

- [ ] **Step 1: `git mv personalscraper/commands/init_config.py personalscraper/commands/config.py`**
- [ ] **Step 2: `grep -rn "commands.init_config\|commands\.init_config" personalscraper/ tests/`** and rewrite imports to `commands.config`.
- [ ] **Step 3: Move `config_migrate_category` body from `cli.py` to `commands/config.py`.**
- [ ] **Step 4: Add `import personalscraper.commands.config` registration line to `cli.py`.**
- [ ] **Step 5: Run** `pytest tests/test_cli.py tests/commands/ tests/conf/ -v`.
- [ ] **Step 6: Commit**

```bash
git commit -m "refactor(arch-cleanup): unify config commands into commands/config.py"
```

### 2.4 — Extract `commands/info.py` and `commands/diagnose.py`

- [ ] **Step 1: Audit which `info`/`diagnose`-flavoured commands exist** in current `cli.py`. If none, skip this sub-phase (mark complete with empty commit message reasoning).
- [ ] **Step 2: For each found command, extract to the appropriate module** following the 2.1 pattern.
- [ ] **Step 3: Add registration imports to `cli.py`.**
- [ ] **Step 4: Test + commit:**

```bash
git commit -m "refactor(arch-cleanup): extract info/diagnose commands"
```

### 2.5 — Shrink `cli.py` to wiring only

After 2.1-2.4, `cli.py` should contain:

- License header / module docstring
- Imports
- (Empty if `app` lives in `cli_app.py`) — re-export `app`
- `main()` Typer entry point (the `def main(...)` callback)
- Bottom: `import` lines that trigger command registration
- (Optional) `if __name__ == "__main__": app()`

- [ ] **Step 1: Verify `cli.py` LOC**

```bash
wc -l personalscraper/cli.py
```

Expected: ≤ 400.

- [ ] **Step 2: Run module-size script**

```bash
python3 scripts/check-module-size.py
```

Expected: `cli.py` no longer in REPORT/WARN list.

- [ ] **Step 3: Final test pass**

```bash
make check
```

Expected: all green.

- [ ] **Step 4: Phase milestone commit**

```bash
git commit --allow-empty -m "chore(arch-cleanup): phase 2 gate — CLI decomposition complete"
```

## Quality gate

```bash
make check
pytest tests/test_cli.py tests/commands/ -v
personalscraper --help              # surface unchanged
personalscraper library-scan --help # legacy command still visible
```

## Success criteria

- `cli.py` ≤ 400 LOC
- `commands/pipeline.py`, `commands/library.py`, `commands/config.py` exist; each ≤ 800 LOC
- `personalscraper --help` output identical to pre-phase 2 (diff empty)
- All CLI tests pass without modification (other than import-path-only adjustments)
- `python3 scripts/check-module-size.py`: `cli.py` no longer flagged

## Rollback plan

Each sub-phase is one commit. To roll back:

- 2.1 only: `git revert <2.1-sha>` — revert restores `cli.py` to monolithic, no other phase impacted.
- Whole phase: `git revert <2.5-sha>..<2.1-sha>` (in reverse).

## Estimated effort

6-8 commits, ~6 hours (most time in 2.1 — the first extraction sets the import pattern that 2.2-2.4 follow mechanically).
