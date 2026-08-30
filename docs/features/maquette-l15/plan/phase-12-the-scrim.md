# Phase 12 — The scrim gets one owner

**Kind** conversion. **Part** 7.

## What is wrong today

One element, three writers. The engine raises `#scrim` for the drawer (`openDrawer`) and for the
dialog (`openDlg`); React raises it for the sheet (`ui/sheet.tsx`). `hideLayers` and `closeDlg`
each clear it as a side effect. So whether the scrim is up is a fact nobody owns, and a caller
that closes one layer and opens another on the next line has to know that.

## What lands

The layer host raises the scrim when **any** scrim-backed layer is open, derived from
`app/layer-registry.ts`, and **no one else writes it**. `ui/sheet.tsx` stops writing it directly;
the drawer and the dialog never did once phases 7 and 8 converted them, so what this phase removes
is the engine's remaining `setOpen(select("#scrim"), …)` calls inside `hideLayers`.

`window.__closeLayers` keeps its meaning — what a scrim TAP closes, in order — and keeps living in
the engine until L13.

## The rule

A hold that opens each of the three layers in turn, asserts the scrim is up, closes it, asserts the
scrim is down — and then the case the accumulation made impossible to reason about: **close the
sheet and open a dialog in the same task**, asserting the scrim stays up throughout. **Mutation**:
give the sheet back its own scrim write and confirm the hold falls naming the frame in which the
scrim was down.

## The oracle reads this one

`shell/scrim` is a region, and it is measured across states that open and close layers — which is
exactly why `opacity` and `visibility` were added to the subset on 2026-08-20. Zero divergence.
