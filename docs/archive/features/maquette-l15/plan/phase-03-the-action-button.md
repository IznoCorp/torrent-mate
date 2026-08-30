# Phase 3 — The action button

**Kind** conversion. **Part** 6.

## What lands

`app/action-button.tsx` — `<button id="fab">` at the same id and classes. It reads **two facts**,
which is the whole of the decision the engine's own comment records: the page says whether it has a
primary action (`app/navigation.ts`'s `actionButton`), and a message on screen says whether it may
be shown right now (the toast's store state — phase 6 owns the message; until then the flag crosses
the seam).

The 200 ms return after a message finishes leaving is preserved exactly: it is a measured
arbitration (the close target lands inside the button's box), not a flourish. It applies **only**
after a message, never on a page arrival.

`index.html`'s static `<button id="fab">` is removed in this commit.

## What the engine loses

`refreshActionButton`, `pageWantsActionButton`, `messageIsOnScreen`, `actionButtonReturn`, the
`select("#fab").onclick` binding, and the `fab` capture. The click's act — « the ＋ always means
follow » — crosses the seam as the row's `actionButton` value naming the verb, not the markup.

## The rule

`harness/chrome.py` gains the hold the engine's comment describes and nothing reads: with a message
on screen, `elementFromPoint` at the close button's centre must answer the CLOSE button and not the
action button. **Its mutation**: drop the `messageIsOnScreen` condition and confirm the hold falls
naming the overlap.

## Trap

The button's bottom is `calc(var(--tm-bottom-bar-h,0px)+16px)`. Phase 2 moved when that property is
published; a button drawn before the first publish sits at `0px` for a frame. The layout effect
ordering is what prevents it, and the oracle is what says so.
