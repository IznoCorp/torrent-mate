# Phase 9 — The continuation is seen (DOIT-5)

**No STOP C.** A PROOF over surfaces already drawn.

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -n "\"resolved\":" frontend/maquette/design/src/i18n/fr.json` → lines **471, 476** — the state
  word and the message; `grep -n "route(\"resolveDecision\"" …/mocks/handlers/decisions.ts` → line **91**;
  `git grep -ln "resolveDecision" -- frontend/maquette/harness` → **`mocks.py`** alone, which reads the layer's
  answer, never the card after the message.
- **Points ≈ 5.** R-L24-f 3, walked by finger from « À traiter » AND from phase 7's « Corriger »; the resolve handler
  re-answered so the card's rung moves past « identifié » within the visit, if it does not already 1; the report 1.
- **Readers.** R207 (`harness/one_ladder.py`, 256 lines) reads the ladder's order and one source; R-L24-f reads its
  MOVEMENT — a different question, a different hold.

## Red today

R-L24-f: read at the phase's opening.

## Move

The rule only, and the handler if the red requires it. No surface changes.


## Register

The map's DOIT-5 « to draw » half is proved; proposed at phase 20.


## Commit

`test(maquette-l24): after a choice, the card is seen going on`
