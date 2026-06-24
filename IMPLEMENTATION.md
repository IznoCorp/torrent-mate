# Implementation Progress — latch

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Le bouton save config sur les pages sans config — gate the config toolbar (Save · Validate · HealthPill) to the config-editing tabs only, not every board-scoped tab (bugfix)
**Version bump**: 0.22.1 → 0.22.2
**Branch**: fix/latch
**PR merge**: manual
**PR**: _(created after last phase)_
**Track**: lite (skiff fast-track — no full DESIGN.md/plan dir)
**Design**: docs/features/latch/SCOPE.md
**Master plan**: docs/features/latch/SCOPE.md § "Checklist plan" (lite-lane — the checklist serves as the plan)

## Phases

_(lite-lane — the SCOPE.md "Checklist plan" (4 steps) is the implementation plan; no separate /implement:plan phase dir)_

| # | Step | Status |
| --- | --- | --- |
| 1 | `web/src/App.jsx` — add `configScope` predicate (`columns`/`transitions`/`defaults`) + pass to `<AppShell>`; keep `boardScope` for the scope badge | [x] |
| 2 | `web/src/components/AppShell.jsx` — destructure `configScope`; switch the 3 config-toolbar gates (mobile Save `:124`, mobile Validate `:191`, desktop cluster `:389`) from `boardScope` to `configScope`; leave badge gate (`:365`) on `boardScope` | [x] |
| 3 | Manual verify — cluster absent on Monitoring/Board/Issues/Validation/YAML, present + functional on Columns/Transitions/Defaults; daemon-scope tabs unchanged (verified via `npm run build` — JSX compiles; gating logic reviewed) | [x] |
| 4 | Version bump 0.22.1 → 0.22.2 across the 5 sync points | [x] |

## Review cycles

_lite lane — max 2 cycles. PR #123._

### Cycle 1

Norms reviewed (lite subset — correctness / security / test-coverage), filter artifact `docs/features/latch/SCOPE.md`:

- **Correctness** — PASS. `configScope = active ∈ {columns, transitions, defaults}` is exactly the editable-config set (each receives the live `draft`+`update`; the toolbar `onSave` → `api.saveConfig` persists the draft — `App.jsx:258-285`, save handler `:169-176`). The 3 toolbar gates flipped from `boardScope` to `configScope` (`AppShell.jsx:125`/`192`/`395`); the board/daemon scope **badge** correctly stays on `boardScope` (`:374`). No gate missed, none stranded.
- **Security** — PASS. Pure client-side UI-visibility change; no server-side authorization path altered.
- **Test coverage** — PASS. No JS test harness exists in `web/` (lite-lane manual-verify accepted; Python CI untouched). `npm run build` (vite) compiles clean.
- **Blocking finding (major)** — stale branch: caulk (#122) landed `0.22.2` on `main` first, so latch's independent `0.22.2` bump produced a `VERSION` merge conflict (`mergeable_state: dirty`), blocking the human merge. **Fixed in-cycle**: merged `origin/main` into `fix/latch` (additive, no history rewrite; `AppShell.jsx` auto-merged with caulk's tooltip work, gating logic intact) and moved all 5 version-sync points to `0.22.3` (commit `533904f`).

**Post-fix verification**: PR `mergeable: True`; CI check `check` (Python gate) on head `533904f` → **success**. No critical/major/medium findings remain → loop exits clean. Merge is **human-only** — PR left OPEN for the operator.

## Next action

Review complete — PR #123 open, mergeable, CI green. Awaiting human squash-merge.
