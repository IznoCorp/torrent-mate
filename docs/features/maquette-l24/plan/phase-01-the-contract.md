# Phase 1 — The contract

**STOP C: OPEN 3** — demand C (`readScrapingActivity`) is declared only under reading B. Demands A and B carry none.

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
  → **68** operations; `[p for p in d['paths'] if 'enqueue' in p or 'completeness' in p or 'activity' in p]` →
  **`[]`**. The engine declares all three (`grep -n "enqueue\"\|/completeness\"\|decisions/activity\"" frontend/src/api/schema.d.ts`
  → lines 163, 1173, 2131).
- **Points ≈ 9 / 7.** `enqueueForResolution` declared new 2; `readFollowCompleteness` declared new 2, its answer
  shape copied from the engine's `CompletenessResponse` (seasons, `source`, `provider_catalog_empty`); reading B of
  OPEN 3: `readScrapingActivity` declared new 2; the register regenerated, its counters read before and after 1;
  the types regenerated 1; the report 1.
- **Readers.** None yet — no feature reads an operation this phase declares.

## Red today

None — a contract has no rule; `python3 scripts/compare-contracts.py --check` is the guard, read by OUTPUT.

## Move

1. Declare the operations in `frontend/maquette/contract/openapi.json`, each shape the engine's own, renamed to the
   contract's camelCase; nothing invented (D7).
2. `python3 scripts/compare-contracts.py --write`, then `--check`; `npm --prefix frontend/maquette/design run
   generate-contract-types`. Counters before and after into the report.

## Mutation

None.

## Register

Demands A, B (and C under OPEN 3 B) filed by the regenerated `docs/reference/frontend-backend-demands.md`; demand D
needs no shape change (DESIGN § 2).

## Oracle: states that diverge, declared by name

None — a contract moves no surface.

## Commit

`feat(maquette-l24): the enqueue and completeness operations are declared`
