# Phase 1 — Bootstrap Engine + Polling Core

> Each sub-phase = ONE commit `<type>(genesis): <description>`. Full gate checklist before gate commit.
> Architecture invariants: DESIGN §3.2 layering (downward-only); network timeouts on every urllib
> request; `shlex.quote` all subprocess paths. Module ceiling 1000 LOC.

**Goal**: Scaffold repo + packaging; port reusable engine from PoC; build NEW `diff`/`tick`/`daemon`.
Drop `payload`/HMAC/n8n entirely. CI green on unit + local-real.
**Design refs**: §3 arch, §5 daemon, §12 layout, §14 P1.

---

## Gate

Fresh repo, `VERSION 0.1.0`, `DESIGN.md` present.
**Blocking pre-implementation (DESIGN §11)**: re-sync latest PoC from
`PersonnalScaper/.claude/skills/kanban/` before writing any ported code.

---

### 1.1 — PoC re-sync audit

- [ ] Enumerate PoC modules to PORT vs DROP (`payload.py`, HMAC parts, `n8n/`) vs CREATE NEW
      (`core/domain.py`, `core/diff.py`, etc. per DESIGN §3.3).
- [ ] Read `bin/kanban-heartbeat`, `engine/stage_comment.py`, `engine/teardown.py`,
      `cli/plan_cancel.py` — note interfaces for §8.1/§8.2/§8.3 (wired in Phase 5 only).
- [ ] Confirm heartbeat hook is command-string form per DESIGN §8.3.

**Verification**: no commit; proceed only after audit complete.

---

### 1.2 — Package scaffolding + Makefile

**Files**: `pyproject.toml`, `Makefile`, `src/kanbanmate/__init__.py`, `src/kanbanmate/py.typed`,
`tests/__init__.py`, `tests/conftest.py`.

- [ ] `pyproject.toml`: package `kanbanmate`, entry `kanban="kanbanmate.cli.app:main"`,
      deps `typer>=0.12 PyYAML>=6 attrs>=23`, dev extras `pytest ruff mypy types-PyYAML`,
      markers `local_real` + `integration`, ruff line-length=100 py311, mypy strict.
- [ ] `Makefile` targets: `lint` (ruff+mypy), `test` (`-m "not integration"`), `check`
      (lint+test+size), `size` (soft 800 / hard 1000 LOC per file).
- [ ] `src/kanbanmate/__init__.py`: `__version__ = "0.1.0"` only.
- [ ] Verify: `pip install -e ".[dev]"` succeeds; `python -c "import kanbanmate"` exits 0; `make lint` passes.

```bash
git commit -m "chore(genesis): package scaffolding + Makefile"
```

---

### 1.3 — Hexagonal directory layout + layering guard

**Files**: `src/kanbanmate/{core,ports,adapters,app,daemon,cli,bin}/__init__.py` stubs,
`tests/test_layering.py`.

- [ ] All `__init__.py` stubs: docstring only, no imports.
- [ ] `test_layering.py`: AST-walk each layer's `.py` files; assert no upward imports
      (`core`/`ports` → nothing; `adapters` → not app/cli/daemon; `app` → not cli/daemon).
      Skip layers whose directory is empty. Parametrize over `FORBIDDEN: dict[str, list[str]]`.
- [ ] Verify: `make test` — layering tests skip (empty) — OK.

```bash
git commit -m "chore(genesis): hexagonal directory layout + layering guard"
```

---

### 1.4 — `core/domain.py`

**Files**: `src/kanbanmate/core/domain.py`, `tests/core/__init__.py`, `tests/core/test_domain.py`.

- [ ] Pure frozen dataclasses, zero I/O, zero upward imports. Types: `ColumnClass(Enum)`
      AGENT/REACTIVE/INERT; `Column`, `Ticket`, `BoardSnapshot(tickets: tuple[Ticket,...], fetched_at: float)`,
      `Transition(ticket, from_column: str|None, to_column: str)`,
      `ActionKind(Enum)` LAUNCH/TEARDOWN/RESET/BLOCK/NOOP, `Action(kind, ticket, reason)`.
- [ ] `test_domain.py`: frozen asserts, ColumnClass values, Transition.from_column=None OK.
- [ ] Verify: `make test` pass, `make lint` zero errors.

```bash
git commit -m "feat(genesis): core domain model (Ticket, Column, BoardSnapshot, Transition, Action)"
```

---

### 1.5 — `core/columns.py` + `core/antiloop.py` + `core/interval.py`

**Files**: `src/kanbanmate/core/{columns,antiloop,interval}.py`,
`tests/core/test_{columns,antiloop,interval}.py`, `assets/columns.yml.tmpl`.

- [ ] `columns.py`: `load_columns(yaml_text: str) → dict[str, Column]` — pure YAML parse, set
      ColumnClass from `triggers_agent` / `action: teardown` / neither.
- [ ] `antiloop.py`: port from PoC `engine/cap.py` — target-keyed guard + per-ticket rate-limit;
      `is_blocked(state, ticket_id, target_col) → bool`.
- [ ] `interval.py`: `next_sleep(last_activity_ts, cfg) → float` — short when active, backs off to
      `cfg.idle_max` when idle (DESIGN §3.3 `interval.py` strategy).
- [ ] `assets/columns.yml.tmpl`: default 11 columns per DESIGN §9 (agent: In Progress, PR/CI,
      Review; reactive: Cancel; inert: rest).
- [ ] Tests: agent/reactive/inert YAML; antiloop allows first/blocks second; interval short/long.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): core columns, antiloop, interval (ported + adapted)"
```

---

### 1.6 — `core/diff.py` + `core/decide.py` + `core/dependency_gate.py`

**Files**: `src/kanbanmate/core/{diff,decide,dependency_gate}.py`,
`tests/core/test_{diff,decide}.py`.

- [ ] `diff.py`: `diff(persisted: dict[str,str], snapshot: BoardSnapshot) → list[Transition]`.
      Yield Transition when `ticket.column_key != persisted.get(item_id)`; `from_column=None` for
      new items. This replaces all PoC payload parsing.
- [ ] `decide.py`: `decide(transition, columns, ctx) → Action`. ctx carries antiloop state,
      kill-switch flag, unattended-hours. Rules: agent col→LAUNCH; reactive→TEARDOWN;
      Cancel→Backlog→RESET; antiloop/kill-switch→BLOCK; else NOOP.
- [ ] `dependency_gate.py`: `evaluate(issue_body, snapshot) → (bool, str)` — parse
      `Depends on #N`, check N in Done/Merge column. Pure.
- [ ] Tests: diff — no-change empty; move detected; new item; multi. decide — all branches.
- [ ] Verify: `make test` pass, `make lint` zero errors.

```bash
git commit -m "feat(genesis): core diff + decide (polling heart, replaces payload/HMAC)"
```

---

### 1.7 — Ports layer

**Files**: `src/kanbanmate/ports/{board,workspace,store,clock}.py`.

- [ ] `board.py`: `BoardReader(Protocol)` — `cheap_probe()->str`, `snapshot()->BoardSnapshot`.
      `BoardWriter(Protocol)` — `move_card(item_id, column_key)`, `comment(issue_number, body)`.
- [ ] `workspace.py`: `Workspace(Protocol)` — `ensure_worktree/remove_worktree/discover_branch`.
      `Sessions(Protocol)` — `launch/is_alive/kill`.
- [ ] `store.py`: `StateStore(Protocol)` — `load/save/touch_heartbeat/release_slot/list_running`.
- [ ] `clock.py`: `Clock(Protocol)` — `now() → float`.
- [ ] Verify: `make lint` zero errors; layering test passes (ports import nothing upward).

```bash
git commit -m "feat(genesis): ports layer (BoardReader/Writer, Workspace, Sessions, StateStore, Clock)"
```

---

### 1.8 — `adapters/store/` (filesystem state)

**Files**: `src/kanbanmate/adapters/store/fs_store.py`,
`tests/adapters/__init__.py`, `tests/adapters/test_fs_store.py`.

- [ ] Port from PoC `state.py`. Implements `StateStore`. Configurable root (default `~/.kanban/`).
      `save()` = atomic temp+`os.replace`. `touch_heartbeat()` = **no-op when state file absent**
      (§8.3 no-resurrection). Slot reservation = `open(O_EXCL)` + `flock`.
- [ ] Tests: `tmp_path` root; atomic save; touch_heartbeat no-op when absent; O_EXCL blocks concurrent.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): adapters/store filesystem state (atomic writes, flock, heartbeat)"
```

---

### 1.9 — `adapters/workspace/` (tmux + git worktree)

**Files**: `src/kanbanmate/adapters/workspace/{worktree,sessions}.py`,
`tests/adapters/test_workspace.py`.

- [ ] `worktree.py`: port from PoC `engine/worktree.py`. `shlex.quote` on all paths.
- [ ] `sessions.py`: port from PoC `engine/tmux.py`.
- [ ] Tests: unit mocks subprocess; `@pytest.mark.local_real` for real tmux+git (skipped by default).
- [ ] Verify: `make test` pass (local_real skipped).

```bash
git commit -m "feat(genesis): adapters/workspace (git worktree + tmux sessions)"
```

---

### 1.10 — `adapters/github/` (urllib GraphQL client)

**Files**: `src/kanbanmate/adapters/github/{client,_queries,_parsers,token,types}.py`,
`tests/adapters/github/__init__.py`, `tests/adapters/github/test_client.py`.

- [ ] Port from PoC `kanbanmate/github/`. **MANDATORY**: connect + read timeouts on every request.
      Inject transport for testability. Pagination = stub page-1 only (H3 in Phase 3).
- [ ] Token validation: scopes `project`+`repo` only (no `admin:org_hook`).
- [ ] Tests: fake transport returning fixture JSON; assert Ticket parsing; assert timeout args set.
- [ ] Verify: `make test` pass, `make lint` zero errors.

```bash
git commit -m "feat(genesis): adapters/github urllib client (PAT, GraphQL read+move, injected transport)"
```

---

### 1.11 — App layer: `tick` + `actions` + `wiring`

**Files**: `src/kanbanmate/app/{tick,actions,wiring}.py`,
`tests/app/__init__.py`, `tests/app/test_{tick,actions}.py`.

- [ ] `actions.py`: command pattern — `LaunchAction`, `TeardownAction`, `ResetAction`, `BlockAction`,
      each `execute(deps: Deps) → None`. `Deps` dataclass holds all injected adapters.
- [ ] `tick.py`: imperative shell (DESIGN §3.1) — `probe→snapshot→diff→decide→execute→reap+drain+heartbeat`.
      Idempotent. Per-tick watchdog timeout wraps each action.
- [ ] `wiring.py`: composition root — build adapters from config, inject into tick/actions.
- [ ] Tests: all adapters mocked; assert LaunchAction on agent-col transition; TeardownAction on Cancel;
      noop on inert.
- [ ] Verify: `make test` pass.

```bash
git commit -m "feat(genesis): app layer (tick imperative shell, command-pattern actions, wiring)"
```

---

### 1.12 — Daemon loop + minimal CLI + CI + smoke test

**Files**: `src/kanbanmate/daemon/loop.py`, `src/kanbanmate/cli/app.py`,
`tests/test_smoke.py`, `.github/workflows/pr.yml`.

- [ ] `loop.py`: blocking loop; `flock ~/.kanban/daemon.lock`; SIGTERM→finish tick+exit;
      config reload on mtime change at top of each tick. PM2-agnostic.
- [ ] `cli/app.py`: typer app; `run` → `loop.main()`; other commands stubs (Phase 2 fills).
- [ ] `test_smoke.py`: `importlib.import_module` for `kanbanmate`, `kanbanmate.core.domain`,
      `kanbanmate.core.diff`, `kanbanmate.app.tick` — assert no ImportError.
- [ ] `pr.yml`: `pip install -e ".[dev]"` → `make check` → `python -c "import kanbanmate"`.
      Trigger on PR to main + push to `feat/genesis`.

**Phase 1 gate** — run before gate commit:

1. `make lint` — zero errors
2. `make test` — all pass (`local_real`+`integration` skipped — expected)
3. `make check` — clean
4. `rg --type py "payload|n8n|HMAC|hmac" src/ tests/` — zero matches
5. `python -c "import kanbanmate"` — exits 0

```bash
git add src/kanbanmate/daemon/ src/kanbanmate/cli/ tests/test_smoke.py .github/
git commit -m "feat(genesis): daemon loop (kanban run) + CLI stub + CI workflow"
git commit --allow-empty -m "chore(genesis): phase 1 gate — bootstrap engine + polling core"
```
