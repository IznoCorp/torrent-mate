# Phase 18 — The menu button's badge

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** The button is static markup: `sed -n 229,236p frontend/maquette/design/index.html` →
  `<button class="burger …" aria-label="Ouvrir le menu de navigation" data-drawer="1">` (line 231-234), inside the static
  `<header … data-part="shell/header">` (line 228). `app/frame-verbs.ts:118` `openDrawer` answers `data-drawer`.
  `app/frame.tsx` renders the chrome components (`ActionButton`, `BottomSlot`, `TabBar`, `NavigationDrawer`,
  `DialogLayer`, …) and no header. The badge component to copy in look: `tabBarBadge` (`ui/variants`). Rules that read the
  button: `git grep -l -E 'burger|\[data-drawer' -- 'frontend/maquette/harness/*.py' | wc -l` → **6** (they read its id, its
  `data-drawer` and its name — all three must stay where they are). `features/system/queries.ts` holds the system reads;
  `features/system/locks-queries.ts` the locks read.
- **Points ≈ 12.** A small component portalled into the static header (the way `app/page-host.tsx` portals into `#view`)
  ≈ 30 lines written 3; the mount point and `frame.tsx` 1; `systemBadge` exported by the system feature ≈ 10 lines written 1;
  `sys.badge` in the table and the frame's sum over the rows OUT of the bar ≈ 8 lines 2; R-L22-c with its mutations 3;
  two states (`menu-system-badge`, `menu-clear`) 2.

Ruling 15: the button carries the badge when Système has something to say. **What Système « has to say » is OPEN 8**
(maintenance facts only, or the machine's faults too): the phase draws the wiring and seeds the function with the
smaller reading — A — **only as a placeholder the steward's word replaces in one line**; the rule is independent of it
(it reads that the button equals the drawer entry, whatever the count).

## Red today

**R-L22-c — the menu button's badge**: the button carries a badge exactly when the rows out of the bar have something to say,
its number equal to the drawer entry's own count; ABSENT, not `0`, otherwise.

**Red against `main`**: the button has no badge and `sys` has no badge function.

## Move

The frame sums `badge()` over `NAVIGATION.filter((row) => !row.inBar)` — a derivation that names no domain word, so
invariant 10 is not touched — and draws the result on the button; the drawer entry already draws the same function
(`app/drawer.tsx`), so the button, the entry and the page's own reading are ONE derivation (§13). **The mount leaves the
button's id, its `data-drawer` and its accessible name where they are** (the phase measures the portal against the header's
conversion first and takes the smaller change — DESIGN § 3.6).

## Mutation

With the commit made first: drop the wiring → R-L22-c falls; print a constant → it falls under a seeded change.

## Register

—

## Oracle: states that diverge, declared by name

**None** — the button's own rectangle is not a region root. R-L22-c reads it. Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; the six burger readers run by name; `--a11y` over `menu-system-badge` (the badge's contrast, both
themes).

## Commit

`feat(maquette-l22): the menu button carries Système's badge`
