# Phase 3 — The links to Acquisition, and the screens' exits (N4–N6, L1–L4, S1–S7)

**Opening measure** (taken on `f71a44f7b`; re-taken at the real opening): `grep -cv '^\s*$'` →
`features/system/run-screen.tsx` **324**, `features/acquisition/verbs.ts` **131**, `features/acquisition/add-screen.tsx`
**382** (STOP D near 400); the two screen REPLACES (`features/releases/verbs.ts:93–99`,
`features/acquisition/resolution-verbs.ts:106–108`). **The readers this phase reverses**: R239
`frontend/maquette/harness/no_sentence_to_arrivals.py:176–177` (« the landing stands on the floor, no entry left
underneath ») — re-aimed OUT LOUD: the landing stands ON the trail, not on the floor (`__TSR_index`: `floor + 2`
walked menu → Système → link, `floor + 3` through the run screen), its docstring's point 2 rewritten; its « À traiter » holds (`:171–174`) unchanged.

## What changes

1. **An in-page link arriving home STACKS** (N4, N5; Q12 = A): `switchPage`'s step back onto the floor
   (`page-switch.ts:218–245` here) serves only a bar or menu origin (phase 1's origin fact); an in-page
   link to Acquisition records like any other. Retour → Système, or the
   run screen; the guard arms only from the floor (Y5 walked again).
2. **N6's control is the screen's Retour**: `backAction` + `bridge.back()` (as `run-screen.tsx:307`), no `data-go`;
   a cold `/run/<unknown>` already has Système synthesised under it (`lib/addresses.ts:77`).
3. **« Compléter » goes through the switch** (L3): `complete` (`features/acquisition/verbs.ts:95–101`) calls the
   `go` path from its panel; the panel's entry is kept (D-L13-1), so Retour → Médiathèque, the panel reopened.
4. **The add screen's exit closes it** (L4): `toFollows` pops the screen (`bridge.back()`), then sets « Maintenant »
   as a setting (the replace door) — no second Acquisition entry.
5. **A screen that opens another stacks** (S2, S3; DECIDED 2 = A): the two `replace` flags go; a pick in the
   identification search rewinds two entries, as the resolution's pick closes it (09-15 Q4).
6. **The named states** `nav-acquisition-over-system` (`harness/states/system.ts`, `poseTrail(["acq", "sys"])` then
   « À traiter ») and `run-not-found` (the run screen on an unknown uid) — DESIGN § 4.
7. R-navigation-a's `owed: 3` rows lose the mark; the completeness hold's second hold reads 0 `page` writes outside
   the verbs.

## Acceptance — red first on the old code, then green

- **R-navigation-a**: N4–N6, L3, L4, S2, S3 red at phase 2's head (declared), green here; mutations by NAME —
  « an in-page link arriving home steps back onto the floor » → N4, N5, Y5 fall; « `complete` writes `page`
  itself » → L3 and the second hold fall.
- **R239 re-aimed** as above; R187/R75 (`back.py`, `screen_addresses.py`) green — the run screen's Retour unchanged.
- Walked by finger at 369 px: Système › passages « Acquisition → » → Retour → Système → Retour → Acquisition →
  Retour → the guard; Médiathèque › Incomplets › a series › « Compléter » → Retour → Médiathèque, panel open;
  Acquisition « + » → « Voir mes suivis » → Retour → the guard; a release → « profil » → Retour → the releases.
- Oracle: accepts `nav-acquisition-over-system`, `run-not-found` by name; R-conformity-a on both.

## Commit

`fix(maquette-navigation): a link to Acquisition stacks, and every screen closes the way it opened`
