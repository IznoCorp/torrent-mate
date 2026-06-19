# Phase 1 — Layering guard + behaviour-preserving relocations

**Goal**: register the new `mcp` layer in the import guard and relocate the two helpers `mcp/tools.py`
needs out of `bin/` (forbidden for `mcp/`) into permitted layers — an **import-only,
behaviour-preserving** change so the bins stay byte-for-byte equivalent at runtime (DESIGN §3.1, §11).

This phase introduces **no `mcp/` code yet**; it lands the prerequisites so Phase 2's tool bodies have
real symbols to import.

## Why first

`mcp/tools.py` (Phase 2) imports `resolve_target_column` from `core.columns` and `fetch_base` /
`ff_dev_clone` from `adapters.workspace.base_sync`. Those must exist in permitted layers, and the
layering guard must accept `mcp` → `app`/`adapters`/`core`/`ports`/`cli`, before any `mcp/` file can
land green.

## Sub-phase 1a — Layering guard: add the `mcp` entry

**File**: `tests/test_layering.py`.

The forbidden-prefix map `FORBIDDEN` (`tests/test_layering.py:29-49`) currently ends at:

```python
"app": ["cli", "daemon"],
"http": ["daemon", "bin"],
```

Add **one** entry, modelled exactly on `http` (DESIGN §3.1):

```python
# mcp is the stdio board-server entrypoint (conduit / roadmap mcp). Like cli/daemon/http it sits
# at the TOP of the hierarchy and may import app/adapters/core/ports/cli (the http set — http
# already imports cli.init), but must NOT reach the daemon/bin sibling entrypoints.
"mcp": ["daemon", "bin"],
```

The guard parametrises over `sorted(FORBIDDEN)` (`tests/test_layering.py:131`,
`@pytest.mark.parametrize("layer", sorted(FORBIDDEN))`) and walks the **full AST**
(`ast.walk(tree)`, `_imported_modules`, `tests/test_layering.py:69-101`), so the new layer is
auto-exercised once any `src/kanbanmate/mcp/*.py` exists. No other change to the test is required.

**Verify now (before any `mcp/` exists)**: `pytest tests/test_layering.py -q` stays green — the new
`mcp` param has zero files to scan yet, so it trivially passes; the entry must not regress the other
layers.

## Sub-phase 1b — Relocate `resolve_target_column` → `core/columns.py`

**Source today**: `bin/kanban_move.py:93-116` defines the pure
`resolve_target_column(columns: dict[str, Column], target: str) -> Column` — **key-first** match,
**raises `KeyError`** on miss.

> ⚠️ This is **distinct** from the existing `core.columns.resolve_column(columns, token) -> Column | None`
> (`src/kanbanmate/core/columns.py:99-138`), which matches **name-first** and **returns `None`** on
> miss (the daemon's classification path). The two helpers have different precedence **and** different
> miss-behaviour; do **NOT** collapse them — the `move` tool and the `kanban-move` bin both depend on
> the raising, key-first variant. Keep `resolve_column` untouched.

**Action**:

1. **Move** `resolve_target_column` verbatim (its docstring + body) from `bin/kanban_move.py` into
   `src/kanbanmate/core/columns.py` — its natural home (`Column` is already defined there, imported via
   `from kanbanmate.core.domain import Column, ColumnClass`, `core/columns.py:25`). Place it next to
   `resolve_column`.
2. In `bin/kanban_move.py`, delete the local definition and add
   `from kanbanmate.core.columns import resolve_target_column` (the bin already imports `Column`-related
   names; keep its existing call sites unchanged — same name, same signature, same `KeyError`).

**Behaviour-preserving check**: `resolve_target_column` is pure (reads only its two args). The bin's
call site and error path are unchanged → the bin stays runtime-equivalent (DESIGN §11.1).

## Sub-phase 1c — Relocate base-clone git sync → `adapters/workspace/base_sync.py`

**Source today**: `bin/kanban_update_main.py` performs subprocess git ops via the module-local
`_git(...)` helper — `_git(["fetch", "origin", "main"], base_clone)` (`bin/kanban_update_main.py:~185`)
and `_update_dev_clone(dev_repo)` (`bin/kanban_update_main.py:~190`, which runs
`_git(["pull", "--ff-only"], dev_repo)`). These are a workspace/adapter concern (DESIGN §11.2).

**Action**:

1. Create `src/kanbanmate/adapters/workspace/base_sync.py` (sibling of `sessions.py` / `worktree.py` in
   `src/kanbanmate/adapters/workspace/`) exposing two functions with Google-style docstrings:
   - `fetch_base(clone: str | Path) -> None` — runs `git fetch origin main` in `clone`; raises (or
     returns a typed failure consistent with the bin's current handling) on non-zero exit. Match the
     bin's existing `_git` subprocess invocation (capture, `cwd=clone`, timeout discipline) exactly.
   - `ff_dev_clone(repo: str | Path) -> None` — runs `git pull --ff-only` in `repo` (strict
     fast-forward; never a merge commit, DESIGN §10), mirroring `_update_dev_clone`'s best-effort
     warning behaviour.
2. Re-point `bin/kanban_update_main.py` to import and call these (`from kanbanmate.adapters.workspace
import base_sync` or direct symbol import), removing the relocated bodies. Preserve the bin's exact
   stdout/stderr messages and return codes (its `main` flow at the `Fetching origin/main…` /
   `Fast-forwarding dev clone…` steps) so the bin stays byte-for-byte equivalent in behaviour.

**Note for the implementer**: read `bin/kanban_update_main.py` end-to-end first and lift the **real**
`_git` wrapper semantics (it uses `subprocess.run` with captured output and returncode checks). The new
adapter functions must reproduce those semantics; do not invent a new subprocess shape.

**Scope lever (DESIGN §11.2)**: if 1c proves too broad, the documented fallback is to **drop the
`update_main` MCP tool** (the only tool with no board effect) and ship the other five tools, deferring
this relocation. Prefer landing 1c; record the decision in the phase report if the fallback is taken.

## Sub-phase 1d — Declare the `mcp` SDK dependency (DESIGN §4.1)

**Files**: `pyproject.toml`, `.github/workflows/pr.yml`.

The `mcp` Python SDK is **NOT** a current dependency — it is not importable in the 3.12 project
interpreter and not declared in `pyproject.toml` (an earlier design draft wrongly assumed it present;
it was only importable in an unrelated 3.11 env). It must be declared before Phase 3's `server.py`
imports it. Mirror the existing `[ui]` extra (FastAPI) exactly:

1. **`pyproject.toml`** — add to `[project.optional-dependencies]` (next to `ui`):

   ```toml
   mcp = [
       "mcp>=1.26",
   ]
   ```

   (`mcp 1.28.0` is verified pip-installable on Python 3.12.4.)

2. **`.github/workflows/pr.yml:32`** — change `pip install -e ".[dev,ui]"` to
   `pip install -e ".[dev,ui,mcp]"` so CI (ruff/mypy/tests) has the SDK; the Phase 2/3 tests import it.
3. **Deploy note** (operator action, not a code change): the daemon/agent editable install must add
   `[mcp]` (`pip install -e .[dev,ui,mcp]`) so worktree agents can actually run `kanban mcp`.

**Import-guard contract** (implemented in Phase 3, stated here): the `kanban mcp` command lazy-imports
the server inside the command body behind `try/except ImportError`, raising a friendly "install
`.[mcp]`" message — exactly as `cli/config.py` guards the `serve` import behind `[ui]`. The bare
`kanban` CLI keeps working without `[mcp]`.

**Verify**: `pip install -e ".[mcp]"` then
`python -c "import mcp; from mcp.server import Server; from mcp.server.stdio import stdio_server"`
succeeds in the 3.12 project interpreter; `kanban --help` still works in an env WITHOUT `[mcp]`.

## Tests / gate for Phase 1

- `tests/test_layering.py` green (the new `mcp` entry regresses nothing).
- `tests/bin/` (existing `kanban-move` / `kanban-update-main` tests) green — proves the relocations are
  behaviour-preserving. If a relocated function lacked direct coverage, add a focused unit test:
  - `tests/core/test_columns.py`: `resolve_target_column` returns the right `Column` for a **key** and
    for a **name**, and raises `KeyError` on an unknown token (use real keys from a `load_columns`
    fixture — never an empty mapping).
  - `tests/adapters/` : a `base_sync` test may stub subprocess; keep it consistent with how existing
    workspace adapter tests fake git.
- `make check` green (ruff + mypy + module-size guards; no module crosses the 1000-LOC ceiling).
- Residual-import grep: `rg --type py 'def resolve_target_column' src/` returns the `core/columns.py`
  definition **only** (not `bin/kanban_move.py`); `rg --type py '_update_dev_clone|_git\(' src/kanbanmate/bin/kanban_update_main.py`
  shows the bin now delegates to `base_sync`.

## Commit

`chore(conduit): phase 1 — layering mcp entry + relocate resolve_target_column & base-clone sync`
