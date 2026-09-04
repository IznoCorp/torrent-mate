# Phase 11 — Acquisition: the follow sheet, and NE-DOIT-PAS-9's rule

## Objective

`openFollowSheet` (`legacy.js:31593–31799`, **207 lines**, two callers) moves to
`features/acquisition/panel-follow.ts`, kind `follow`, addressed `follow:<title>`. It is the
largest producer in the lot and the one that names the most.

## The recipe

The ten steps of `INDEX.md` § « What every conversion phase does » apply and are not repeated
here. What follows is only what is particular to this surface.

## What is particular

- **The seasons block is already React** and needs nothing:
  `features/media/panel-seasons.tsx` registers `"saisons"`. What line `:31707` still does is
  BUILD the descriptor that names that block. The name crosses through
  `ui/panel/contract`'s open union, which is not a feature import — invariant 7 holds.
- Its derivations read `LIBRARY`, `OWNED`, `SHEETS_RAW`, `INCOMPLETE` and the follow's own state.
  Each read moves to the feature's cache key; **each family whose last producer reader leaves is
  named in this file with what still reads it**, because several are also published to React
  through the reference and do not die here.
- **The 400-line ceiling.** 207 lines of producer plus its derivations will not fit one module
  under the ceiling: it is cut on a SUBJECT — the descriptor, the primary action's arbitration,
  the fraction derivation — never on a line count (L07-bis's precedent, and L14's twice).
- Its primary action's arbitration (blocked outranks everything, then to-grab, then incomplete,
  then followed) is transplanted verbatim. **A behaviour change here is a defect**, and it is
  precisely what a rule below reads.
- R100 hold (f) gains `followsheet-complete` and `followsheet-gaps` — the second being the holed
  matrix, the harder of the two.

## The rules that bite

1. **The primary action's arbitration**, read as a table: for each of the five states, the panel
   offers exactly the action the engine offered. The mutation swaps two branches of the ladder;
   the hold falls naming the state and the two actions.
2. **NE-DOIT-PAS-9's instrument.** The map reads it `partly`: the five galleries
   `harness/gallery.py` names are served, and the LIST rows (a follow row, an arrival row, a
   search result) and the galleries outside those five (`/add`'s results, `acq-now`) are
   unproved. This phase writes a numbered rule over every list row and gallery this lot's
   producers draw: **each names an identified medium and carries a path to its sheet**. The
   mutation removes the path from one row kind and the hold falls naming it.

Where a row is drawn by a producer this lot does NOT move, the rule says so and the map's row
keeps the `partly` with the remainder named. **A row is not turned `served` by a rule that does
not read all of it.**

## Verdict

*(filled when the phase lands)*
