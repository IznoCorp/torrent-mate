# Phase 17 — Système leaves the bar

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `git grep -n inBar -- frontend/maquette/design/src ':!frontend/maquette/design/src/engine'` → 9 sites in
  `app/navigation.ts` (`acq`, `lib`, `arr`, `sys` true; `maint`, `cfg`, `profile`, `404` false), `app/navigation-seam.ts:35,69`
  (mirrors the flag), `app/tab-bar.tsx:72` (`NAVIGATION.filter((row) => row.inBar)`). The drawer already groups every row
  that has a `group`: `sys` and `maint` sit in « system » (`app/drawer.tsx`). `harness/states/frame.ts` holds
  `drawer-navigation` (« Tiroir de navigation (hamburger) »). Rules that reach Système by the BAR:
  `git grep -n -E 'data-page="sys"|nav button\[data-page="sys"\]' -- 'frontend/maquette/harness/*.py'` → **7 lines in 5
  files**: `locks.py:156` (`SYSTEM_TAB`), `queued_by_hand.py:303`, `seeds_at_rest.py:298`, `sweep.py:15`, `url_state.py:168-170`.
  The drawer path already exists in the harness (`journey.py:502`: tap `[data-drawer]` then `#drawer [data-navgo="…"]`).
  The table's header comment still says « the bar holds the four places one goes to SEE ».
- **Found (2026-09-26).** **The oracle is silent here by construction** (DESIGN § 4.1): D8 reads the rectangle of the `<nav>`,
  never a button, so the bar with three places has the same rectangle as with four. Only R-L22-q reads the buttons.
- **Points ≈ 12.** `navigation.ts` (`sys.inBar` false; the header comment rewritten, ≈ 12 lines) and the seam 2; five
  readers re-aimed onto the drawer path ½ each 3; R-L22-q with its mutation 3; three states (`drawer-system`,
  `bar-todo-badge`, `bar-clear`) 3 (reusing seeds) — 11 → **12** with the second touch of `queued_by_hand.py`, which
  phase 21 revisits.

Ruling 15: Système LEAVES the bar and is reached from the drawer, at its right. **The bar's composition by rights is
L18's** — this phase draws the bar the table says, with no field added for a right.

## Red today

**R-L22-q — the bar's places**: the bar draws exactly the rows the table marks `inBar`, each tappable at 44 px; Système is
NOT among them and IS in the drawer's system group; a tap on its drawer entry lands on `/system`.

**Red against `main`**: `sys` is `inBar: true`.

## Move

`sys` becomes `inBar: false`; the five rules that tapped the bar's Système tab reach it by the drawer; the header comment
of `navigation.ts` is rewritten in the same commit (a comment that outlives its decision is read as current — the species
`CLAUDE.md` records twice). Named states `drawer-system`, `bar-todo-badge`, `bar-clear`.

## Mutation

With the commit made first: put `inBar: true` on `sys` back → R-L22-q falls.

## Register

—

## Oracle: states that diverge, declared by name

**None by the oracle** (above). The states that draw the bar are read by R-L22-q, not by the reference. A divergence on a
state that draws neither the bar nor the drawer is STOP A.

## Gate

Per INDEX « Gates »; the five re-aimed files run by name.

## Commit

`feat(maquette-l22): Système leaves the bottom bar and is reached from the drawer`
