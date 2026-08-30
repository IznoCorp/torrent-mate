# Phase 10 — B-237: the dialog's z-order

**Kind BEHAVIOUR.** Alone, with its own rule.

## What is wrong

`.dlg` is `z-index: 48` (`legacy.css:225`) and `#nav` is `z-50` (`index.html:447`), both children
of `.device`: **a confirmation opens with the tab bar over its lower edge.** The z-order the tab bar
sits above is not « every layer but two » — `.selbar` 51, `.eppop` 60, `.hpanel` 60,
`.loginscreen` 60, `.splash` 70 all paint over it. The dialog is the one that does not.

Part 6 says what this part owns: **one ranked list, in one place**. Today it is an accumulation.

## What changes

The dialog's stacking rank moves above the tab bar's, and the ranked list becomes a declared scale
in `app/frame.tsx`'s own vocabulary rather than nine numbers in five files. `legacy.css`'s
`z-index: 48` on `.dlg` is **subtracted** — the residue may not grow and this is the reverse of
growing it.

## The rule

A hold that opens each dialog and hit-tests its lower edge: `elementFromPoint` inside the dialog's
rectangle must answer the dialog or a descendant of it, never `#nav` or one of its buttons. Reading
the two `z-index` values and comparing them is NOT the hold — that is a table written beside the
code, and it says nothing about two elements in different stacking contexts.

**Its mutation**: restore the old rank and confirm the hold falls naming the tab bar under the
finger.

## What the oracle will show — NOTHING, and that is the point

**`z-index` is not among the oracle's 19 measured properties** — `regions.json` → `probe` →
`computedStyleSubset` lists `position`, the type metrics, the box, `opacity`, `visibility`, the
colours, `box-shadow`, `animation` and the flex four, and no stacking property at all. The
rectangle does not move either. So this behaviour change is **invisible to the oracle by
construction**, which is precisely why it needs a rule of its own and why that rule must hit-test
rather than read a number. A divergence the oracle reports in this phase is something else moving,
and it is a defect.
