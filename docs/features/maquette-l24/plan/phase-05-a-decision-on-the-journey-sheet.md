# Phase 5 — A decision on the journey sheet (S1)

**No STOP C.** Ruled OPEN 1 = C (2026-09-29): a settled decision lives on its medium's card — no list, no screen.

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -cv '^\s*$' frontend/maquette/design/src/features/acquisition/{panel-journey.ts,decision-queries.ts,decision-vocabulary.ts}`
  → **129, 55, 81**; `grep -n "journey-requeue\|journey-rescrape" …/features/acquisition/panel-journey.ts` → lines
  **117, 122** (the sheet's two acts); `grep -n "\"decisionState\"" -A4 frontend/maquette/design/src/i18n/fr.json`
  → « Réglée », « Laissée telle quelle », « Remplacée depuis » — the settled vocabulary exists.
- **Points ≈ 13.** R-L24-a 3; the block, one module of `features/acquisition/` (≈ 40 lines new) 4; `panel-journey.ts`
  draws it from the rung « identifié » onward (≈ 6 lines edited) 1; `fr.json` — the author words (operator, engine)
  and « parmi N candidats » 1; three states re-using phase 2's seeds (`sheet-journey-decision-operator`,
  `sheet-journey-decision-engine`, `sheet-journey-decision-dismissed`) 3; the report 1.
- **Readers.** `sheet-journey` and R126 (`harness/journey_verbs.py`, the sheet's verbs) — the block adds no act in
  this phase (« Corriger » is phase 7's), so R126 reads unchanged.

## Red today

R-L24-a over `sheet-journey-decision-operator`: no block is drawn — `0 block(s)`.

## Move

1. The block reads the medium's latest settled decision from the one settled read (DESIGN § 1.1): what was chosen,
   among how many candidates, by whom, when; a dismissed or superseded decision reads its `decisionStateDetail`
   sentence in the choice's place.
2. While the decision is pending, nothing is drawn — the medium is an « À traiter » card (L22), unchanged.
3. The block is exported for `features/media/` (phase 6): its fan-in is read against
   `python3 scripts/check-frontend-boundaries.py` (ceiling 4) — over it is STOP D.

## Mutation

Draw the candidates' count as a fixed figure → the count hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

`sheet-journey` if the seed's medium already carries a settled decision (declared by script at the opening), and the
three new states.

## Commit

`feat(maquette-l24): a settled decision reads on the journey sheet`
