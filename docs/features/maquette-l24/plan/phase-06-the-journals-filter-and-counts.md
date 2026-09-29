# Phase 6 — The journal's filter and counts (S1)

**STOP C: OPEN 1**, as phase 5.

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `grep -n "parameter: \"tab\"" frontend/maquette/design/src/lib/addresses.ts` → the `DIALS` table at
  lines **134–140**, five dials; one more is one line (396 → 397 with phase 5's).
- **Points ≈ 13.** R-L24-a 3; the `state` dial ⅕; the filter row with its four counts, derived from the one read
  (≈ 30 lines new) 3; the entry « Tout voir » under « Réglées récemment » (≈ 4 lines edited) 1; `fr.json` 1; states
  `decisions-filtered`, `decisions-empty`, `decisions-loading`, `decisions-error` 4; the report ¾.
- **Readers.** R69 (`harness/url_state.py`) reads every dial: the new one joins its list, re-aimed out loud.

## Red today

R-L24-a over `decisions-filtered`: no filter is drawn — `0 filter(s)`.

## Move

1. The filter is a dial (`?state=`): changing it REPLACES (§ 16 rule 1, a setting never enters the stack).
2. Counts are one derivation of the one read; under the error phase the filter is not drawn.

## Mutation

Draw every count as `0` under `decisions-error` → the error hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

The four new states, and `acq-resolution-none` / `acq-resolution-tie` (the « Tout voir » entry under their six rows).

## Commit

`feat(maquette-l24): the journal filters by state, its counts from the one read`
