# Phase 3 — The mocks that move

**Reads OPEN 1 (the media block's gate) and OPEN 6 (what « stoppé » means).** OPEN 1 = B: the media route (2 points and ≈ 20 lines, 2) is not
written and the phase is **9**. OPEN 6 = A (by cause): the handler derives « stoppé » from the switch and « tracker sans cross-seed » from
the row's eligibility, keeping no past; OPEN 6 = B (by history): the handler reads the row's stop date, ≈ +6 lines, +1.

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `ls frontend/maquette/design/src/mocks/handlers | wc -l` → **14** files, none `trackers.ts` (L16's phase 1 creates it).
  `grep -cve '^[[:space:]]*$'` on `acquisition.ts` → **359**, `configuration.ts` → **120**, `staging.ts` → **121**, `index.ts` → **36**;
  `mocks/stream.ts` → **399 of 400** (no line of this phase goes there). The pattern for a write that MOVES the state:
  `sed -n 71,112p frontend/maquette/design/src/mocks/handlers/configuration.ts` (`updateConfigurationFile` moves `raw` and `displayedValue`).
  The contract-conformance test: `frontend/maquette/design/src/mocks/contract-conformance.test.ts` exists.
- **Points ≈ 13.** The handler file `mocks/handlers/cross-seed.ts` ≈ 60 lines new 6 (by SUBJECT, the `staging.ts` / `pipeline.ts` precedent; L16's
  `trackers.ts` size decides at the opening whether it would fit under 400 — if it does not, this is the file); `readTrackerCrossSeed` new route 2;
  `readMediaCrossSeed` new route 2 (OPEN 1, A); the summary handler re-answered so its `crossSeed` counts are DERIVED from the section's rows
  1; the registration in `mocks/handlers/index.ts` (2 lines) 1; `contract-conformance.test.ts` re-read over the new routes 1.
- **Found (2026-09-27).** The counts are DERIVED, not seeded (DESIGN § 2.3): `seeding` and `refused` are computed from the SAME rows the section
  answers, so R-L17-b's agreement holds by construction and a mutation that seeds them twice is what the rule fells. **The answer for an
  identity that is not the administrator's is phase 11's**, not written here.

## Red today

None — a handler has no rule; `contract-conformance.test.ts` and `check-mock-seeds.py` are the guards.

## Move

1. `mocks/handlers/cross-seed.ts`: the two routes and the summary's derivation, reading the phase 2 rows. The switch's write is the EXISTING
   `updateConfigurationFile`; the handler reads the settings state the write moves, so a flip moves every projection in the same answer.
2. Register the handler in `mocks/handlers/index.ts`.

## Mutation

None.

## Register

—

## Oracle: states that diverge, declared by name

None.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`; the contract-conformance unit test (`npm --prefix frontend/maquette/design test -- --run
mocks/contract-conformance` — vitest, run under the test class of the mutex).

## Commit

`feat(maquette-l17): the cross-seed reads answer from the seed and derive their counts`
