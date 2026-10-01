# Phase 11 — Identification, read on the card (S3)

**No STOP C.** Ruled OPEN 3 = A (2026-09-29): no global « en ce moment »; the activity reads on each card, and this
phase is its PROOF.

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `python3 -c "import json;print([r for r in json.load(open('frontend/maquette/design/src/mocks/seeds/journey-stages.json')) if r['state']=='now'])"`
  → **`identified`, « en cours depuis 4 min »**; `grep -rn "decisions/activity" frontend/maquette/design/src` →
  **nothing**, and it stays so.
- **Points ≈ 4.** R-L24-l 3 — the rung « identifié » drawn `now` on the card and the journey sheet, from the
  per-medium journey; the report 1.
- **Readers.** R207 (`harness/one_ladder.py`) reads the ladder's order — untouched.

## Red today

Written against the journey sheet.

## Move

The rule only.


## Register

`decisions/activity` recorded served differently, by the cards, in the close's report.


## Commit

`test(maquette-l24): identification in progress is read on the card`
