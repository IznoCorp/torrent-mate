# Phase 1 — The reads' contract

**Ruled.** OPEN 6 = B (« stoppé » by history): the pair's row carries `stoppedAt` and a closed `stopCause` (`switch`
| `removed`). OPEN 1 = B holds the media route for L18: **this phase declares no `readMediaCrossSeed` and no
`readAccount` admin fact** — both are out of this lot's contract, and the report says so.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
  → **63** operations; `sed -n 20,29p docs/reference/frontend-backend-demands.md` → « required and missing » **16**
  (L22 and L16 move both before L17 opens — re-take). `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([p for p in d['paths'] if any(x in p.lower() for x in ('cross','tracker','seed'))])"`
  → `[]` on this head; L16's phase 1 declares the tracker summary read and the downloads read, so this phase EXTENDS them.
  `grep -c 'x-unseeded' frontend/maquette/contract/openapi.json` → **33**. `personalscraper/acquire/cross_seed.py:220-260`
  → the engine stops at the FIRST verified injection (DESIGN fact 16, F26).
- **Points ≈ 13.** Summary read edited 1; downloads read edited 2; the schemas ≈ 55 lines new 5½; the two
  `x-unseeded` sentences 1; the register regenerated, counters before and after 1; demand B worded for every
  eligible tracker 1½; the dropped media route and `readAccount` fact said in the report 1.

## The contract, as the next phases consume it

- **Summary read** (demand A): a `crossSeed` sub-object — `enabled`, `engineEnabled`, `active`, `failed`,
  `lastInjectedAt`.
- **Downloads read** (demand B): a `crossSeed` array on the origin entry, one row per other eligible tracker —
  `tracker`, `state` (the six-word enum), `reason`, `at`, `stoppedAt`, `stopCause`, `excluded`, `searching`.
- **Reason enum**: CLOSED, twelve codes plus one reserved upload/tracker-side-creation-failure slot (round 8 Q18 = B,
  DESIGN § 2.2); none is a tracker policy (DESIGN fact 3).
- **Identity** (F60): L16's `AcquisitionDownload` already carries `info_hash` per entry (fact 17) — no new field.
- **Naming**: `CrossSeedInjected.source_tracker` names the TARGET tracker (fact 2); the contract's field is
  `tracker`, and the difference is written in the demand's `description`.
- Demand B's `description` asks for an attempt per ELIGIBLE, switched-on tracker, not the engine's current
  first-only behaviour.

## ~~Red today · Mutation · Oracle~~

None — a contract has no rule and moves no surface. `scripts/compare-contracts.py --check` is the guard, read by hand.

## Move

1. Declare demands A, B and the schemas in `frontend/maquette/contract/openapi.json`, each new or extended field
   carrying `x-unseeded` (« invented: no fixture exists for the cross-seed, DESIGN § 2.3 »). Demand D is filed in
   phase 8, E in 14, K in 11 — where each is drawn.
2. `python3 scripts/compare-contracts.py --write`, then `--check`, then `npm --prefix frontend/maquette/design run
   generate-contract-types`. **The counters go in the report, before and after.**

## Register

Demands A and B of DESIGN § 6.2, filed by the regenerated `docs/reference/frontend-backend-demands.md`.

## Gate — done when

~~Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py` (its~~
`provenance` arm refuses an operation carrying neither `x-seeded-from` nor `x-unseeded`).

## Commit

`feat(maquette-l17): the cross-seed reads are declared, invented and marked`
