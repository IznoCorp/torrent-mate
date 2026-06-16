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
