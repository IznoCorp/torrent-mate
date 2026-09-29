# Phase 14 — The ladder's words (DOIT-1)

**STOP C: OPEN 5.** Reading A (4 points): the fold « trié · enrichi · rangé » stands (L22 OPEN 4 = B, 2026-09-26) and
the phase is a proof. Reading B (9): on the journey sheet « enrichi » unfolds into « posters récupérés » and
« bande-annonce », each with its state.

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `python3 -c "import json;print([s['rung'] for r in json.load(open('frontend/maquette/design/src/mocks/seeds/journey-stages.json')) for s in r.get('steps',[])])"`
  → **`['sorted', 'enriched', 'shelved']`**; `grep -n "\"steps\"" -A4 frontend/maquette/design/src/i18n/fr.json`
  → « trié », « enrichi », « rangé »; `grep -cv '^\s*$' frontend/maquette/harness/one_ladder.py` → **256** (R207).
- **Points.** A: the rule 3 (every rung and step word read from the one ladder's vocabulary, on the card AND the
  sheet), the report 1. B: + two step rows in the seed shape 1, `panel-journey.ts` (≈ 10 lines edited) 2, `fr.json`
  1, `sheet-journey-enriched-unfolded` 1.
- **Readers.** R207 reads the ladder's order and its one source: under B its step list grows, re-aimed out loud.

## Red today

A: if green on the mocks, the mutation shows the red first. B: `sheet-journey-enriched-unfolded` draws « enrichi »
folded — `0 unfolded step(s)`.

## Move

A: the rule only. B: the unfold, the card's « n sur 8 » unchanged (the card reads rungs, never steps).

## Mutation

Retype a step word in the sheet instead of reading the vocabulary → the one-source hold falls by name.

## Register

The map's DOIT-1 « to draw » half; proposed at phase 19.

## Oracle: states that diverge, declared by name

A: none. B: `sheet-journey`, and the new state.

## Commit

`test(maquette-l24): the ladder speaks DOIT-1's words from one vocabulary` (A) or
`feat(maquette-l24): « enrichi » unfolds into what it fetched` (B)
