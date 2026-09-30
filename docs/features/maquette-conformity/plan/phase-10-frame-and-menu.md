# Phase 10 — The frame and the menu (bottom bar, header, drawer, connection notice)

## What changes

1. **The bottom bar's labels read whole at 320 px** (a defect the rule found — `cut · shell/tab-bar`): repaired by
   the scale's own steps, never a size off the scale (`ui/variants/frame.ts:111, 128`, **397 / 400**: class edits
   only). `BUGS.md` line (order 57).
2. **The connection notice's bevel** (R1's family, `bevel · shell/connection-notice` on `relay-lost`,
   `relay-refused`): its `<button>` resets its border.
3. **The three badges are the one badge** (D.1 #8): the bar's, the menu's (`app/menu-badge.tsx:38`), the drawer's
   (`app/drawer.tsx:150`) take phase 3's placements.
4. **The drawer's Appearance choice is `viewSwitch({ size: "text" })`** (OPEN 4 = A, `app/drawer.tsx:48, 163`):
   the frame stops importing a feature's variant; `segmentSmall` dies with its last caller.

## Acceptance — red first

- R-conformity-a: `cut · shell/tab-bar`, `bevel · shell/connection-notice` leave the owed list.
- R-conformity-k (new, `harness/one_badge.py`): on `menu-system-badge`, `drawer-navigation`, `acq-todo-loaded` the
  badges share size, fill and type; R-conformity-o gains its hold: `app/` imports nothing from `features/*/variants.ts`.
- Re-aimed by name: `badges_observed.py`, `drawer.py`, `appearance.py`.
- The oracle accepts by name: the bar at 390 px unchanged (a divergence there is STOP A), the drawer's badge.
  Also `relay-lost` and `relay-refused` (the orchestrator's ruling A, 2026-09-30): the declared consequence of
  item 2 — without the button's bevel and padding the notice is lower, and the viewport under it grows (15 and 6 px).

## Commit

`fix(maquette-conformity): the frame — whole labels at 320 px, one badge, the drawer's choice from ui`
