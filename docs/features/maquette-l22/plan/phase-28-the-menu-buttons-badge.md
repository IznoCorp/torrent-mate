# Phase 28 — The menu button's badge

**Cut 2026-09-27 at its opening (≈ 30 on `8a9500c43`):** this file is now 28 (F1 + C2, R236), 29 (the boot list's move) and 30 (the badge below, with M3) — INDEX's last amendment.

**Phase 29, 2026-09-27:** `engine-data.ts` keeps three families no component observes (the follows, the suggestions, the producers' reads) and dies when the last is declared beside its reader — its removal is PROPOSED for phase 40 and put to the steward, who places it.

**Numbered 24, then 26, then 28, on 2026-09-27** (was 20; the triage's F51). **HELD until its opening carries, BEFORE its first commit,
the coherence triage (`review-archive/coherence-2026-09-27-triage.md` § B; texts in `coherence-2026-09-27.md`): F1 + C2 (blocking)** — each navigation row that carries a badge DECLARES the queries its badge reads, and the frame
keeps them OBSERVED for the document's lifetime (a frame-level observer); the declaration is born keyed on the row, so a
row not drawn registers no observer (C2); Système declares locks, services and dependencies; `engine-data.ts`'s boot list
moves into those declarations (its removal scheduled, its header corrected); R-L22-c reads the badge on a cold load of
ANOTHER page, then after a live event, on a seeded fact, with the mutation « drop the declaration → falls »; DESIGN
§ 2.1 and § 3.6 corrected. **And M3** (the auditor's decision-coherence round): the badge counts BY RIGHTS — this phase
builds the no-rights half only, declaring its reads per row, and SAYS so in black and white; L18 writes the rights half
and mutates it. Re-measured at the opening; > 15 → cut. The MIDPOINT full suite runs after this phase.

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** The button is static markup: `sed -n 229,236p frontend/maquette/design/index.html` →
  `<button class="burger …" aria-label="Ouvrir le menu de navigation" data-drawer="1">` (line 231-234), inside the static
  `<header … data-part="shell/header">` (line 228). `app/frame-verbs.ts:118` `openDrawer` answers `data-drawer`.
  `app/frame.tsx` renders the chrome components (`ActionButton`, `BottomSlot`, `TabBar`, `NavigationDrawer`,
  `DialogLayer`, …) and no header. The badge component to copy in look: `tabBarBadge` (`ui/variants`). Rules that read the
  button: `git grep -l -E 'burger|\[data-drawer' -- 'frontend/maquette/harness/*.py' | wc -l` → **6** (they read its id, its
  `data-drawer` and its name — all three must stay where they are). `features/system/queries.ts` holds the system reads;
  `features/system/locks-queries.ts` the locks read.
- **Points ≈ 13.** A small component portalled into the static header (the way `app/page-host.tsx` portals into `#view`)
  ≈ 30 lines written 3; the mount point and `frame.tsx` 1; `systemBadge` exported by the system feature, reading the locks, the
  services and the dependencies ≈ 20 lines written 2; `sys.badge` in the table and the frame's sum over the rows OUT of the bar
  ≈ 8 lines 2; R-L22-c with its mutations 3; two states (`menu-system-badge`, `menu-clear`) 2.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run — the static button
  (`index.html` 229-236), `frame-verbs.ts:118`, 6 burger readers — identical; and for the ruling: `readLocks`, `readServices`
  and `readDependencies` are declared operations (`GET /api/maintenance/locks`, `/api/system/services`, `/api/system/dependencies`)
  whose keys `features/system/live.ts` already refreshes (`LOCKS_KEY`, `SERVICES_KEY`, `DEPENDENCIES_KEY`), and `system-outage`
  already replays a fault (`features/system/fault.ts`). **Points 12 → 13, moved by OPEN 8 (ruled B: the maintenance facts AND the
  machine's faults)**: the badge function reads three answers instead of one (+1).

Ruling 15: the button carries the badge when Système has something to say. **What Système « has to say » is ruled (OPEN 8,
reading B): the maintenance facts AND the machine's faults** — a stale lock, leftover temporary entries, a sweep that did not
finish (`readLocks`), and a service that stopped answering or a dependency that is down (`readServices`, `readDependencies`).
The reading that kept the badge to maintenance alone was refused. One function counts both, and the button, the drawer entry
and the page's own reading are ONE derivation.

## Red today

**R-L22-c — the menu button's badge**: the button carries a badge exactly when the rows out of the bar have something to say,
its number equal to the drawer entry's own count; ABSENT, not `0`, otherwise; **and Système's number moves under a seeded
maintenance fact AND under a seeded service or dependency fault** (both families, OPEN 8).

**Red against `main`**: the button has no badge and `sys` has no badge function.

## Move

The frame sums `badge()` over `NAVIGATION.filter((row) => !row.inBar)` — a derivation that names no domain word, so
invariant 10 is not touched — and draws the result on the button; the drawer entry already draws the same function
(`app/drawer.tsx`), so the button, the entry and the page's own reading are ONE derivation (§13). **The mount leaves the
button's id, its `data-drawer` and its accessible name where they are** (the phase measures the portal against the header's
conversion first and takes the smaller change — DESIGN § 3.6).

## Mutation

With the commit made first: drop the wiring → R-L22-c falls; print a constant → it falls under a seeded change; count the
maintenance facts alone (the refused reading) → the fault hold falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** — the button's own rectangle is not a region root. R-L22-c reads it. Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; the six burger readers run by name; `--a11y` over `menu-system-badge` (the badge's contrast, both
themes).

## Commit

`feat(maquette-l22): the menu button carries Système's badge`
