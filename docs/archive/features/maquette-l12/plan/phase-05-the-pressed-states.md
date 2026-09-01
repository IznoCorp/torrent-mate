# Phase 5 — The pressed states

**Kind: BEHAVIOUR.**

## What it does

`@media (hover: hover)` for hover, `:active` for pressure, **no JavaScript** — D9 settles all three
and none of them is re-argued here:

- **`onTouchStart` for pressed states is REFUSED.** It lights the pressed state when the finger is
  starting a **scroll**, so a list flickers as it is scrolled. `:active` is cancelled by the browser
  when the gesture becomes a scroll — which is the wanted behaviour, for free.
- **`@media (hover: hover)` is ADOPTED.** The sticky-hover problem is real and this is its
  declarative remedy.

## The device-only half, and it is NOT claimed

The contract says: *verify on a device whether `:active` still needs a touch listener to fire; if it
does, the remedy is one empty listener, never a per-component JavaScript state.* A headless browser
cannot settle this. It is **written and dated as a device-only protocol** in `REPORT.md` (phase 12),
exactly as the interaction budget and the standalone reading are — **never recorded as passed**.

## The rule

One driven rule: under a **real touch stream**, a pressable surface takes its pressed appearance on
press and **loses it when the gesture becomes a scroll**. The second half is the one that matters —
it is the defect `onTouchStart` would introduce, and a rule asserting only the first half would be
green over it.

## Mutation

Implement the pressed state with a JavaScript flag set on `pointerdown` → the scroll case falls.
Restore.

## Done when

Hover is behind `@media (hover: hover)`; pressure is `:active`; no JavaScript state; the rule bit on
the scroll case; the device question is written and dated, not answered.
