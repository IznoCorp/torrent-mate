# Implementation Progress — sieve

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Filtre status ticket sur liste des issues — add a client-side status filter to the KanbanMateUI Issues list, narrowing the flat ticket list to a single board column (status) (minor)
**Version bump**: 0.22.5 → 0.23.0
**Branch**: feat/sieve
**PR merge**: manual
**PR**: _(created after last phase)_
**Track**: lite (skiff fast-track — no full DESIGN.md/plan dir)
**Design**: docs/features/sieve/SCOPE.md
**Master plan**: docs/features/sieve/SCOPE.md § "Checklist plan" (lite-lane — the checklist serves as the plan)

## Phases

_(lite-lane — the SCOPE.md "Checklist plan" (6 steps) is the implementation plan; no separate /implement:plan phase dir)_

| # | Step | Status |
| --- | --- | --- |
| 1 | `web/src/panels/IssuesPanel.jsx` — add `Select` to the design-system destructure (`:13-14`) | [ ] |
| 2 | Same file — add `statusFilter` state (`""` = all) near the other list state (`:27-29`) | [ ] |
| 3 | Same file — carry `column_key` through the `issues` memo (`:53-64`) for a key-based predicate | [ ] |
| 4 | Same file — derive filter options (board-order) + filtered list; render filtered array in the list `.map` (`:372`) and feed the filtered length to `issues.count` (`:347`) | [ ] |
| 5 | Same file — render the `Select` in the LIST toolbar (`:333-349`), guarded on `board` loaded | [ ] |
| 6 | i18n — add `issues.filter_all` + `issues.filter_tip` to **both** `web/src/i18n/en.yaml` and `fr.yaml` | [ ] |

## Review cycles

_(filled by implement:pr-review — max 2 cycles for the lite lane)_

## Next action

Run `/implement:plan` (or, on the lite lane, proceed straight to `/implement:phase`) to execute the SCOPE.md checklist.
