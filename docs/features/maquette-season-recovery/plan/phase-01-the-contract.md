# Phase 1 — The contract

**STOP C: OPEN 1 and OPEN 5** (DESIGN § 5). Written for A and A: the card carries its season, its episode and the
engine's pointer; the journey is read per acquisition. Under OPEN 5 = B the three `QueueCard` fields are not added
(≈ 3 points less); under OPEN 1 = B the journey's parameter is untouched (≈ 2 points less).

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));s=d['components']['schemas'];print(sum(len(v) for v in d['paths'].values()),sorted(s['QueueCard']['properties']))"`
  → **75** operations; `QueueCard` **13** fields, none of `season`, `episode`, `absorbedBy`. The season-grab answer
  (`paths['/api/acquisition/follows/{followedId}/seasons/{season}/grab']['post']['responses']`) → `201` only,
  properties `season`, `absorbedCount`, `queued`, `runUid` — no `reused`. The engine:
  `grep -n "reused=True\|absorbed_by = ?" personalscraper/web/routes/acquisition_seasons.py personalscraper/acquire/_wanted_store.py`
  → the reuse answer (**169**) and the pointer column (**745**).
- **Points ≈ 8.** `QueueCard` edited — `season`, `episode`, `absorbedBy`, each nullable, each description saying the
  engine holds the column and does not serve it (SR1) — 1; the grab's `200` (reused) answer declared 2; the journey
  read keyed by the acquisition (SR4) 1; the types regenerated 1; the register regenerated, counters before and
  after 1; the report 2.
- **Readers.** `contract/types.d.ts` `QueueCard` is read by `lib/engine-queue.ts`, `arrival-slots.ts`,
  `asked-seasons.ts` — typed here, read from phase 4 on.

## Red today

None — a contract has no rule; `python3 scripts/compare-contracts.py --check` is the guard, read by OUTPUT.

## Move

1. Edit `QueueCard` and the grab's answers in `frontend/maquette/contract/openapi.json`, camelCase, every new field
   nullable (a card of a film carries no season).
2. The journey's path parameter documented as the acquisition's key (`<title>|S03`, `<title>|S03E07`), the demand
   named in its description.
3. `scripts/compare-contracts.py --check` by OUTPUT; the types regenerated.

## Mutation

None.

## Register

`docs/reference/frontend-backend-demands.md` regenerated: SR1 and SR4 appear, counters before and after.

## Oracle: states that diverge, declared by name

None — no drawing moves.

## Commit

`feat(maquette-season-recovery): the queue card carries its season, its episode and what absorbed it`
