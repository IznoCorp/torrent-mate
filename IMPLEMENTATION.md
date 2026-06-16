# Implementation Progress — clean-termination (engine bug fix)

> For Claude: read this file at session start. Current feature tracker.

**Feature**: clean-termination — Option-1 clean agent termination (#1) + status-update English-only (#3)
**Version bump**: bugfix (Z+1)
**Branch**: `fix/clean-termination`
**PR merge**: manual (human-only)
**PR**: _(created after the gate)_
**Design**: `docs/features/clean-termination/DESIGN.md`
**Master plan**: _(single-pass engine fix — no multi-phase plan)_

## Phases

| Phase | Scope | Status | Commits |
|-------|-------|--------|---------|
| 1 | #1 Option-1 clean termination: `kanban-done` helper + done breadcrumb (store/mixin) + `Sessions.end_session` + reaper done-exit branch + `KANBAN_ROOT` injection + prompt terminal step | DONE | `fix(clean-termination): Option-1 clean agent termination` |
| 2 | #3 status-update English-only + corrected GitHub enum-mapping docstring | DONE | `fix(clean-termination): status-update body English-only + enum docstring` |

## Behaviour deltas (gate requirement)

- **#1** — The agent's terminal step is `kanban-done <issue>` (drops a persisted `done/<issue>`
  breadcrumb). The reaper cleanly EXITS an ALIVE + IDLE + done session via `Sessions.end_session`
  (C-c/C-d, never `kill`) so the trailing `; kanban-session-end` fires (teardown). Approach A
  unchanged for not-done / working / dead sessions. `purge_ticket` purges the done breadcrumb.
  `KANBAN_ROOT` is injected on the launched command for non-default daemons so the helpers target
  the launching daemon's root (km-worktree-helper-root fix).
- **#3** — The rolling status-update body renders ENGLISH only; the stale enum-mapping docstring is
  corrected (ACTIVE→ON_TRACK / WAITING→AT_RISK / BLOCKED→OFF_TRACK).

See `docs/features/clean-termination/DESIGN.md` for the full delta.

## Next action

**Phase gate green** (lint + 1561 tests + size guard). Awaiting human review + merge (merge is
human-only). The operator redeploys the daemons after merge.
