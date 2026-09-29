# Phase 10 — Identification, now (S3)

**STOP C: OPEN 3.** Reading A (4 points): a proof — the identification in progress is read on the card's rung, from
the per-medium journey. Reading B (12): the proof, plus Système's « en ce moment » row reading demand C.

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `python3 -c "import json;print([r for r in json.load(open('frontend/maquette/design/src/mocks/seeds/journey-stages.json')) if r['state']=='now'])"`
  → **`identified`, « en cours depuis 4 min »**; `grep -rn "decisions/activity" frontend/maquette/design/src` →
  **nothing**; `grep -cv '^\s*$' …/features/system/pipeline-panel.tsx` → **36**.
- **Points.** Reading A: the rule 3, the report 1. Reading B: + the mock route 2, the row in `pipeline-panel.tsx`
  (≈ 20 lines new) 2, `fr.json` 1, states `system-scraping-now`, `system-scraping-idle` (a new seed row) 3.
- **Readers.** R240 (`harness/levers_stay_live.py`) reads Système's « Pipeline » section: under B its walk meets
  one more row, re-aimed out loud.

## Red today

Reading A: the rule written against the journey sheet; if green on the mocks, the mutation shows its red first.
Reading B: `system-scraping-now` draws no row — `0 row(s)`.

## Move

A: the rule only. B: the row, each medium leading to its card (NE-DOIT-PAS-9's path, three spellings).

## Mutation

A: draw the rung « identifié » as done while the seed says `now` → falls. B: + the row counting a fixed figure →
falls.

## Register

Under A, `decisions/activity` is recorded served differently in the close's report.

## Oracle: states that diverge, declared by name

A: none. B: the two new states, and `system`.

## Commit

`test(maquette-l24): identification in progress is read on the card` (A) or
`feat(maquette-l24): Système says what is being identified now` (B)
