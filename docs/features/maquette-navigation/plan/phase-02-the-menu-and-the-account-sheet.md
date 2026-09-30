# Phase 2 — The side menu and the account sheet (M1–M3, M6, M7, P1) — then the MIDPOINT

**Opening measure** (taken on `f71a44f7b`; re-taken at the real opening): `grep -cv '^\s*$' app/page-switch.ts` after
phase 1; `switchPageFromLayer`'s rewind `(leaving === homePage ? 1 : 2) + stackedSurfaces()` (`app/page-switch.ts:296`
here); the `navgo` comment (`app/frame-verbs.ts:99–101`). **The readers this phase reverses**: R82
`frontend/maquette/harness/journey.py:524–525, 554–555, 562–564` (« one Back off Profil reaches the entry page,
never the page it was opened from ») — its account-menu stop becomes `((LIBRARY, "lib"), (HOME, HOME_PAGE))`, the
guard one entry further; said OUT LOUD in its docstring. R65 `drawer.py:182–183` walks from Acquisition (M1
coincides): unchanged, its docstring's hold 2 re-read against the new rule.

## What changes

1. **The layer switch reads the destination's class**: a non-bar destination (Système, Maintenance, Réglages,
   Profil) rewinds the LAYER's entry only and records on the page left (M2, M3, P1); a bar destination unwinds the
   trail (M4, M5 — phase 1's path); the page one is on closes the drawer and writes nothing (M6).
2. **A rubric open under the drawer** (M7, OPEN 3 = B): the drawer's tap gives the rubric's entry back first, the
   order `giveTheEntryBackFirst` already follows for an in-page control (`lib/stacked-surface.ts`), then stacks —
   Retour → the page's root. Under OPEN 3 = A the rubric is counted and kept instead; the answer is read first.
3. **The `navgo` comment** (`app/frame-verbs.ts:99–101`) says the amended rule; « a drawer entry is a top-level
   destination like any other » goes.
4. R-navigation-a's rows M2, M3, M7, P1 lose `owed: 2`.

## Acceptance — red first on the old code, then green

- **R-navigation-a**: M2, M3, M7, P1 red at phase 1's head (declared), green here; M1, M6 green; mutation « the
  layer switch rewinds to the floor for every destination » → M2, M3, P1 fall, read by NAME.
- **R82 re-aimed**: the account-menu stops read `/media` then `/acquisition`, the guard on the third Retour; its
  drawer case (to Acquisition) unchanged.
- Walked by finger at 369 px: Trackers → menu → Maintenance → menu → Réglages → Retour ×3 (Maintenance, Trackers,
  Acquisition); Médiathèque → avatar → « Profil et préférences » → Retour → Médiathèque; Réglages › a rubric → menu →
  Système → Retour → Réglages' root.
- Oracle: no state moves (the drawer and the sheet draw the same); a divergence is STOP A.
- `run.sh --rules journey.py drawer.py arrivals_gone.py bar_places.py selection_survives_the_tab.py` green.

## The midpoint, after this phase

`--contracts` and the full responsive sweep (Chromium + WebKit), once; their real falls repaired before phase 3.

## Commit

`fix(maquette-navigation): the side menu and Profil stack — Retour walks back the way one came`
