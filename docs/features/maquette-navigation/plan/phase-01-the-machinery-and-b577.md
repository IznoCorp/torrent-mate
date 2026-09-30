# Phase 1 — The machinery and Système's page links: the trail, the destination's class, B-577

**Opening measure** (taken on `f71a44f7b`; re-taken at the real opening, on `main` after the train):
`grep -cv '^\s*$'` → `app/page-switch.ts` **294**, `lib/navigation-entry.ts` **141**, `harness/drive.ts` **263**,
`frontend/maquette/harness/journey.py` **773**; the emitters of DESIGN § 0.2's command → **16 lines**; Réglages'
row anchored `[data-part="topic"][data-page="cfg"]` (`features/system/page.tsx:132` here, `:141` on the train).
**The readers this phase reverses**: none of the 30 history-reading rules asserts a Retour after Système's
`data-page` rows (DESIGN § 1.2) — R-navigation-b is the first.

## What changes

1. **The rules FIRST, seen RED** (DESIGN § 2): R-navigation-b in `journey.py` (cold `/system`, a finger on
   Réglages' row, one Retour → `/system`), red on the old code; R-navigation-a — `harness/navigation_edges.py`, all
   35 rows as data, each with its walk, its tap, its expected address, page and `armedExit` after one Retour, and
   its owner (`owed: 2`, `owed: 3` asserted red); the walker and its two holds (completeness over § 0.2's
   emitters; no `page` write outside the three verbs) in `journey.py`.
2. **The entry carries its trail** (DESIGN § 3): `navigationState` writes `trail` — the page ids from the floor up;
   `recordPath` extends it, `replacePath` replaces its top, the boot's synthesised stack writes it
   (`app/arrival.ts:215–240`); an entry without one reads as `[floor, page]`.
3. **The origin and the destination's class are read** (DESIGN § 3): the `page` and `go` verbs pass whether the
   tap came from the bar or the menu, or from inside a page; in `switchPage`, an in-page link RECORDS (N1–N3 —
   B-577); a bar tap on a bar page unwinds the whole trail (T4) — rewind `trail.length - 1`, then the floor takes
   the address (`walk.afterUnwind`, as `:238–240` already does); the current page writes nothing (T5, unchanged).
   An in-page link arriving HOME keeps its old path until phase 3 (N4, N5 `owed: 3`). OPEN 1 = A: a page already on
   the trail stacks again — nothing to search.
4. **The exit guard at the bottom only** (Y5): nothing to change in `app/layers.ts` — the guard is popped only from
   the floor once the trail is honest; the walk proves it.
5. **The named states** `nav-exit-armed` and `nav-trail-settings` (DESIGN § 4), in `harness/states/frame.ts`, with the
   driver's `poseTrail(pages)` in `harness/drive.ts` (entries written AFTER the drive, the trail on each).
6. **The two docstrings** of `page-switch.ts` (`:173–197`, `:254–277`) say § 16 as amended; the old paragraph goes.

## Acceptance — red first on the old code, then green

- **R-navigation-b**: red on `f71a44f7b` (`/acquisition` after Retour), green here; mutation « B-577's mechanism »
  (`replacePath()` where the non-bar branch records) → falls, read by NAME.
- **R-navigation-a**: rows N1–N3, M4, M5, T1–T5, Y5 green; every `owed` row red AS DECLARED; the completeness hold
  green on 13 emitters; mutation « a bar destination rewinds one entry » → T4 falls.
- Walked by finger at 369 px: Médiathèque → menu → Système → Réglages → Retour ×3 (Système, Acquisition — the menu
  rows still `owed: 2` —, the guard); Système → Réglages → bar Trackers → Retour → Acquisition.
- Oracle: accepts `nav-exit-armed`, `nav-trail-settings` by name, and nothing else moves.
- `run.sh --rules journey.py back.py drawer.py url_state.py` green (R59, R65, R69 walk the same verbs).

## Commit

`fix(maquette-navigation): a page link stacks and a bar page unwinds the trail — Système → Réglages → Retour is Système`
