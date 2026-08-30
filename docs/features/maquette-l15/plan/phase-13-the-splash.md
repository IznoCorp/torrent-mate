# Phase 13 — The splash

**Kind** conversion. **Part** 9.

## What it owns

One wait: the gap between asking for the application and having an interface. It is on screen from
the first painted frame — the markup is FIRST in `.device` on purpose — and it comes off when the
interface is there, never on a timer. The bar's five seconds are a PACE, not a floor.

## What lands

`app/splash.ts` — the verbs (`show`, `hide`, `coverLoading`) and `window.__loadingDone`, which stays
the seam whatever really knows the interface is ready calls.

**The markup stays in `index.html`.** This is the one part of the entry that does not become a
component, and the reason is the one the document's own comment gives: a browser paints what it has
parsed, and a splash drawn by React appears only once the bundle it exists to cover has already
run. Converting it would break the property it exists for. The bar's animation restart —
`style.animation = "none"`, a forced reflow, then `""` — moves with the verbs.

## What the engine loses

`showStartup`, `hideStartup`, `coverLoading`, `STARTUP_MS`, `loadingEnd`, and the
`window.__loadingDone` assignment.

## The rule

R53 holds « no chrome flash at boot » already. It is re-run, and a hold is added for the property
the restart exists for: driving to the `startup` state twice must show a bar starting from zero
both times, not one left where the previous visit stopped it. **Mutation**: remove the reflow and
confirm the hold falls naming the bar that did not restart.

## Trap

`window.__go` special-cases `startup` (`if (stateId !== "startup") hideStartup()`). That branch
reads a function this phase moves; it moves with it, and `harness/startup.py` is what says so.
