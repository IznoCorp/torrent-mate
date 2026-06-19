# Phase 5 — Version bump + final gate

**Goal**: bump the version for the additive shell surface and run the full quality gate (DESIGN §13).

## Sub-phase 5a — Version bump 0.7.1 → 0.8.0

Minor bump — a new additive shell surface with **no** breaking change to the deployed daemons, bins, or
CLI (DESIGN §13).

- `pyproject.toml` — `version = "0.8.0"` (currently `0.7.1`; confirm the exact current value before
  editing — the `[project]` `version` field).
- `src/kanbanmate/__init__.py` — `__version__ = "0.8.0"` (currently `0.7.1`; keep the two in sync — the
  prior `__version__`/`pyproject` drift is a known footgun).

Verify they match after editing: `python -c "import kanbanmate; print(kanbanmate.__version__)"` prints
`0.8.0` and `grep '^version' pyproject.toml` shows `0.8.0`.

## Sub-phase 5b — Final full gate

Run the project's phase-gate checklist (CLAUDE.md):

1. `make lint` — ruff + mypy, zero errors.
2. `make test` — all pass (check the summary line; any ERROR = collection crash, fix imports first).
3. `make check` — lint + test + module-size guards (every `mcp/` module under the 1000-LOC hard
   ceiling).
4. Residual-import grep in `src/` **and** `tests/` for the relocated symbols:
   - `rg --type py 'def resolve_target_column'` → `core/columns.py` **only**.
   - `rg --type py 'from kanbanmate.bin' src/kanbanmate/mcp` → **zero** matches (the `mcp` layer never
     imports `bin`).
   - `rg --type py 'import.*daemon' src/kanbanmate/mcp` → **zero** matches.
5. `python -c "import kanbanmate"` and `python -c "import kanbanmate.mcp.server"` smoke tests.
6. `pytest tests/test_layering.py -q` green — the parametrised guard exercises the `mcp` layer and finds
   no upward imports.

## Sub-phase 5c — Definition-of-done cross-check (self-review)

Confirm against DESIGN §14 (summary of changes) that every row landed:
- New layer `src/kanbanmate/mcp/{__init__,server,resources,tools,pin}.py` — present.
- CLI `kanban mcp --root --issue [--project --repo]` — registered.
- Layering `"mcp": ["daemon","bin"]` in `FORBIDDEN` — present.
- Relocations: `resolve_target_column` → `core/columns.py`; base-clone sync →
  `adapters/workspace/base_sync.py`; both bins re-import.
- Lifecycle: `write_mcp_registration` (`.mcp.json`) + `enabledMcpjsonServers` — present, called at the
  launch block.
- Tests: `tests/mcp/{test_resources,test_tools,test_server_roundtrip}.py` + perms/layering deltas.
- Version 0.8.0 in both `pyproject.toml` and `__init__.py`.
- **No `merge` tool** anywhere.

## Commit

`chore(conduit): phase 5 — bump 0.7.1 → 0.8.0 + final gate`

(Per the milestone-commit convention, the phase-gate commit may instead read
`chore(conduit): phase 5 gate — MCP board surface`.)
