# Phase 8 — « Corriger » on the Médiathèque sheet

**RULED OPEN 8 = A** (operator, 2026-09-29, `review-archive/l24/rulings-2026-09-29.md`): « Corriger » drawn on the
Médiathèque block, opening the arbitration on a shelved medium's decision by its id, the re-identification of a
shelved medium declared as a demand, 8 points. Refused: B (the phase would have dropped).

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -n "rescrapeMedia" frontend/maquette/design/src/features/media/media-verbs.ts` → line **67**,
  the sheet's existing « Re-scraper »; `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([p for p in d['paths'] if 'rescrape' in p])"`
  → `/api/media/{provider}/{providerId}/rescrape`, `/api/acquisition/journeys/{infoHash}/rescrape` — no operation
  re-identifies a shelved medium against candidates.
- **Points ≈ 8 (A).** The operation declared new, recorded as a demand (D7) 2; its mock route new 2; the act on the
  Médiathèque block (≈ 8 lines) 1½; a hold added to R-L24-e, re-aimed out loud 1; `media-sheet-decision-corrected`
  re-using phase 2's shelved row 1; the report ½.
- **Readers.** `media-sheet-decision` (phase 6) — its block gains the act.

## Red today

Reading A: the hold over `media-sheet-decision-corrected` — no act on the Médiathèque block, `0 act(s)`.

## Move

A: the act, its operation and its mock; the arbitration opens on the decision by its id.

## Mutation

Answer the act without calling the operation → the new hold falls by name.

## Register

Under A, the new demand in the regenerated `docs/reference/frontend-backend-demands.md`.

## Oracle: states that diverge, declared by name

A: `media-sheet-decision` (the act drawn) and the new state.

## Commit

`feat(maquette-l24): a shelved medium's decision can be corrected`
