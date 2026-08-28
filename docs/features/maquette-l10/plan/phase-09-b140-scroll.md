# Phase 9 — B-140: the scroll memory learns about pages

Its own phase, alone, late. A behaviour change inside a behaviour wave is allowed; a behaviour
change hidden inside a relay phase is an edit nobody can review.

## The defect

`app/scroll-restoration.ts:41` — `activePort()` is `document.querySelector(".screen.open .port")`,
the port of an OVERLAY SCREEN. Main pages scroll inside `#port` (`index.html:224`), which is never
inside a `.screen.open`. On a main page the save stores nothing, or stores the just-opened
screen's offset under the departing page's key. Either way the return finds nothing to restore.

**The relay is what makes it hurt**: content arriving under a reader who then opens an item and
comes back lands them at the top of a list that has also changed length.

## Steps

1. `activePort()` resolves the open screen's viewport when one is open, `#port` otherwise.
2. **Anchor on `[data-part="viewport"]`**, which both already carry, rather than on `.port` — a
   style class Tailwind variants own (D4; invariant 2 read from the code's side).
3. Keep the document-order argument intact: `#shell` precedes the legacy `#screen`, so the React
   screen resolves first, and a legacy screen above it keeps its own restoration.
4. Note in the file that this also pays off B-104's first clause — programmatic scrolling now has
   one path, which `frontend-architecture.md` § 1 names as one of the three things that keep the
   semantic scroll index's door open.

## The rule

**R94 (`harness/scroll.py`, extended)** — restoration on a MAIN page, not only an overlay screen.
Scroll a page, open an item, go back, assert the offset. Then the same for an overlay screen, so
the repair is not proved by breaking the case that worked.

**Mutation**: restore `.screen.open .port` as the only selector. The main-page hold must fall and
the screen hold must stay green — which is what says the rule reads two cases and not one.

## What this phase does NOT do

It does not touch the restoration's retry budget, its image-load wait or its token invalidation.
Those work; the defect is the selector.
