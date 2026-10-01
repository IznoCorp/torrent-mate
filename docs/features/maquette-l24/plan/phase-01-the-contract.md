# Phase 1 — The contract

**No STOP C.** Demand C (`decisions/activity`) is not declared — OPEN 3 = A (2026-09-29).

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
  → **68** operations; `[p for p in d['paths'] if 'enqueue' in p or 'completeness' in p]` → **`[]`**; the engine
  declares both (`grep -n "enqueue\"\|/completeness\"" frontend/src/api/schema.d.ts` → lines **163, 2131**).
  `d['components']['schemas']['SettledDecision']['properties']` → `folder, kind, title, reason, state, when, year,
  choice` — no `id`, no candidates' count, no author; the engine's `DecisionListItem` has `id` and
  `candidates_count` (`frontend/src/api/schema.d.ts`).
- **Points ≈ 8.** `enqueueForResolution` declared new 2; `readFollowCompleteness` declared new 2, its answer shape
  copied from the engine's `CompletenessResponse` (seasons, `source`, `provider_catalog_empty`); `SettledDecision`
  edited — `id`, `candidatesCount`, `settledBy: operator | engine` — 1; the register regenerated, its counters read
  before and after 1; the types regenerated 1; the report 1.
- **Readers.** `features/acquisition/decision-queries.ts` (55 lines) reads `SettledDecision` — the new fields are
  optional to it until phase 5.

## Red today

None — a contract has no rule; `python3 scripts/compare-contracts.py --check` is the guard, read by OUTPUT.

## Move

1. Declare the two operations in `frontend/maquette/contract/openapi.json`, each shape the engine's own, renamed to
   the contract's camelCase; edit `SettledDecision` (DESIGN § 2, demand D) — an identification the engine made alone
   is a settled row with `settledBy: engine`, the divergence the register files.
2. `python3 scripts/compare-contracts.py --write`, then `--check`; `npm --prefix frontend/maquette/design run
   generate-contract-types`. Counters before and after into the report.


## Register

Demands A, B and D filed by the regenerated `docs/reference/frontend-backend-demands.md`; C recorded as served
differently (DESIGN § 1.3).


## Commit

`feat(maquette-l24): the enqueue and completeness operations, and a settled decision's id, count and author`
