# Phase 6 — Pull-to-refresh joins the vocabulary

**Kind: CONVERSION.**

`MODEL.md` Part 8 assigns it: *`#ptr` is a gesture on `#port` that knows nothing of what refreshes —
it moves with the gesture vocabulary in L12.* It is engine-driven today — the node is `index.html:255`, driven from `legacy.js:32313`, where the engine writes `height` and `transition` as INLINE styles.

**`MODEL.md` cited `index.html:241` for it and that line holds the skip link's comment.** The citation had drifted; it is corrected in this wave and filed as **B-271**. Re-derive a citation against the tree rather than copying it from the model — that is how this one was found.

## What moves

The **gesture** — the pull, its threshold, its release — into `lib/`, beside the press arbitration.
**What refreshes is not its business** and does not move with it: the gesture reports that a pull
completed; the surface decides what that means.

## Why it is a subtraction

Same posture as phase 3 and as `drawer-gesture.ts`: the arbitration leaves `legacy.js`, the engine
consumes the vocabulary, **zero lines are added to the engine**.

## The rule

One rule driving a **real touch stream** on `#port`: a pull past the threshold fires once, a pull
short of it fires not at all, and a pull that the compositor turns into a scroll fires not at all.

**The third case is the one a synthetic event cannot reach** — the engine's own note records it:
*one `pointermove` delivered, then `pointercancel`, while ten `touchmove` arrive for the same
finger.* A rule that does not drive a real finger is green over a pull-to-refresh that fires on
every scroll.

## Mutation

Lower the threshold below the short pull the rule drives → the « short pull fires nothing » case
falls. Restore.

## Done when

The gesture is vocabulary; the engine is shorter; the oracle is green at zero divergence; the rule
bit, including the scroll case.
