# Phase 3 — The mocks that move

**No OPEN question remains for this phase.** The first drawing's OPEN 1 (a second media route) is dropped entirely
(held for L18); OPEN 6 = B is drawn as the handler's own read of the seed's `stoppedAt`/`stopCause`, not conditional.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.** `ls frontend/maquette/design/src/mocks/handlers | wc -l` → **14** files, none `trackers.ts` (L16's
  phase 1 creates it). `grep -cve '^[[:space:]]*$'` on `acquisition.ts` → **359**, `configuration.ts` → **120**,
  `staging.ts` → **121**, `index.ts` → **36**. The pattern for a write that MOVES the state: `sed -n
  71,112p frontend/maquette/design/src/mocks/handlers/configuration.ts` (`updateConfigurationFile` moves `raw` and
  `displayedValue`). The contract-conformance test: `frontend/maquette/design/src/mocks/contract-conformance.test.ts`
  exists.
- **Points ≈ 11.** The tracker-summary handler re-answered so its `crossSeed` counts (`active`, `failed`) are
  DERIVED from the seed's rows, summed across every torrent 2; the downloads handler re-answered so the origin
  entry's `crossSeed` array reads the seed, filtered to that torrent 2; the `fr.json`-free plumbing (≈ 20 lines new
  in a `mocks/handlers/cross-seed.ts` or folded into L16's `trackers.ts`, the opening measure decides which) 2; the
  registration in `mocks/handlers/index.ts` (2 lines) 1; `contract-conformance.test.ts` re-read over the two
  extended reads 1; the scenario dial's read (the default vs. the named off-scenarios) wired into both handlers 2;
  → 10, 11 by rounding.
- **Found (2026-09-27).** The counts are DERIVED, not seeded (DESIGN § 2.3): `active` and `failed` are computed
  from the SAME rows the downloads read answers, so R-L17-b's agreement holds by construction and a mutation that
  seeds them twice is what the rule fells. **No media route is drawn here** — it is dropped, not merely deferred.

## Red today

None — a handler has no rule; `contract-conformance.test.ts` and `check-mock-seeds.py` are the guards.

## Move

1. The tracker-summary and downloads handlers, reading the phase 2 rows and the scenario dial. The switch's write
   is the EXISTING `updateConfigurationFile`; the handler reads the settings state the write moves, so a flip moves
   every projection in the same answer.
2. Register the handler(s) in `mocks/handlers/index.ts`.

## Mutation

None.

## Register

—

## Oracle: states that diverge, declared by name

None.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`; the contract-conformance unit test (`npm --prefix
frontend/maquette/design test -- --run mocks/contract-conformance` — vitest, run under the test class of the mutex).

## Commit

`feat(maquette-l17): the cross-seed reads answer from the seed and derive their counts`
