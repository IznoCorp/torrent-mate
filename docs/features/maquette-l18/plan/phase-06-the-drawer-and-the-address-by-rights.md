# Phase 6 — The drawer and the address, by rights

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `wc -l frontend/maquette/design/src/app/drawer.tsx frontend/maquette/design/src/app/page-host.tsx frontend/maquette/design/src/app/not-found.tsx frontend/maquette/design/src/lib/addresses.ts` → **199, 117, 37, 415**; `git grep -n "data-navgo" -- frontend/maquette/design/src | wc -l` → 4; `ls frontend/maquette/design/src/routes | wc -l` → 14 (one thin file per address).
- `sed -n 20,28p frontend/maquette/design/src/lib/addresses.ts` → `PAGE_PATHS` declares 7 pages (`acq`, `lib`, `arr`, `sys`, `maint`, `cfg`, `profile`); `/quality/$name` maps to `acq` (line 71).
- The drawer groups the rows that carry a `group` (`supervision`, `system`, `configuration`); `grouped()` walks `NAVIGATION`. **After L16 it also holds `trackers`; after L22 `arr` is gone and `sys` sits in the drawer only.**
- **Reads OPEN 3** (absent or reserved-and-explained). The two readings share this phase's filter and differ in what a closed place answers: A — the not-found page (the address stays as typed, L22's OPEN 5 form); B — the reserved place, drawn by phase 7.
- **This phase edits FRAME code** (`app/`), the only lot after L15 that does; the plan says so rather than discovering it.
- **Points ≈ 8.** `drawer.tsx` filters its entries by the model, 4 lines (1) + the closed-address guard at the root, ≈ 10 new lines (1) + `page-host.tsx` / `not-found.tsx` answer a closed address, ≈ 5 lines (1) + R-L18-e extended to the drawer's entries (1) + R-L18-y with its mutations (3) + one state, `drawer-household` (1).

**FRAME EDIT** (the drawer, the address guard). **DESIGN § 3.3.** The drawer filters its entries by the same model the bar does; the address guard is the OFFER side's other door (a bookmarked `/system` must not draw the page for an account without the right), and the reads under it are already refused by phase 4. **Under reading A of OPEN 3** a closed address is the not-found page; **under reading B** phase 7 replaces that answer by the reserved place, and R-L18-y's assertion changes with it (its mutation is written for both).

## Red today

**R-L18-y — a closed address**: a cold `/system`, `/maintenance`, `/settings`, `/trackers` for the Member draws what OPEN 3 says and never the page, and the page's reads answer `403`; the same addresses for the Operator draw the pages.

**Red against `main`**: every account opens every address.

## Move

The drawer's filter, the root guard, the closed-address answer; the state.

## Mutation

With the commit made first: remove the guard → R-L18-y falls; draw a closed page's entry for the Member → R-L18-e's drawer hold falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** for the Operator's `drawer-navigation`. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the drawer and the address are composed by rights`
