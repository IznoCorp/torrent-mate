# Phase 7 — The bar, composed by rights

**Amended 2026-09-27** (renumbered from the first drawing's phase 5): OPEN 4 is RULED (B, widened by ruling 17 —
every access is an ACL right; `trackers.view` is Admin-default, grantable, no longer a two-reading parameter this
phase reads without choosing). This phase ALSO lands: **Découvrir's bar row** (round 8 Q20, gated by
`acquisition.request`, fourth place — the count is now 2/3/4 or none, never the first drawing's 1–3); **a role
with no page routes to `/no-access`** (ruling 22's precision — a dedicated route, sign-out only, no bar, no menu);
**the entry-page rule** (round 10 Q7 — `addressSeam.homePage` reads the model: the first page of the account's own
bar in bar order, or its only page, or the first menu page opened — F34, amending `frontend-architecture.md`'s §
16 entry and `product-intent.md` § 16.2, both the operator's hand, not this phase's edit). **F49 corrects this
file's own claim of being the sole post-L15 frame-code edit** — L22b and L16 both land `app/` edits first; this
phase RE-READS their `inBar` rows rather than opening them cold. Re-estimated at **15** (was 12).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything, and again against L22b's open
head:**

- **Commands.** `wc -l frontend/maquette/design/src/app/navigation.ts frontend/maquette/design/src/app/tab-bar.tsx frontend/maquette/design/src/app/navigation-seam.ts` → **216, 98, 78**; `git grep -n inBar -- frontend/maquette/design/src | wc -l` → **12** site-lines. Today `NAVIGATION` has 8 rows, 4 in the bar (`acq`, `lib`, `arr`, `sys`), and **no row carries a right**.
- `git grep -l -i -E "data-page=|data-navgo|tabbar|tab-bar|nav button" -- 'frontend/maquette/harness/*.py' | wc -l` → **27** harness files read the bar or the drawer's entries.
- **Does not exist on this head, and re-taken at this phase's opening**: L22's phase 19 (Système leaves the bar, `inBar` on `sys` false, R-L22-q, R-L22-s), phase 20 (the menu button's badge, one derivation summing `badge()` over the rows the bar does not hold) and phase 25 (`arr` dies, the bar reads at two); L16's `trackers` row (`inBar: true`, group `supervision`, no right — L16's OPEN 2 = A). The opening measure re-runs the `inBar` grep and reads what the rows are by then.
- `sed -n 231,234p frontend/maquette/design/index.html` → the menu button is static markup with `data-drawer`; L22 phase 20 chooses its mount.
- **This phase edits FRAME code** (`app/`), the only lot after L15 that does; the plan says so rather than discovering it.
- **Points ≈ 12.** the table: a `right` on the row type and its comment, ≈ 12 new lines (1) + the rows' rights, ≈ 5 lines edited (1) + `tab-bar.tsx` filters by the model, 3 lines; `navigation-seam.ts` mirrors it, 2 lines (1) + the menu button's badge sums over the rows the account can open (1) + R-L18-d and R-L18-e with their mutations (6) + two states re-using the identities' seeds — `bar-household`, `bar-guest` (2).

**FRAME EDIT — the lot's first, and said as such** (the drawer and the address follow in phase 6, the gate in phases 20 and 21). **DESIGN § 3.2.** The table gains ONE thing — the right that opens a row — and the bar one filter: a row is drawn when it is `inBar` AND the model says the account may open it. The badge's sum is filtered the same way (ruling 12: « les droits filtrent les badges avec la barre, sans règle de plus »; the rule is what holds that sentence). **Reads OPEN 4** (who holds `trackers.view`): reading A puts the Operator alone on the row's right, reading B a per-account option — the row's declaration is identical, only the model's table differs (phase 3 carries both as a parameter, so this phase does not move).

## Red today

**R-L18-d — the bar by rights, both sides**: on each identity's bar state the buttons drawn are exactly those the model opens, each of width 1/n (L22's R-L22-s read at 2 and 3), each ≥ 44 px, and the absent pages are ABSENT from the DOM, not hidden; the refusal half is R-L18-c on the pages' reads. **Discharges L16's OPEN 2.**

**R-L18-e — one derivation for the badges**: the menu button's badge equals the sum over the rows the account can open; a seeded Système fault moves the Operator's badge and leaves the Member's absent.

**Red against `main`**: every account gets the Operator's bar.

## Move

The row's right, the filter, the seam's mirror, the badge's filter; the two states.

## Mutation

With the commit made first: draw a row without its right → the absent hold falls; hard-code the Operator's bar → R-L18-d falls on every other identity; sum the badge over every row → R-L18-e falls for the Member.

## Register

—

## Oracle: states that diverge, declared by name

**None by the oracle** — D8 reads the `<nav>`'s rectangle, never a button, so the bar has the same rectangle with two places or four (L22 § 4.1 said so first); the Operator's bar is unchanged. **R-L18-d reads the buttons, or nobody does.** A divergence on a state that draws neither the bar nor the drawer is STOP A. The accessibility tier is re-read.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the bottom bar is composed by rights`
