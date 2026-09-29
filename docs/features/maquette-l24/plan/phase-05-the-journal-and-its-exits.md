# Phase 5 — The journal and its exits (S1)

**STOP C: OPEN 1** — reading A: a screen `/decisions`, parent `acq`; reading B: a section of Système's history, and
R67 re-aimed. This file is cut for A; under B it is re-cut at its opening, points void.

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `grep -cv '^\s*$' frontend/maquette/design/src/lib/addresses.ts` → **395** (one screen line adds 1:
  396); `grep -n "slice(0, 6)" …/features/acquisition/resolution-screen.tsx` → **183**;
  `grep -cv '^\s*$' …/features/acquisition/resolution-cards.tsx` → **240** (`DecisionCard` lives there).
- **Points ≈ 14.** R-L24-b 3; the journal's screen, one row per decision reusing `DecisionCard` (≈ 60 lines new) 6;
  `routes/decisions.tsx` 2; `SCREEN_PARENTS` one line ⅕; `fr.json` heading and hint 1; two states re-using seeds
  (`decisions-all`, `decision-dismissed-open`) 2.
- **Readers.** `resolution-screen.tsx:177–186` keeps its six rows; `harness/screen_addresses.py` (R75) reads every
  screen address — the new one joins its list, re-aimed out loud.

## Red today

R-L24-b: `/decisions` answers the not-found page — `0 row(s)`.

## Move

1. The screen lists every decision, newest first; a row leads per DESIGN § 1.1 (pending → `/resolution/$folder`,
   « Réglée » → `/media/$provider/$id`, the two others unfold their sentence in place).
2. The screen is an arrival: opening it pushes (§ 16 rule 1); its parent under a cold link is Acquisition.

## Mutation

Point a « Réglée » row at `/resolution/$folder` → the sheet-path hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

`decisions-all`, `decision-dismissed-open` (new). Everything else at zero.

## Commit

`feat(maquette-l24): the decisions journal, and where each row leads`
