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

**Landed** over two commits. The 207-line producer becomes three files, cut on SUBJECTS:
`follow-facts.ts` (what is TRUE), `follow-actions.ts` (what one may DO), `panel-follow.ts` (the
descriptor). Nine harness rules that drove `openFollowSheet` are repointed at the seam.

### Where the data comes from, and where it does not

`LIBRARY` and `SEASONS` are read from **the window surface the engine publishes for the harness**,
not through the reference — which does not carry them, and adding them to it would be adding to
the engine, which D5 forbids outside a defect that destroys data. `INCOMPLETE` is the engine's
thin arrow over the library's own query and comes through the slice, with its expiry written
beside it. The seasons block receives the same array the engine handed it — the oracle says so at
zero divergence.

### R122 — NE-DOIT-PAS-9's instrument

Six surfaces, each with a floor. **A path is three things**, because the interface spells
reachability three ways — `data-mediasheet`, `data-panel` (the long press raises the panel that
carries the act), and the frame's navigation. Refusing the second would be refusing the
interface's own gesture vocabulary.

**A row wearing `data-nonmedia` is excluded**, and that is the rule getting sharper rather than
weaker: an arrival still a folder nobody has identified names no medium, and demanding a path to
a sheet that does not exist is the same broken promise read from the other side.

**Its first mutation fell nothing, and the rule was right.** Removing `data-panel` from a card's
body left `data-mediasheet` on its poster, so the row was still reachable. The decisive mutation
takes BOTH, and the rule fells **all six** surfaces naming the exact media left stranded — « 4
dead of 12: Kyma, L'Odyssée, Silo, Spider-Man ».

### Readings

oracle **2 958, no divergence** · contracts **16 rules** + 26 guards, no violation ·
`paths_to_sheets.py` 13 holds · `legacy.js` 32 113 → **31 911** · `states.js` 787 → **786**

### Deviation

**Three files rather than the « about six of 190 lines » shape L14 used.** The cut is on the
three questions this panel answers, and each file is well under the ceiling; splitting further
would have been splitting on a line count, which is what both precedents refuse.
