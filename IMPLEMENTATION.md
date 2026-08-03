# Implementation Progress — rm-lacale

> For Claude: read this file at session start. Current feature tracker.

**Feature**: [#156] Complete removal of the LaCale tracker (+ Torr9 zero-remnant proof)
**Type**: refactor
**Version bump**: 0.76.0 → 0.77.0 (minor)
**Branch**: refactor/rm-lacale
**Ticket**: #156 — claimed (heartbeat live)
**PR merge**: auto — standing operator contract: adversarial review(s) + tests before merge.
**PR**: _(created after last phase)_
**Design**: docs/features/rm-lacale/DESIGN.md
**Master plan**: docs/features/rm-lacale/plan/INDEX.md

## Non-negotiable invariants (DESIGN D1-D10, frozen)

- FULL removal (operator scope) — no deprecation shims. Historic DB rows keep
  `source_tracker="lacale"` untouched and READABLE (no data migration, D2).
- Tests are REWRITTEN onto live trackers, never deleted wholesale (D9) — coverage
  must not shrink silently.
- Ranking-preview samples rewritten on live trackers with same shapes (D4) ⇒
  `make openapi` + commit regenerated files.
- Final gate = zero-hit greps (lacale D10, torr9 D8) as executable ACCEPTANCE criteria.
- Live-config cleanup is POST-MERGE (D6).

## Phases

| #   | Phase                                          | File                                   | Status |
| --- | ---------------------------------------------- | -------------------------------------- | ------ |
| 1   | Backend removal + test rewrites + D2 regression | phase-01-backend-removal.md            | [x]    |
| 2   | Web + frontend + config + docs                  | phase-02-web-frontend-config-docs.md   | [ ]    |
| 3   | ACCEPTANCE + full gate                          | phase-03-acceptance-full-gate.md       | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to execute phase 2 (web + frontend + config + docs).
