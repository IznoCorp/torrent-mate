# Phase 21 — A pull begun on a card refreshes (B-556)

**Born 2026-09-27 from the operator's report** on tm-design (~15:05, main `a6fb6fc1d`): « Onglet suivi : impossible de
tirer pour rafraîchir ». Placed by the steward right after phase 20; every phase after it shifted by two.

**Opening measure (2026-09-27, on `e5411db6f`):**

- **The cause, read** (`app/pull-indicator.ts`, `lib/pull-gesture.ts`, `lib/swipe-arbitration.ts`): the pull's
  `isExcluded` refuses any gesture whose target is inside `.swipe`, `.sugwrap`, `.deck` or `.pillscroll`. Every row of
  « Suivis » is a swipe row (`follows-tab.tsx` → `swipeRowMarkup`), and so is every row of the Médiathèque's lists
  (`library-rows.ts`): a thumb put on the list — nearly the whole screen — starts no pull. « En cours » and « À traiter »
  draw plain cards and are NOT excluded. R223 pulls at `#port`'s top + 60 px, above the cards, which is why it never saw
  it.
- **Why dropping `.swipe` is safe**: the swipe claims the x axis only when |dx| > |dy| × its side-over-down ratio
  (`SIDE_OVER_DOWN` > 1); the pull acts on the y axis only, at the scrollport's top, pulling down. A drag the swipe
  claims is one the pull reads as x, so the two never both answer one drag. `.deck` / `.sugwrap` (Découvrir's deck, whose
  drag goes every way) and `.pillscroll` (a horizontal scroller) stay excluded.
- **Points ≈ 8**: the exclusion 1; the new rule with its mutation 3; the three Acquisition tabs and the Médiathèque read
  2; BUGS.md 1; docs 1. No drawing moves → no oracle divergence.

## Red today

**R235 — a pull begun ON a card refreshes**: on `acq-follows-list`, `acq-now-loaded`, `acq-todo-loaded` and `lib-list`,
a real touch that starts on the first card and travels down past the arming distance ARMS the pull (the indicator opens)
and, released, re-reads (the « Actualisé » message). Red on the code as it stands (main's behaviour on this point):
« Suivis » and the Médiathèque's list do not arm.

## Move

`.swipe` leaves `isExcluded`, and its comment says why the axis is enough.

## Mutation

With the commit made first: `.swipe` excluded again → R235 falls on « Suivis ».

## Oracle

None — a gesture, not a drawing. Any divergence is STOP A.

## Commit

`fix(maquette-l22): a pull begun on a card refreshes`
