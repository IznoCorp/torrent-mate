# Phase 7 — « Corriger » arrives with candidates (S5, DOIT-7)

**RULED OPEN 7 = A** (operator, 2026-09-29, `review-archive/l24/rulings-2026-09-29.md`): one act, « Corriger » on
the block, for both authors, 12 points. Refused: B (a separate third act on the journey sheet).

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -rn "enqueue" frontend/maquette/design/src/features` → **nothing**;
  `grep -cv '^\s*$'` on `features/acquisition/journey-verbs.ts`, `lib/verbs.ts` → **112, 120**;
  `grep -n "route(\"resolveDecision\"" …/mocks/handlers/decisions.ts` → line **91** — addressed by `{decisionId}`,
  which the settled read carries from phase 1.
- **Points ≈ 12.** R-L24-e 3; « Corriger » in the block (≈ 8 lines edited) 1½; its verb in `journey-verbs.ts`,
  registered through `lib/verbs.ts` (L21's registry): on an engine identification it calls `enqueueForResolution`,
  on an operator's choice it opens that decision by its id, then `/resolution/$folder` (≈ 25 lines new) 2½;
  `resolveDecision` re-answered for a settled decision 1; `fr.json`, the act and the refusal's sentence 1; states
  `acq-resolution-enqueued`, `acq-resolution-enqueue-failed` 2; the report 1. R126 (`harness/journey_verbs.py`)
  unchanged — no third act.
- **Readers.** R57 and `harness/ident.py` (186 lines) read the resolution screen's arrival from a card; R126
  (`harness/journey_verbs.py`) reads the sheet's verbs.

## Red today

R-L24-e over `acq-resolution-enqueued`: no act calls `enqueueForResolution` — `0 call(s)` on the network.

## Move

1. The act calls the operation, then opens the screen; the screen shows the candidates the call filed, or the
   pre-filled manual search when none (§ 3's invariant, DOIT-7).
2. A refused call draws its reason; the screen does not open on nothing.

## Mutation

Open the screen without the call → the network hold falls by name.

## Register

The map's DOIT-7 « unproved » half is proved; the row is the operator's to move (phase 20 proposes it).

## Oracle: states that diverge, declared by name

The block's three states (the act drawn) and the two new states.

## Commit

`feat(maquette-l24): « Corriger » sends a decision to arbitration, with its candidates`
