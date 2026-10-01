# Phase 15 — The ladder's words, « enrichi » unfolded (DOIT-1)

**No STOP C.** Ruled OPEN 5 = B (2026-09-29): on the journey sheet « enrichi » unfolds into metadata, posters
fetched, trailer, each with its state; the card ladder keeps its eight rungs (round 5 Q4 unchanged).

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `python3 -c "import json;print([s['rung'] for r in json.load(open('frontend/maquette/design/src/mocks/seeds/journey-stages.json')) for s in r.get('steps',[])])"`
  → **`['sorted', 'enriched', 'shelved']`**; `grep -n "\"sorted\": \"trié\"" -A2 frontend/maquette/design/src/i18n/fr.json`
  → lines **999–1001**, « trié », « enrichi », « rangé »; `grep -cv '^\s*$' frontend/maquette/harness/one_ladder.py` → **256** (R207);
  `grep -cv '^\s*$' frontend/maquette/design/src/features/acquisition/panel-journey.ts` → **129** (+ phases 5, 7).
- **Points ≈ 11.** R-L24-n 3 — every rung and step word read from the one ladder's vocabulary, on the card AND the
  sheet — plus its unfold hold 1; three sub-step rows in the seed shape 1½; `panel-journey.ts` (≈ 10 lines edited)
  2; `fr.json` « métadonnées », « posters récupérés », « bande-annonce » 1; `sheet-journey-enriched-unfolded` 1;
  the report 1½.
- **Readers.** R207 reads the ladder's order and its one source: its step list grows, re-aimed out loud.

## Red today

`sheet-journey-enriched-unfolded` draws « enrichi » folded — `0 unfolded step(s)`.

## Move

The unfold on the sheet only; the card's « n sur 8 » unchanged (the card reads rungs, never steps).


## Register

The map's DOIT-1 « to draw » half; proposed at phase 20.


## Commit

`feat(maquette-l24): « enrichi » unfolds into what it fetched`
