# Phase 9 — Tabs by rights, the section absent, the viewer's memory

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `wc -l frontend/maquette/design/src/features/acquisition/acquisition-tabs.tsx frontend/maquette/design/src/features/acquisition/page.tsx` → **54, 49**. **L22 phase 8 creates the fourth tab and phase 13 the default-tab rule** (« Suivis » first, then the last tab opened, in local storage under try/catch): this phase's opening measure re-reads both.
- `git grep -n -E "localStorage|sessionStorage" -- frontend/maquette/design/src | wc -l` → **8** lines in 3 files (`app/appearance.ts`, `app/outbox-store.ts`, `app/worker-registration.ts`): none is keyed to a viewer today (the appearance is the device's) — **L22's default-tab memory is the first viewer-keyed use**, and it does not exist on this head.
- `wc -l frontend/maquette/design/src/app/bar-height.ts` → 58; and `sed -n 60,75p frontend/maquette/design/src/app/tab-bar.tsx` → the bar's height is published (`publishBarHeight`) and read by the content's padding; a bar not drawn must publish zero.
- **Reads OPEN 7** (a bar of one place: A — not drawn; B — one full-width button) and, for the guest's « Suivis » tab, **OPEN 6**.
- **This phase edits FRAME code** (`app/`), the only lot after L15 that does; the plan says so rather than discovering it.
- **Points ≈ 15.** `acquisition-tabs.tsx`: the tabs by rights, ≈ 10 lines edited (2) + the default falls to the first tab the account has, ≈ 8 lines (2) + the section absent: the `acq` row's right is the OR of two, and the landing, ≈ 6 lines (1) + the bar of one place (OPEN 7): A — not drawn (`tab-bar.tsx`, `bar-height.ts`, ≈ 8 lines) / B — one button at full width (the rule amended) (2) + R-L18-x and R-L18-h with their mutations (6) + two states — `acq-guest`, `bar-rightless` (2).
- **What to cut if the opening measure exceeds 15.** At 15. Cut: R-L18-x becomes its own phase (5), and this phase returns to 10.

**DESIGN § 3.4 points 2 and 7, § 3.2.** « Suivis » needs `acquisition.follow`; the others need `acquisition.request`. **L22's default-tab rule meets an account without « Suivis » — and a remembered tab from ANOTHER account on the same device**: the default falls to the first tab the account has, and a remembered tab it does not hold is ignored (R-L18-x). The rights-less Plex user has no Acquisition row, no tabs, no badge (§ 17: the named exception — no explanation is owed, nothing concerns that account) and lands on the Médiathèque.

## Red today

**R-L18-x — the viewer's memory is the viewer's**: after a switch of identity, a remembered tab the new account does not hold is ignored; the default falls to its first tab.

**R-L18-h — the section absent**: `plex-without-rights` — no Acquisition row, tab, badge or address; the landing is the Médiathèque; the bar reads as OPEN 7 says.

**R-L18-d (phase 5) is read again** on `bar-rightless`, at the count OPEN 7 gives it (one place, or no bar).

**Red against `main`**: L22's default rule reads the stored tab unasked.

## Move

The tabs' filter, the fall-back, the landing, the bar of one place, the two states.

## Mutation

With the commit made first: read the stored tab without asking the model → R-L18-x falls; leave the Acquisition row for the rights-less account → R-L18-h falls; draw the bar with an empty slot (reading A) → the frame's shares hold falls.

## Register

—

## Oracle: states that diverge, declared by name

**None** for the Operator's states (the Operator holds every tab). Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): acquisition's tabs follow the account's rights, and an account without them lands on the library`
