# conduit — implementation plan (INDEX)

> **Codename**: conduit · **roadmap**: mcp · **bump**: minor (0.7.1 → 0.8.0) ·
> **Branch**: `feat/conduit` · **Mode**: single feature branch (one PR).
> **Design**: `docs/features/conduit/DESIGN.md`

## Goal (one line)

Expose the Kanban board as an additive **stdio MCP** surface (read resources + pinned write tools)
that shares the exact `core`/`app`/port functions the `kanban-*` bins call — no direct GitHub
writes, no change to the deployed daemons/bins/CLI behaviour.

## Phase ordering rationale

Phase 1 lands the layering-driven, behaviour-preserving relocations **first** because `mcp/tools.py`
imports the relocated symbols (`core.columns.resolve_target_column`,
`adapters.workspace.base_sync.{fetch_base,ff_dev_clone}`) and the layering guard must accept the new
`mcp` layer before any `mcp/` file can land green. Phase 2 builds the SDK-free pure shell (serializers,
tool bodies, pin guard) that Phase 3's `server.py` dispatches into; the `kanban mcp` CLI command
(Phase 3) must exist before Phase 4 writes a `.mcp.json` that invokes it. Phase 5 bumps the version and
runs the full gate.

## Phases

| # | Phase | File | Status |
| --- | --- | --- | --- |
| 1 | Layering guard + behaviour-preserving relocations | phase-01-layering-relocations.md | [ ] |
| 2 | MCP pure shell — pin, resources, tools (SDK-free) + unit tests | phase-02-pure-shell.md | [ ] |
| 3 | SDK server + `kanban mcp` command + roundtrip test | phase-03-server-cli.md | [ ] |
| 4 | Lifecycle wiring — `.mcp.json` + `enabledMcpjsonServers` | phase-04-lifecycle-wiring.md | [ ] |
| 5 | Version bump + final gate | phase-05-version-gate.md | [ ] |

## Cross-cutting invariants (every phase upholds)

- **Layering**: `core/` imports nothing below it; `mcp/` may import `app`/`adapters`/`core`/`ports`/`cli`
  but **never** `daemon`/`bin` (`tests/test_layering.py:38-49`, full AST walk
  `tests/test_layering.py:69-101` — a function-local import does **not** bypass it).
- **No direct GitHub writes from `mcp/`**: every write tool routes through the same `core`/`app`/port
  function the bin uses (DESIGN §6, §11).
- **No `merge` tool**, ever (DESIGN §2.6, §6, §7).
- **Pinning + PAUSE** guard on every write tool (DESIGN §7).
- **Bins stay byte-for-byte equivalent at runtime**: relocations are import-only (DESIGN §11).
- `make check` (ruff + mypy + tests + module-size guards, 1000-LOC hard ceiling) green at each gate.
- New tests live under `tests/mcp/` (mirroring the layer-named test tree
  `tests/{core,app,adapters,cli,daemon,http,bin,integration,local_real}`), with real column **keys**
  and non-empty fixtures — never assert two empty sides.
