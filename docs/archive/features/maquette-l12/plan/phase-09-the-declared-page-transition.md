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

---

## The skeletons captured — a design option, with its cost (for the operator)

**The defect.** The transition arrives on PLACEHOLDERS. The data lands when it lands, so a 300–450 ms
transition finishes over skeletons and the real content then snaps in with **no transition of its
own**. The steward measured three shimmers live through the capture; silencing them during the
transition removed one competing animation and none of the snap. **It gets worse as the transitions
become more visible**, which the 2026-08-31 re-tuning has just made them.

**Three ways out, and none is free.**

| Option | What it does | What it costs |
| --- | --- | --- |
| **A — transition on the CONTENT's arrival** | keep the navigation instant; start the view transition when the query lands, so the thing that animates is the real content replacing the skeleton | the address changes before anything moves, so a slow query looks like a dead tap. Needs a floor — if the data is already cached, this is indistinguishable from today |
| **B — hold the navigation until the data is there** | wait for the query (with a ceiling, say 200 ms) before starting the transition, so the transition carries real content | a tap that does nothing for up to 200 ms, which is the very sensation §12 is against. Above the ceiling it degrades to today's behaviour, so it is A with extra machinery |
| **C — transition twice** | the navigation transitions to the skeleton; the content's arrival gets a second, quieter one | two movements per tap. Honest about the two events, and the risk is exactly the defect this lot has already paid for once: two systems animating one surface |

**The recommendation is A**, and it rests on what the interface already promises: §19's optimistic
discipline says an action answers the finger before the network. A is the same idea for an arrival —
the *address* answers instantly, the *picture* animates when there is a picture. B buys a smoother
first frame with the one thing §12 will not spend, and C re-introduces the shape that produced the
hero's flash.

**Not this lot's to take.** It changes what a tap feels like on every screen, which is a design
decision and the operator's. Recorded here so it is arbitrated rather than inherited.
