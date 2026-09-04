# Phase 08 — Acquisition: « Veille et obligations » and the journey

## Objective

`openMoreSheet` (`legacy.js:31865–31892`) and `openJourneySheet` (`:31805–31848`) move to
`features/acquisition/panel-more.ts` and `features/acquisition/panel-journey.ts`, kinds `more`
and `journey`, the second addressed `journey:<title>`.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- **§20: the journey sheet IS the tunnel seen by the operator.** It is the surface DOIT-5 names
  and the one L21 will hang « Remettre en file » and « Re-scraper » off. **This lot adds
  neither** — a producer here offers exactly what it offered.
- **The 260 ms wait at `legacy.js:10215`** (`data-journey`: `panel.close()` then
  `setTimeout(() => openJourneySheet(…), 260)`) goes with the producer. The panel leaves inside
  the navigation's own commit, as `data-mediasheet` already does since L12.
- R103 gains a **refused floor on this path**: after the move, the gap between the scrim reaching
  zero and the journey arriving is zero frames. It keeps PRINTING the five sites this lot does
  not own (see `DESIGN.md` § 3.3).
- R100 hold (f) gains `sheet-more` and `sheet-journey`.

## The rules that bite

`harness/journey.py` (R82) already holds the journey's address. It gains the seam and the
descriptor's own facts. `exits.py` gains the refused floor.

The mutation for the floor puts the wait back:

```bash
sh scripts/mutate.sh frontend/maquette/design/src/engine/legacy.js \
  '<the 260 ms wait restored on the journey path>' frontend/maquette/harness/exits.py
```

Red, naming the frames of bare page. Restored.

## Verdict

*(filled when the phase lands)*
