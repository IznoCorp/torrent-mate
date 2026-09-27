# Phase 19 — Système leaves the bar

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
- **Points ≈ 15.** `navigation.ts` (`sys.inBar` false; the header comment rewritten, ≈ 12 lines) and the seam 2; five
  readers re-aimed onto the drawer path ½ each 3; R-L22-q with its mutation 3; three states (`drawer-system`,
  `bar-todo-badge`, `bar-clear`) 3 (reusing seeds) — 11 → **12** with the second touch of `queued_by_hand.py`, which
  phase 31 revisits; **R-L22-s with its mutations 3 → 15** (OPEN 2).
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: `git grep -n inBar` → 12
  site-lines (9 in `app/navigation.ts`, 2 in `navigation-seam.ts`, 1 in `tab-bar.tsx`), 7 lines in 5 files reach Système by the
  bar, `navigation.ts` 210 lines, `tab-bar.tsx` 94, the header comment still « the bar holds the four places one goes to SEE ». New
  measure for the ruling: `sed -n 111,122p frontend/maquette/design/src/ui/variants/frame.ts` → `tabBarButton` is
  `flex min-h-[44px] min-w-0 flex-1 basis-0 …`, and `tabBar` is `flex`: **each present button already takes an equal share, whatever
  their number, and nothing draws a fixed slot**. **Points 12 → 15, moved by OPEN 2 (ruled A: a general FRAME rule)**: a new rule
  with its mutations (+3), and no code, because the code already keeps it. **What to cut if the opening measure exceeds 15**:
  R-L22-s becomes its own phase BEFORE this one — it is green over today's four-button bar too — and this phase returns to 12.

- **Re-measured 2026-09-27 at its opening, on `c94b1c638` — RULINGS 17:** the same five readers plus a sixth, `journey.py` (its page-switch walks tapped `#nav button[data-page="sys"]`, re-aimed onto the bar's own pages, out loud); the three planned states are NOT added — they would copy `drawer-navigation`, `acq-todo-loaded` and `acq-todo-empty`, add no subject and copy a known light-contrast debt — so R-L22-q (R231, `bar_places.py`) and R-L22-s (R232, `bar_shares.py`, one page read as no bar at all, the operator's L18 OPEN 7) read the bar and the drawer on those three. ≈ 11.

Ruling 15: Système LEAVES the bar and is reached from the drawer, at its right. **The bar's composition by rights is
L18's** — this phase draws the bar the table says, with no field added for a right. **OPEN 2 (ruled A) adds the frame rule the
bar owes every count it will ever have**: only the buttons present are drawn, in equal shares of 1/n, n from 2 to 4, never an
empty slot — three here, two when Arrivées dies (phase 33), three again when Trackers lands (L16).

## Red today

**R-L22-q — the bar's places**: the bar draws exactly the rows the table marks `inBar`, each tappable at 44 px; Système is
NOT among them and IS in the drawer's system group; a tap on its drawer entry lands on `/system`.

**R-L22-s — the bar's shares** (DESIGN § 5, a frame rule): on every state that draws the bar, at the count it has, the bar draws
exactly the buttons the table marks `inBar`, each of width 1/n of the bar (within a pixel of rounding), n between 2 and 4, and the
buttons tile the bar's width whole — **no empty slot**.

**Red against `main`**: `sys` is `inBar: true`. **R-L22-s is NOT red** — measured above, the code already shares the bar equally —
so it is written GREEN and proved by its mutations; this is stated rather than staged, and it is why the rule is worth its 3
points: a rule the code already keeps still needs a guard, or the next edit to `tabBarButton` loses it silently.

## Move

`sys` becomes `inBar: false`; the five rules that tapped the bar's Système tab reach it by the drawer; the header comment
of `navigation.ts` is rewritten in the same commit (a comment that outlives its decision is read as current — the species
`CLAUDE.md` records twice) and says the frame rule (« the bar draws the buttons present, 1/n, 2 to 4 »). Named states
`drawer-system`, `bar-todo-badge`, `bar-clear`; R-L22-s reads the bar on each of them.

> **Amended 2026-09-27 (triage F58; RULINGS 17):** none of the three states was created — the bar's rules read the
> states that already draw it. A later lot anchors its bar states beside `drawer-navigation` in
> `harness/states/frame.ts`, never beside `bar-todo-badge`, which does not exist.

## Mutation

With the commit made first: put `inBar: true` on `sys` back → R-L22-q falls; give the buttons a fixed share (`basis-1/4`) →
R-L22-s falls (an empty slot at three); drop `flex-1` → it falls; put a fifth row `inBar: true` → its « n ≤ 4 » hold falls.

## Register

—

## Oracle: states that diverge, declared by name

**None by the oracle** (above). The states that draw the bar are read by R-L22-q and R-L22-s, not by the reference. A divergence on a
state that draws neither the bar nor the drawer is STOP A.

## Gate

Per INDEX « Gates »; the five re-aimed files run by name.

## Commit

`feat(maquette-l22): Système leaves the bottom bar, which draws only the buttons it has`
