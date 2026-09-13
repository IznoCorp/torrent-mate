# Phase b·10-bis — The library's membership read

A BEHAVIOUR phase, added on 2026-09-13 by rulings 41 and 53 of L13a (recorded in
`docs/features/maquette-l13/RESUME.md@<L13a squash>`), placed between b·10 and b·11 because `legacy.js` cannot die
while it still holds `LIBRARY` (527 lines), `INCOMPLETE`, `knownMedium` and `SEASONS` (110 lines) and while product code
still reads them. It is the ONE phase of L13b where the served answer changes what the screen says, and the rule that
proves it is written RED against the engine first.

## Why it is not a conversion — measured at a·10 and a·14.2

- The library cache is PAGED (24 items, `/media` only) and `/api/library/incomplete` is read on the library page only, so
  « ask the cache » is a NARROWER answer than `window.LIBRARY`'s whole table: `mediaNamedBy` and `knownMedium` would say
  « not in the library » for a title on page two.
- Provider ids are not an identity: two « Doctor Who » rows share tmdb 57243 / tvdb 78804; the engine's tables and every
  address are keyed by exact TITLE (with year where the title alone is ambiguous).
- The engine's `SEASONS` fixture disagrees with the served sheets on 6 of the 10 followed titles that draw a season block
  (Silo has a fourth season in `SEASONS` and three in the served sheet; Dexter's second differs; owned counts 0 where the
  served read says 8/10/12): `python3 /private/tmp/tm-l13a/a142-compare-seasons.py`, kept for this phase's reader. The
  engine LIES today, and the follow panel draws the lie. The constitution's § 13 (real data) is the line that decides
  which side wins: the SERVED sheet.

## The proof FIRST — rules written RED against the engine, then green

- **R-b10bis-1 — membership is exact.** For five titles across the seed (two on the paged listing's first page, two
  beyond it, one absent from the library), the media sheet's « in the library » fact, the follow panel's `inLibrary`
  fact and the delete dialog's reachability all agree with `library-items.json`'s WHOLE seed. Red on the engine for the
  two beyond page one only if the engine copy differs from the seed (it « already ignores mock deletes », DESIGN § 5.1):
  the red reading is the DELETE walk — delete a title, reload, the fact must say absent; the engine says present.
  Mutation: the membership read answers `true` for every title.
- **R-b10bis-2 — the follow panel agrees with the sheet.** For the ten followed titles that draw a season block, the
  season count and each season's owned number equal `readMediaSeasons` for the follow's identity; **Silo's fourth season
  is named in the assertion** (red on the engine: four drawn, three served). Mutation: the panel reads a constant.
- **R-b10bis-3 — INCOMPLETE is the served list.** The « incomplete shows » facts (five reader sites: `:4483`, `:7292`,
  `:8432`, `:29507`, `:30008` of the engine at a·10's head, re-taken on this phase's head) equal `/api/library/incomplete`
  on the library page and are reachable NOWHERE else without a read of their own. Mutation: the served list is emptied.
- **The oracle**: the follow panel of the six disagreeing titles WILL move (a fourth season row disappears on Silo; owned
  numbers change) — a divergence this phase NAMES per state before it runs, and the reference is re-recorded in the
  post-merge gesture, never in the phase. Every other state at zero divergence.
- **Hold counts**: `--compare` with `failed` first; the nine `window.SEASONS` readers re-aimed « count unchanged » or
  their movement written.

## The move

- **The contract gains an exact membership read**: `GET /api/library/membership?title=<exact>&year=<n>` (or the shape the
  contract's conventions prefer — `docs/production/web-ui.md` REST conventions; one operation, typed, staging-guarded on
  the real backend later) answering `{ inLibrary, incomplete, ids }` from the WHOLE seed in the mock layer
  (`mocks/`: a module of its own, `mocks/index.ts` sits at 399 lines). Recorded as a BACKEND DEMAND in the lot's demands
  list (`docs/reference/backend-demands-architecture.md`): exact-title(+year) membership; and, from ruling 55, year + kind
  on QueueCard / LibraryItem / LibraryRow / IncompleteShow.
- **The three readers switch**: `mediaNamedBy` and `openDeleteDialog` (moved to `features/library/` by b·6) read the
  membership answer; `follow-facts.ts`'s `inLibrary` reads it through the follow's identity. `knownMedium` dies with them.
- **`SEASONS` dies**: `follow-facts.ts`'s `followFacts` read (`:33`, `:96` at a·14.2's head) asks `readMediaSeasons` by the
  follow's ids; the seasons half of the `window.__mocks` seed accessor (ruling 54 landed the sheets half only) is added
  for the harness, read by rules and states alone.
- **Deleted from `legacy.js`**: `LIBRARY`, `INCOMPLETE`, `knownMedium`, `SEASONS`, `mediaNamedBy`'s engine copy; the ledger
  re-recorded DOWNWARD in the same commit; `fixture-register.json`'s four rows marked converted / removed ($counts down).
- **Harness re-aims, said out loud in each docstring**: `panel.py`, `url_state.py`, `said_and_done.py`, `library_sort.py`,
  `season_grab_unfollowed.py` (the five a·10 named), and the eight or nine `window.SEASONS` readers a·14.2 named — each
  replayed alone at baseline or its movement written; the `window.__mocks` accessor is the harness's only door to the
  seed.
- **Arms before the move (the steward runs them, L13b brief § Method)**: `python3 scripts/check-frame-domain.py` on the
  head before the phase; `check-frontend-boundaries.py --arm fan-in` after it (the membership read is a `lib/` or
  `features/library/` query, never a new key on `app/`).

## What it makes void

- phase-a10's « the three readers ask the cache » (already amended); phase-b06:39's « reading the library query's cache »
  (amended at a·10 — this phase is where the two fixtures die); DESIGN § 5.1's `LIBRARY` row « dies at a·10 ».
- The two blind spots L13a's reader round names (`panel-seasons.tsx` `ownedSeason`, `follow-facts.ts` `hasSheet`) gain
  their rule here (R-b10bis-2).

## Gate

Per INDEX « Gates ». The operator's Mac walk gains one line for this phase: « Open Silo's follow panel: three seasons,
not four; the owned numbers match the sheet. » — the § 13 sentence for the operator: the engine drew a season that
does not exist.

## Commit

`feat(maquette-l13b): the library answers membership by exact title and the follow panel agrees with the served sheet`
