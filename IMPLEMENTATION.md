# Implementation Progress — health-field (per-card "Health" GitHub single-select field)

> For Claude: read this file at session start. Current feature tracker.

**Feature**: health-field — a per-card "Health" single-select FIELD carrying the operator's own
vocabulary (`INACTIVE / BLOCKED / WAITING / ACTIVE / COMPLETE`) as native GitHub chips, maintained
by the daemon ON CHANGE (a workaround for GitHub's fixed, un-renameable status-update pill enum)
**Version bump**: minor (Y+1)
**Branch**: `feat/health-field`
**PR merge**: manual (human-only)
**PR**: _(created after the gate)_
**Design**: `docs/features/health-field/DESIGN.md`
**Master plan**: _(single feature branch — sub-phases below)_

## Phases

| Phase | Scope | Status | Commit |
|-------|-------|--------|--------|
| 1 | core + ports + types: pure `core/health.compute_health` + option specs; `HealthField` value object; `ProjectHealthReporter` port + `StateStore` Protocol health methods | DONE | `feat(health-field): per-card Health single-select field maintained by the daemon` |
| 2 | GraphQL surface: `_queries.create_project_field_single_select` (the only new query) + `_parsers.parse_health_field` / `parse_created_single_select_field` | DONE | (same commit) |
| 3 | client: `_health.ensure_health_field` helper + `GithubClient.ensure_health_field` / `set_item_health` (reuses `move_item`); cached `_health_field` | DONE | (same commit) |
| 4 | store mixin: `fs_health_state.HealthStateMixin` (field id/options + per-card last-written + rebind clear), mixed into `FsStateStore` (`health/` dirs) | DONE | (same commit) |
| 5 | app step + tick wire: `app/health_reporter.apply_health` (on-change, fail-soft, rebind guard) + tick Step 4e; `health_reporter` on `Deps` + `wiring`; `_NullStatusReporter` moved to `status_reporter.py` (actions.py LOC headroom) | DONE | (same commit) |
| 6 | init surface: best-effort `ensure_health_field` after `ensure_columns` (non-fatal) | DONE | (same commit) |
| 7 | tests + docs: pure mapping, parsers/queries, client ensure/set, store mixin, app on-change/fail-soft/multi-root/rebind, tick wiring; DESIGN doc + this row | DONE | (same commit) |

## Behaviour deltas (gate requirement)

- **New per-card "Health" single-select field.** The daemon find-or-creates a custom "Health" field
  (5 options, operator colours: ACTIVE=GREEN, WAITING=YELLOW, BLOCKED=RED, INACTIVE=GRAY,
  COMPLETE=PURPLE) and sets each card's Health every tick — but ONLY when the computed value CHANGED
  (the on-change discipline; per-card last-written value persisted under `<root>/health/last/`).
- **Pure per-card mapping** (`core/health.compute_health`): WAITING agent → WAITING; RUNNING agent →
  ACTIVE; no agent + Blocked column → BLOCKED; no agent + Done column → COMPLETE; otherwise INACTIVE.
  First-match-wins; the Blocked/Done column keys come from `TickConfig` (not hardcoded).
- **Idempotent provisioning, zero manual step.** First tick post-merge/restart ensures the field
  (creates it once); the field id + option ids are persisted in the STORE (board-wide,
  per-kanban-root) so every later tick is a cache hit. `kanban init` also best-effort ensures it.
- **Fail-soft.** The whole Health step + each per-card write swallow every exception (logged WARNING)
  — it NEVER raises into the tick or blocks a launch (mirrors `report_status`).
- **Multi-root.** Markers live under each daemon's own `<root>/health/`; a project-rebind guard drops
  stale ids when the registry is re-pointed. Both `~/.kanban` and `~/.kanban-km` get their own field.
- **GraphQL reuse.** Only `createProjectV2Field` is new; the read reuses `status_option_map`, the SET
  reuses `move_item` (`updateProjectV2ItemFieldValue`), and the reconcile reuses
  `update_status_field_options` (a generic single-select REPLACE preserving option ids).

See `docs/features/health-field/DESIGN.md` for the full delta.

## Next action

**Phase gate green** (`make check`: ruff + ruff format --check + mypy + 1619 tests + size guard, exit
0). Awaiting human review + merge (merge is human-only). The operator redeploys the daemons after
merge; the "Health" field then auto-appears on the next tick of each daemon (zero manual step).

---

# Follow-up — firm-exit (reaper clean-termination robustness)

> Focused engine bugfix on branch `fix/end-session-robust` (SemVer **patch / Z+1**). A separate,
> standalone fix from the health-field feature above — extends the clean-termination (#1) reaper
> done-exit so a finished brainstorm/plan agent is reliably terminated. DESIGN delta:
> `docs/features/clean-termination/DESIGN.md` §8.x (firm-exit follow-up).

## Phases

| Phase | Scope | Status | Commit |
|-------|-------|--------|--------|
| 1 | adapter + port: robust `TmuxSessions.end_session` (Escape→C-u→C-d→C-d, sleeper-seam delays, BSpace fallback, no kill-session) + new `Sessions.kill_repl_process` (pane-PID → claude child → SIGTERM, fail-soft) + its `Sessions` Protocol method | DONE | `fix(reaper): robust end_session + kill-escalation for finished agents` |
| 2 | store: `AgentBreadcrumbsMixin` `end_attempts/` counter (`get_end_attempts`/`bump_end_attempt`/`clear_end_attempts`) + `StateStore` Protocol stubs; `FsStateStore.__init__` dir + `purge_ticket` unlink (both paths) | DONE | (same commit) |
| 3 | reaper: `MAX_END_ATTEMPTS`=3; `_end_done_session` bounded-retry-then-kill escalation (dispatch+bump < MAX, keep breadcrumb; kill_repl_process + clear at MAX); `_reset_stale_end_attempts` defensive not-done reset; Approach A intact | DONE | (same commit) |
| 4 | prompt tweak: shared `_CLEAN_STOP` appended to all 8 `kanban-done` launch prompts | DONE | (same commit) |
| 5 | tests + DESIGN delta + this row: robust end_session order + delays; kill_repl_process SIGTERM-not-session + 4 fail-soft paths; counter mixin (8); reaper escalation/retry/reset (7); clean-stop in all 8 prompts | DONE | (same commit) |

## Behaviour deltas (gate requirement)

- **Robust `end_session`.** Escape (close the slash-command menu) → C-u (clear the box) → C-d → C-d
  (the second confirms exit past "N shells still running"), with small `sleeper`-seam delays
  (0.3/0.3/0.5s, worst-case 1.1s < 1.5s budget). Fixes the helm #5 NO-OP where a leftover
  `/implement:plan` + background shells blocked the old two-key `C-c`/`C-d`. Never `kill-session`.
- **`kill_repl_process` escalation primitive.** SIGTERMs the `claude` REPL child (resolved via
  `tmux list-panes` pane-PID → `pgrep`/`ps` child), NOT the session/shell, so the surviving shell
  still runs `; kanban-session-end`. Fail-soft on every resolution/kill error.
- **Bounded-retry-then-kill (REVERSES the SINGLE-SHOT contract).** The reaper re-dispatches
  `end_session` each tick (KEEPING the done breadcrumb + bumping a persisted `end_attempts/<issue>`
  counter) until the REPL exits or `MAX_END_ATTEMPTS`=3 is hit → then it kills the REPL process and
  clears both markers. A failed dispatch does not bump/clear (retries the same attempt). Counter reset
  on `purge_ticket` (both paths) + a defensive not-done sweep reset.
- **Approach A preserved.** Only ever acts on a done + IDLE + ALIVE session; a WORKING/not-done/dead
  session is never exited or REPL-killed by this branch.
- **`_CLEAN_STOP` prompt instruction.** Belt-and-suspenders on all 8 `kanban-done` prompts: end the
  turn immediately after `kanban-done`, no next-stage command, no trailing background shells.

See `docs/features/clean-termination/DESIGN.md` §8.x for the full delta.

## Next action

**Phase gate green** (`make check` exit 0; `python -c "import kanbanmate"` OK). Awaiting human review +
merge (merge is human-only). The operator redeploys the daemons after merge; finished brainstorm/plan
agents then terminate reliably (robust keystrokes + REPL-kill escalation).
