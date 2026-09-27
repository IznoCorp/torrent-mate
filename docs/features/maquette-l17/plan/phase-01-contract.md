# Phase 1 — The reads' contract

**Every OPEN question this phase touched is ruled.** OPEN 6 = B (« stoppé » by history): the pair's row carries
`stoppedAt` and a closed `stopCause` (`switch` | `removed`) — drawn from the first opening, not conditional any
more. OPEN 1 = B holds the media route for L18: **this phase declares no `readMediaCrossSeed` and no `readAccount`
admin fact** — both are dropped from this lot's contract entirely, not merely postponed with a stale declaration
left behind.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
  → **63** operations declared before this phase; `sed -n 20,29p docs/reference/frontend-backend-demands.md` →
  « required and missing » **16** (L22 and L16 move both before L17 opens — re-take). `python3 -c "import
  json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([p for p in d['paths'] if any(x in
  p.lower() for x in ('cross','tracker','seed'))])"` → `[]`: **no route names the cross-seed or a tracker on this
  head**; L16's phase 1 declares the tracker summary read and the downloads read, so on the day this phase opens
  both EXIST and this phase EXTENDS them. `grep -c 'x-unseeded' frontend/maquette/contract/openapi.json` → **33**:
  the provenance marker every new operation carries. `personalscraper/acquire/cross_seed.py:220-260` → the engine
  stops at the FIRST verified injection though its search walks every tracker (DESIGN fact 16, F26) — demand B is
  worded for an attempt per ELIGIBLE, switched-on tracker, not the engine's own current behaviour.
- **Points ≈ 13.** The summary read edited (a `crossSeed` sub-object: `enabled`, `engineEnabled`, `active`,
  `failed`, `lastInjectedAt`) 1; the downloads read edited (a `crossSeed` array on the origin entry: `tracker`,
  `state` — six values — `reason`, `at`, `stoppedAt`, `stopCause`, `excluded`, `searching`) 2; the schemas — the
  six-word state enum, the reason enum of twelve codes plus the reserved upload/creation-failure slot (§ 2.2), the
  array's row shape — ≈ 55 lines new 5½; the two `x-unseeded` sentences (≈ 4 lines edited) 1; the register
  regenerated, its counters read before and after 1; demand B's own description worded for every eligible tracker
  (fact 16), not only the one the engine tried (≈ 6 lines) 1½; the drop of the media route and the `readAccount`
  admin fact declared by the FIRST drawing — nothing to remove from the contract itself (they were never filed) but
  the report SAYS so 1.
- **Found (2026-09-27).** The reason enum is CLOSED and carries twelve codes plus one reserved slot for a future
  upload/tracker-side-creation failure (round 8 Q18 = B); none is a tracker policy (DESIGN fact 3). The identity
  F60 asked for is ALREADY answered: L16's `AcquisitionDownload` carries `info_hash` per entry (fact 17) — this
  phase adds no new identity field for it. `CrossSeedInjected.source_tracker` names the TARGET tracker (fact 2): the
  contract's field is `tracker`, and the difference is written in the demand's `description`, not hidden.

## Red today

None — a contract has no rule of its own. `scripts/compare-contracts.py --check` is the guard and it is read by
hand.

## Move

1. The contract first (D7): declare demands A, B (both extensions of L16's OWN reads) and the schemas in
   `frontend/maquette/contract/openapi.json`, each new or extended field carrying `x-unseeded` (« invented: no
   fixture exists for the cross-seed, DESIGN § 2.3 »). Demand D (the obligations read's `crossSeedOf`) is NOT filed
   here — it is filed in phase 8, where it is drawn. Demands E and K are filed where THEY are drawn (14, 11).
2. `python3 scripts/compare-contracts.py --write`, then `--check`, then `npm --prefix frontend/maquette/design run
   generate-contract-types`. **Read the counters and put them in the report, before and after.**

## Mutation

None.

## Register

Demands A and B of DESIGN § 6.2 filed by the regenerated `docs/reference/frontend-backend-demands.md`; nothing
else is edited.

## Oracle: states that diverge, declared by name

None — a contract moves no surface.

## Gate

Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py` (its
`provenance` arm refuses an operation carrying neither `x-seeded-from` nor `x-unseeded`).

## Commit

`feat(maquette-l17): the cross-seed reads are declared, invented and marked`
