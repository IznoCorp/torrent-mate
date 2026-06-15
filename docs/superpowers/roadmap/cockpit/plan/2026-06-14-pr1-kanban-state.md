# PR1 — `kanban state` (read-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline) or
> subagent-driven-development. Steps use `- [ ]` checkboxes.

**Goal:** Add a read-only `kanban state [--json]` command: a unified board + agents + queue + recent
events + health-pill + daemon-health view, for operators (human) and agents/scripts (`--json`).

**Architecture:** Pure cli-layer extension of the existing `cli/status.py` read model. NO core/app
changes, NO daemon changes, NO writes → sidesteps the `core→cli` layering blocker (aggregation already
lives in cli, which may import core/app). Health pill = read the `status/last_status` marker (the
daemon's last-computed enum), so no recompute / no network beyond the board snapshot `build_status`
already takes.

**Tech Stack:** Python 3.12, typer CLI, pytest. Reuses `cli/status.build_status` / `render_status` /
`read_queued` / `read_daemon_health` / `read_degraded` and `store.read_status_events` /
`store.get_status_last_enum`.

---

## File Structure

- Create `src/kanbanmate/cli/state.py` — `StateReport`, `build_state`, `render_state_human`,
  `render_state_json`, `state()` imperative wrapper.
- Modify `src/kanbanmate/cli/app.py` — add the `state` command (`--root`, `--json`).
- Modify `plugin/skills/kanban/SKILL.md` — add the `kanban state` row.
- Create `tests/cli/test_state.py` — aggregation + JSON shape + human render tests.

### Task 1: `cli/state.py` read model + renderers

**Files:** Create `src/kanbanmate/cli/state.py`; Test `tests/cli/test_state.py`.

- [ ] **Step 1 — failing tests** (`tests/cli/test_state.py`): with in-memory fakes (a board_reader
      returning a snapshot of 3 tickets across 2 columns; a store with one RUNNING ticket, a queued
      ticket, an events ring `[{ts,kind,issue,detail}]`, and `last_status="AT_RISK"`):
  - `build_state(...)` returns a `StateReport` whose `.status` is the `build_status` report, whose
    `.events` equals the store ring (tuple), and whose `.health == "AT_RISK"`.
  - `render_state_json(report)` is valid JSON with keys `health, paused, board{columns,total},
agents[], queue[], events[] (newest-first), daemon, degraded`; `health=="AT_RISK"`; `board.total`
    == number of snapshot tickets; first event is the newest by `ts`.
  - `render_state_human(report)` contains the board render, a `Health` line with the enum, and a
    `Recent events` section listing the events newest-first.
  - health defaults: with `last_status=None`, json `health` is `null` and human shows `—`.
- [ ] **Step 2 — run, verify fail** (`pytest tests/cli/test_state.py -q` → ImportError/fail).
- [ ] **Step 3 — implement `cli/state.py`:**
  - `@dataclass(frozen=True) class StateReport: status: StatusReport; events: tuple[dict[str,object],
...] = (); health: str | None = None`.
  - `build_state(board_reader, store, *, paused=False, degraded="", daemon=None, queued=None,
now=None) -> StateReport`: `status = build_status(board_reader, store, paused=paused,
degraded=degraded, daemon=daemon, queued=queued, now=now)`; `events = tuple(store.read_status_
events())`; `health = store.get_status_last_enum()`; return `StateReport(status, events, health)`.
  - `render_state_json(report) -> str`: `json.dumps({...}, indent=2)` with the keys above; agents
    projected to `{issue_number, session_id, status, column_key, heartbeat_age, attach_hint}`; queue
    to `{issue_number, stage, age}`; events `list(reversed(report.events))` (ring is oldest-first);
    daemon to its dataclass fields or `None`.
  - `render_state_human(report) -> str`: `render_status(report.status)` + `"\nHealth: " +
(report.health or "—")` + a `Recent events` block (newest-first, `HH:MM <kind> #<issue>
<detail>`); reuse a local `time.localtime` HH:MM formatter.
  - `state(board_reader, store, *, root, ttl, now=None, as_json=False) -> str`: imperative shell
    mirroring `status()` — read `paused`/`degraded`/`daemon`/`queued` from `root`, `build_state`,
    then `render_state_json` if `as_json` else `render_state_human`.
- [ ] **Step 4 — run, verify pass** (`pytest tests/cli/test_state.py -q`).
- [ ] **Step 5 — commit** (`feat(cockpit): kanban state read-only command (PR1)`).

### Task 2: wire the `state` CLI command

**Files:** Modify `src/kanbanmate/cli/app.py`.

- [ ] **Step 1** — add `from kanbanmate.cli import state as state_cmd` with the other cli imports.
- [ ] **Step 2** — add command mirroring `status` with a `--json/-j` bool option:
  ```python
  @app.command()
  def state(
      root: Path = typer.Option(_DEFAULT_ROOT, "--root", help="Kanban runtime root (default ~/.kanban)."),
      json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
  ) -> None:
      """Unified read-only board + agents + queue + events + health-pill view (read-only)."""
      deps = build_deps(_wiring_for(root))
      typer.echo(state_cmd.state(deps.board_reader, deps.store, root=root.expanduser(),
                                 ttl=doctor_mod.HEARTBEAT_TTL_FLOOR, as_json=json_out))
  ```
- [ ] **Step 3** — `pytest tests/cli -q` (no regression); manual `kanban state --json` smoke deferred
      to gate.

### Task 3: skill surface

**Files:** Modify `plugin/skills/kanban/SKILL.md`.

- [ ] **Step 1** — add a row to the commands table:
      `| kanban state [--json] | Unified board + agents + queue + events + health view (read-only) |`.

### Task 4: gate + commit

- [ ] `make check` (lint + test + module-size + layering) green.
- [ ] residual-import / `python -c "import kanbanmate"` smoke.
- [ ] commit any wiring/skill changes.

## Self-Review

- **Spec coverage (§6 of the design):** `kanban state` ✓, JSON + human ✓, board+agents+queue+events+
  pill ✓, no writes ✓, layering (all cli) ✓, health via `last_status` marker ✓.
- **Placeholders:** none — signatures + shapes are concrete.
- **Type consistency:** `StateReport.status: StatusReport` (from cli/status.py); `events` are the raw
  ring dicts; `health: str|None` matches `get_status_last_enum`.
- **Deferred to PR2/PR3:** all writes (intents, move, ticket, pill), nudge, daemon changes.
