# conduit — MCP board surface

> **Codename**: conduit · **roadmap**: mcp · **bump**: minor (0.7.1 → 0.8.0 — new shell surface,
> purely additive) · **Branch**: `feat/conduit` · **Mode**: single feature branch (one PR).

## 1. Goal

Expose the Kanban board as a rich **MCP (Model Context Protocol)** surface so an autonomous agent
can reason about board state **and act on its own ticket without shelling out** to the `kanban-*`
helper bins. Full **read + write parity** (operator decision): read **resources** for the board
state and write **tools** wrapping the helper actions.

The MCP server is an **additive parallel surface**: it shares the exact same `core`/`app` write
functions the bins call, performs **no direct GitHub writes**, and is **pinned** to the agent's own
issue. The existing `kanban-*` bins are **kept unchanged** in behaviour — zero migration risk to the
live daemons, the shell, or CI.

## 2. Locked decisions (from the brainstorm)

1. **Surface**: read + write parity — resources for state AND tools wrapping the helper actions.
2. **Write routing**: MCP write tools call the **exact same `core`/`app` functions** the bins call.
   `move` ⇒ enqueue an intent the daemon drains with derived authority (cockpit #28 unification);
   `update_body` ⇒ marker/title coherence-validated edit. One audited write path, no duplicated
   GitHub logic, **no direct GitHub writes**.
3. **Bins fate**: KEEP the `kanban-*` bins. MCP is additive. (The pure helpers the bins and MCP
   both need are _relocated_ to permitted layers — see §11 — which is behaviour-preserving for the
   bins: an import-only change, not a migration.)
4. **Pinning**: the worktree-launched server is **pinned to the agent's issue #** (passed at launch
   via `--issue`). Write tools refuse any other issue; read resources still see the whole board.
5. **Transport**: stdio (no port/auth/HTTP surface). HTTP transport is explicitly out of scope.
6. **No `merge` tool, ever** — merge stays human / merge-agent only.

## 3. Architecture & layering

A new **top-level shell layer** `src/kanbanmate/mcp/`, a sibling of `http/` · `cli/` · `daemon/` ·
`bin/`. It imports `app` / `core` / `adapters` / `ports` / `cli` only — never `daemon` or `bin`.
This mirrors `http/`, which "sits at the TOP of the import hierarchy alongside `cli` and `daemon`…
it may import `app` / `adapters` / `core` but NOT the sibling entrypoints"
(`src/kanbanmate/http/__init__.py:1-13`). The MCP shell holds **no domain logic** — serializers and
tool bodies are thin wrappers over already-existing `core`/`app`/port functions; the SDK is a pure
transport adapter.

### 3.1 Layering guard extension

The downward-only import guard is `tests/test_layering.py`. It does a **full AST walk**
(`ast.walk(tree)`, `_imported_modules`, `tests/test_layering.py:69-101`) — so a **function-local
import does NOT bypass it** — and matches each module against a per-layer forbidden-prefix map
(`FORBIDDEN`, `tests/test_layering.py:29-49`), parametrised over `sorted(FORBIDDEN)`
(`tests/test_layering.py:131`). The map currently ends at:

```python
# tests/test_layering.py:38-48 (verbatim, the http entry being the template)
"app": ["cli", "daemon"],
"http": ["daemon", "bin"],
```

**Extension**: add one entry, modelled exactly on `http`:

```python
"mcp": ["daemon", "bin"],
```

This permits `mcp/` → `app` / `adapters` / `core` / `ports` / `cli` (the same set `http/` enjoys —
`http/config_api.py` already imports `cli.init`), and forbids `mcp/` → `daemon` / `bin`. The guard
auto-discovers the new layer via the `parametrize` over `FORBIDDEN`; no other test change is needed.
**Consequence**: the MCP shell may **not** import `bin/_pin.py` or `bin/kanban_move.py` even from
inside a function — hence the relocations in §11.

### 3.2 Module map (`src/kanbanmate/mcp/`)

```
mcp/
  __init__.py        # layer docstring (mirrors http/__init__.py)
  server.py          # main(root, issue, …) — wires Deps, builds the SDK Server, runs stdio
  resources.py       # pure serializers: board / ticket / agents / queue / health / events  → dict
  tools.py           # thin write/read tool bodies over core/app fns; pinning + PAUSE guards
  pin.py             # pure pin-mismatch guard for the shell (see §7)
```

`resources.py` and `tools.py` functions take already-wired ports (`BoardReader`, `BoardWriter`,
`StateStore`) and plain values as arguments and return JSON-serialisable `dict`s — they are unit
testable **without** the MCP SDK. `server.py` is the only module that imports `mcp`.

## 4. Entry point & wiring

New CLI command `kanban mcp`, modelled on `kanban serve` (`src/kanbanmate/cli/app.py:103-148`): a
direct `@app.command()` that lazy-imports the server module inside the body and delegates.

```python
# src/kanbanmate/cli/app.py — new command (sketch, mirrors serve at :103)
@app.command()
def mcp(
    root: Path = typer.Option(_DEFAULT_ROOT, "--root", help="Kanban runtime root (default ~/.kanban)."),
    issue: int = typer.Option(..., "--issue", help="The agent's pinned issue number (write tools refuse any other)."),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Start the stdio MCP board server, pinned to ``--issue`` (conduit / roadmap mcp)."""
    from kanbanmate.mcp import server as mcp_server
    mcp_server.main(root=root.expanduser(), issue=issue, project=project, repo=repo)
```

`_PROJECT_OPTION` / `_REPO_OPTION` already exist for the multi-project commands
(`cli/app.py:475-504` `status` is the template). The server wires the **same adapters the
daemon/CLI use** through the existing wiring path:

```python
# src/kanbanmate/mcp/server.py — wiring (uses the established CLI helpers)
deps = build_deps(_wiring_for(root, project=project, repo=repo))
```

`_wiring_for(root, *, project, repo)` (`cli/app.py:151-186`) loads the board `WiringConfig`
(`config.yml` when present, else the registry selection); `build_deps(config)`
(`app/wiring.py:112-186`) constructs the `GithubClient` (satisfying `BoardReader` **and**
`BoardWriter`), the `FsStateStore`, and the rest. The MCP server needs exactly three of the wired
ports: `deps.board_reader`, `deps.board_writer`, `deps.store`.

### 4.1 The SDK server

Built on the `mcp` Python SDK — low-level `from mcp.server import Server` +
`from mcp.server.stdio import stdio_server`. **The SDK is NOT yet a project dependency**: it is not
importable in the 3.12 project interpreter and not declared in `pyproject.toml` (an earlier draft
wrongly assumed it present — it was only importable in an unrelated 3.11 env). Phase 1 therefore
**adds it as a `[mcp]` optional extra** (`mcp>=1.26`, mirroring the `[ui]` extra for FastAPI), CI is
updated to install `.[dev,ui,mcp]`, the deploy/agent editable install must include `[mcp]`, and the
`kanban mcp` command **guards the import** behind `try/except ImportError` exactly as `cli/config.py`
guards the `serve` import (so the bare `kanban` CLI still runs without `[mcp]`). `mcp 1.28.0` is
verified pip-installable on 3.12.4. `server.py` uses the **low-level**
`mcp.server.Server` and registers four handlers — `list_resources`, `read_resource`, `list_tools`,
`call_tool` — each a thin dispatcher into the pure `resources.py` / `tools.py` functions, then runs
over `stdio_server()`. (FastMCP's decorator API was considered; the low-level Server keeps the
serializers/tool bodies SDK-free and explicitly testable, which fits the functional-core rule.)

`server.main(...)` is **side-effect-free at import time** (mirrors `http/serve.py:461`): all wiring
and the blocking stdio run happen inside `main`.

## 5. Resources (read — whole board, NOT pinned)

Resources reuse existing read models verbatim; serializers live in `mcp/resources.py`.

| URI                   | Backed by                                                                                                                       | Returns                                                                                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `kanban://board`      | `cli.state.build_state(board_reader, store, …)` + `cli.state.render_state_json`                                                 | The unified state read model — `health, paused, degraded, board{columns,total}, agents[], queue[], events[] (newest-first), daemon` (`cli/state.py:108-155`).                     |
| `kanban://ticket/{n}` | `board_reader.issue_context(n)` (`ports/board.py:68-90`) + the `Ticket` from `board_reader.snapshot()` (`ports/board.py:41-49`) | `{issue_number, title, column_key, body, comments[], linked_issue_body}` — body + comment history + linked-issue body (the same enrichment `app/launch_context.py:70-77` builds). |
| `kanban://agents`     | `store.list_running()` (`ports/store.py:293-307`)                                                                               | One row per LIVE ticket (`TicketState`): `issue_number, item_id, session_id, status, heartbeat, stage, profile, …` (`ports/store.py:81-161`).                                     |
| `kanban://queue`      | `store.dequeue_pending()` + `store.load_queued(n)` (`ports/store.py:667-702`)                                                   | The launch queue: `[{issue_number, stage, enqueued_at}]`.                                                                                                                         |
| `kanban://health`     | `store.get_status_last_enum()` (`ports/store.py:805-823`)                                                                       | The last-posted rolling-status enum (the health pill), or `null`.                                                                                                                 |
| `kanban://events`     | `store.read_status_events()` (`ports/store.py:873-890`)                                                                         | The recent-events ring (≤10), newest-first: `[{ts, kind, issue, detail}]` (kinds = `EVENT_EMOJI` keys, `core/status_update.py:86-103`).                                           |

For `kanban://board` the cleanest reuse is to call the existing imperative shell
`cli.state.state(board_reader, store, root=root, ttl=HEARTBEAT_TTL_FLOOR, as_json=True)`
(`cli/state.py:190-226`) and return its JSON — it already reads `PAUSE` / `DEGRADED` / daemon
heartbeat / queue off `root` and renders the stable shape. `ticket`/`agents`/`queue`/`health`/
`events` call their narrower port methods directly so each resource is independently cheap.

## 6. Tools

Read tools mirror the resources (some MCP clients invoke tools more reliably than they read
resources — locked decision, open question (a)). Write tools are **pinned** and route through the
same `core`/`app` function each bin uses.

### 6.1 Read tools (not pinned)

| Tool                | Backed by                                       |
| ------------------- | ----------------------------------------------- |
| `get_board()`       | same as `kanban://board`                        |
| `get_ticket(issue)` | same as `kanban://ticket/{n}`                   |
| `get_state()`       | alias of `get_board()` (the unified read model) |

### 6.2 Write tools (pinned — refuse any issue ≠ the server's pin; see §7)

| Tool                                                                         | Args                        | Routes through (identical to the bin)                                                                                                                                                                        | Bin parity                          |
| ---------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------- |
| `comment(issue, body)`                                                       | issue, body                 | `board_writer.comment(issue, body)`                                                                                                                                                                          | `bin/kanban_comment.py:207`         |
| `progress(issue, line, stage=None)`                                          | issue, line, optional stage | `app.stage_signal.upsert_stage_comment(writer, issue, stage, append=line, now=…)` (`app/stage_signal.py:48-56`); free-form fallback `board_writer.comment(issue, stamped)` when no stage                     | `bin/kanban_progress.py:200,222`    |
| `move(issue, to_col)`                                                        | issue, target key/name      | `store.enqueue_intent(id, payload)` + `store.nudge_daemon()` (`ports/store_intents.py:24,78`); payload `{"kind":"move","issue":issue,"args":{"to_col":column.key},"requested_at":now,"caller":"agent"}`      | `bin/kanban_move.py:233-246`        |
| `done(issue)`                                                                | issue                       | `store.record_agent_done(issue, now=…)` (`ports/store.py:413`)                                                                                                                                               | `bin/kanban_done.py:66`             |
| `update_body(issue, set_field=(key,value) \| append_section=(heading,text))` | issue + one mode            | `core.body_edit.set_field` / `append_section` (`core/body_edit.py:66,103`) → `core.body_edit.validate_roadmap_matches_title` (`core/body_edit.py:258`) → `board_writer.update_issue_body(node_id, new_body)` | `bin/kanban_update_body.py:210-227` |
| `update_main()`                                                              | —                           | `adapters.workspace.base_sync.fetch_base(...)` + `ff_dev_clone(...)` (relocated git-sync, §11.2)                                                                                                             | `bin/kanban_update_main.py:182,190` |

`comment`/`progress`/`update_body` need the issue's GraphQL node id; the server resolves it the same
way the bins do — `board_writer`/`GithubClient` exposes `fetch_issue` /
`update_issue_body(node_id, body)` (`bin/kanban_update_body.py:205,227`). `update_body` is the
**single** coherence-gated write: the post-edit `validate_roadmap_matches_title` returns a non-`None`
message ⇒ the tool refuses and surfaces that message (it never desyncs the ticket↔roadmap binding).

The `move` tool also mirrors the bin's **pre-flight pair-aware anti-loop guard**
(`bin/kanban_move.py:209-230`, UX only): it refuses when `(from_col, to_col)` is itself a
prompt-bearing launch transition. The **authoritative** gate remains the daemon's `validate_intent`
under daemon-derived authority (`app/intents.py:166`, `core/intent.py:124-222`), which alone enforces
R1, the Merge deny, and the wildcard-aware re-fire guard. The MCP shell does **not** re-implement that
authority — it enqueues an intent exactly as the bin does and lets the daemon decide.

The `to_col` target string (key **or** display name) is resolved by the relocated pure
`resolve_target_column(columns, target)` (§11.1). The `columns` model is read from the wired board
config (`build_tick_config`, `app/wiring.py:189-231`).

## 7. Safety invariants (inherited, not reinvented)

- **Pinning on every write.** The server is constructed with `pinned_issue=<--issue>`. Each write
  tool first calls the pure `mcp.pin.pin_violation(requested, pinned)` → returns a refusal message
  (string) when `requested != pinned`, else `None`. The tool returns the refusal and performs no I/O.
  This mirrors `bin/_pin.check_pin` (`bin/_pin.py:244-252`), which does the same comparison — but the
  MCP shell may **not** import `bin/_pin` (forbidden by §3.1) **and does not need to**: the pinned
  value is supplied at launch via `--issue` (the worktree's `.claude/kanban-issue`, written by
  `adapters/perms.write_issue_pin`, `adapters/perms.py:718-743`, is the source of that value). The
  pure comparison lives in `mcp/pin.py` (a shell-local helper, no relocation needed — there is no
  forbidden-layer _value_ to import, only a one-line `!=`).
- **PAUSE kill-switch floor.** Each write tool first checks `store.kill_switch_active()`
  (`ports/store.py:491`, impl `adapters/store/fs_store.py:379-395` = `<root>/PAUSE` exists). When the
  sentinel is present the tool refuses, mirroring how the bins/daemon degrade under PAUSE. Read
  resources are unaffected (PAUSE surfaces as the `paused` banner in `kanban://board`).
- **`move` keeps the agent rule** (only **non-triggering** target pairs): enforced by the daemon's
  `validate_intent` as above; the MCP shell adds the same UX pre-flight as the bin.
- **Intent-queue authority + body coherence** are preserved because the tools call the very same
  functions (`enqueue_intent`/`validate_roadmap_matches_title`) — no parallel path.
- **No `merge` tool** is registered, in any form.

## 8. Lifecycle wiring — `.mcp.json` materialisation

The launch path materialises each worktree's `.claude/settings.json` + perms profile via
`adapters.perms.materialise_settings(profile, worktree, issue=…, permission_mode=…)`
(`adapters/perms.py:560-613`), called from `app.actions.LaunchAction.execute` at
`app/actions.py:317`, in the block that also writes skills/bin-symlinks/pins (`app/actions.py:309-338`).

Two additions, both in that same block (the **only** change to the deployed startup path):

1. **New** `adapters.perms.write_mcp_registration(worktree, *, root, issue, project_id, multi_project)`
   — writes `<worktree>/.mcp.json` (project-scoped MCP config Claude Code reads from the project
   root), following the write pattern of `materialise_settings`/`write_issue_pin`:

   ```json
   {
     "mcpServers": {
       "kanban": {
         "command": "kanban",
         "args": ["mcp", "--root", "<root>", "--issue", "<n>"]
       }
     }
   }
   ```

   `--project <project_id>` is appended to `args` only when `multi_project` is true (the per-project
   disambiguation the bins use). Called right after `materialise_settings` at `app/actions.py:317`.

2. **Pre-trust the server for headless agents.** Project `.mcp.json` servers are not trusted by
   default, and these agents run non-interactively. `build_settings`/`materialise_settings`
   (`adapters/perms.py:560,607`) must therefore also emit `"enabledMcpjsonServers": ["kanban"]` into
   the worktree `settings.json`, so the agent loads the `kanban` MCP server without an approval
   prompt. (Scoped to the single named server — not a blanket `enableAllProjectMcpServers`.)

No change to the daemon, the polling loop, or any existing bin is required.

## 9. Resource freshness / cost (open question (b), resolved)

Resources are read **live, on demand** — no caching in this PR. `kanban://board` and
`kanban://ticket/{n}` each cost one timed GraphQL `snapshot()` / `issue_context()` call (the same
calls the daemon makes; both carry the urllib client's connect+read timeouts). Agent MCP reads are
infrequent relative to the daemon poll, so a `cheap_probe`-gated cache is unnecessary complexity for
PR1; it is noted as a future optimisation only. The store-backed resources (`agents`/`queue`/
`health`/`events`) are local filesystem reads — negligible cost.

## 10. Open questions — resolved

- **(a) Resource and tool for the same data?** **Both** (client invocation-reliability variance).
- **(b) Per-call snapshot cost?** Fresh snapshot per call; no cache in PR1 (§9).
- **(c) Expose MCP prompts?** **No** (YAGNI) — resources + tools only.
- **(d) Single-root / single-issue per agent sufficient?** **Yes** — agents are always single-ticket;
  the server pins to one `--issue` and one `--root`.

## 11. Refactors required (layering-driven, behaviour-preserving)

Two pure/impure helpers that the write tools need currently live in `bin/` (forbidden for `mcp/` per
§3.1). Each is relocated to its natural permitted layer and re-imported by the bin — an **import-only,
behaviour-preserving** change, so the bins stay byte-for-byte equivalent at runtime (honours locked
decision 3).

1. **`resolve_target_column(columns, target)`** — pure (a `dict[str,Column]` + a string → `Column`,
   raising `KeyError` on miss; `bin/kanban_move.py:93-116`). **Relocate to `core/columns.py`**
   (its natural home — `Column` is already defined there). `bin/kanban_move.py` re-imports it from
   `core.columns`; `mcp/tools.py` imports it from `core.columns`.

2. **base-clone git sync** — `_git(["fetch","origin","main"], base_clone)` +
   `_update_dev_clone(dev_repo)` (`bin/kanban_update_main.py:118,182,190`) are subprocess git ops, a
   workspace/adapter concern. **Relocate to a new `adapters/workspace/base_sync.py`**
   (`fetch_base(clone)` + `ff_dev_clone(repo)`). `bin/kanban_update_main.py` re-imports them; the
   `update_main` MCP tool calls them directly. (If the plan stage judges the relocation too broad for
   PR1, the fallback is to drop `update_main` from the tool set — it is the only tool with no board
   effect — and ship the other five; this is the single scope lever and is called out for the plan.)

No relocation is needed for `comment` / `progress` / `done` / `update_body` / `move`: every function
they call (`board_writer.comment`, `app.stage_signal.upsert_stage_comment`,
`store.record_agent_done`, `core.body_edit.*`, `store.enqueue_intent`/`nudge_daemon`) already lives
in a permitted layer (`app` / `core` / `ports`).

## 12. Testing

Fakes for `BoardReader` / `BoardWriter` / `StateStore` already exist under the suite. New tests live
in **`tests/mcp/`** (mirroring `tests/core/`, `tests/app/`, `tests/http/`, …; the test tree is
layer-mirrored — `find tests -type d` shows `tests/{core,app,adapters,cli,daemon,http,bin,integration}`).

- **`tests/mcp/test_resources.py`** — each serializer (`board`/`ticket`/`agents`/`queue`/`health`/
  `events`) against fakes pre-seeded with **real** values: real column **keys** (not display labels),
  a snapshot with ≥1 `Ticket`, a non-empty events ring, a live `TicketState`. Assert the produced
  `dict` matches the documented shape — never assert two empty sides.
- **`tests/mcp/test_tools.py`** — for each write tool: (i) **pinning** — a tool called with
  `issue != pinned` returns the refusal and performs **zero** writes on the fake; (ii) **PAUSE** — with
  the fake store reporting `kill_switch_active() is True`, the tool refuses; (iii) **routing** —
  `move` results in exactly one `enqueue_intent` with the expected payload + one `nudge_daemon`;
  `update_body` with a roadmap/title mismatch refuses via `validate_roadmap_matches_title` and never
  calls `update_issue_body`; `done` calls `record_agent_done` once.
- **`tests/mcp/test_server_roundtrip.py`** — an in-process MCP **client over stdio** round-trip: list
  resources/tools, read `kanban://board`, call a read tool, and assert a pinned write tool refuses a
  foreign issue end-to-end through the SDK.
- **`tests/test_layering.py`** — the new `"mcp"` entry is auto-exercised by the existing
  parametrised guard; add an explicit assertion (or rely on the parametrize) that `mcp/` imports
  nothing from `daemon`/`bin`.
- **`tests/test_perms.py`** — `write_mcp_registration` writes a well-formed `.mcp.json`; the
  materialised `settings.json` carries `enabledMcpjsonServers: ["kanban"]`.

`make check` (ruff + mypy + tests + module-size guards) must be green; every module respects the
1000-LOC hard ceiling.

## 13. Durable cross-stage carry & version

This DESIGN.md is committed to the per-ticket WIP branch so the plan/create-branch stages see it
without a push (worktrees share one `.git`). The **design** marker is set to the repo-relative path
`docs/features/conduit/DESIGN.md`.

Version bump on implementation: **0.7.1 → 0.8.0** (minor — a new additive shell surface; no breaking
change to the deployed daemons, bins, or CLI). `pyproject.toml:version` + `src/kanbanmate/__init__.py:__version__`.

## 14. Summary of changes (for the plan stage)

| Area            | Change                                                                                     | Anchor                                                             |
| --------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| New layer       | `src/kanbanmate/mcp/{__init__,server,resources,tools,pin}.py`                              | new                                                                |
| Dependency      | add `mcp>=1.26` as a `[mcp]` optional extra; CI installs `.[dev,ui,mcp]`; cli import-guard | `pyproject.toml` (`[ui]` precedent), `.github/workflows/pr.yml:32` |
| CLI             | `kanban mcp --root --issue [--project --repo]` command                                     | `cli/app.py:103` (serve template)                                  |
| Layering        | add `"mcp": ["daemon", "bin"]` to `FORBIDDEN`                                              | `tests/test_layering.py:29-49`                                     |
| Relocate (pure) | `resolve_target_column` → `core/columns.py`; bin re-imports                                | `bin/kanban_move.py:93`                                            |
| Relocate (git)  | base-clone sync → `adapters/workspace/base_sync.py`; bin re-imports                        | `bin/kanban_update_main.py:118`                                    |
| Lifecycle       | `write_mcp_registration` (→ `.mcp.json`) + `enabledMcpjsonServers` in settings             | `adapters/perms.py:607`; called at `app/actions.py:317`            |
| Tests           | `tests/mcp/{test_resources,test_tools,test_server_roundtrip}.py` + perms/layering deltas   | new                                                                |
| Version         | 0.7.1 → 0.8.0                                                                              | `pyproject.toml`, `__init__.py`                                    |
