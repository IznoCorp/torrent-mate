# Phase 9 — The declared page transition

**Kind: BEHAVIOUR.** **Owns P5** (a declared transition between sibling surfaces) and **P20**
(reduced motion is a designed state for it).

## What it does

A page switch runs inside `document.startViewTransition`; the rules are `::view-transition-*` in
`styles/base.css`; **none of it is a script** (D9 rule 1 — what is declarative lives in the
stylesheet, therefore in the design reference, therefore under the oracle).

**Where the wrap goes**: `app/navigation.ts` (197 non-blank — room). **`app/shell.tsx` is not
opened** (D-L12-3): it is at 398 of 400 and it is not on this path.

**D9 adopts the View Transitions API** — native, compositor-driven, zero bytes, declarative, and
same-document transitions are supported on the target platform. **A JavaScript animation library
for page transitions is REFUSED**: it buys what the platform gives, costs tens of kilobytes, and
moves motion out of the stylesheet. Neither is re-argued.

## §16 is load-bearing here

Back must still re-walk the path, and the ladder L05 delivered must not be disturbed: opening
pushes, adjusting replaces, switching a top-level page replaces. **A transition wrapping navigation
must change none of it.** P3's rules (R59, R65, R69, R82, R94) and P18's are the standing proof and
**must stay green through this phase** — they are read as part of its gate, not merely not broken.

## The rule — and it has two halves, both required

One driven rule reading `document.getAnimations()` **mid-switch**:

- under `prefers-reduced-motion: no-preference` → a view transition **is running**;
- under `prefers-reduced-motion: reduce` → **none is** (invariant 14).

**A rule asserting only the first half has certified half a designed state.** Reduced motion is a
designed state, not a fallback, and the interface being frozen includes it.

## The instrument's trap

The oracle measures at rest under `html.measuring`; a state captured mid-transition is a flicker.
**Named states stay measured settled** — the oracle's own two-frame wait is the precedent. This rule
drives the transition and reads it *while it runs*; it never leaves the oracle to stumble into one.

## Mutation

Remove the `reduce` branch → the second half falls naming reduced motion. Remove the
`startViewTransition` wrap → the first half falls. Restore. **Both seen red.**

## Done when

P5 reads true; P20 reads true for this transition; the transition is declared, not scripted; the
ladder's rules are green; both halves of the rule bit.
