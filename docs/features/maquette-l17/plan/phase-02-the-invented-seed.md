# Phase 2 — The invented seed

**Ruled.** OPEN 5 = A (a fifth word) and round 10 Q5 = A (a sixth): the seed carries rows of both new kinds. OPEN 6
= B (by history): three rows carry `stoppedAt` and `stopCause`. **Round 9 Q9: the DEFAULT scenario shows the LIVE
states** (switches on, a mix of the six words as an ordinary library would show) — the operator's off values in the
settings seed are untouched EXAMPLES, never his choice; « le moteur est coupé » is a NAMED scenario, not the default.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.** `ls frontend/maquette/design/src/mocks/seeds | wc -l` → **48** seed files, none a cross-seed
  (`git grep -n -i -l 'crossseed\|cross_seed\|cross-seed' -- frontend/maquette` → `features/acquisition/live.ts`,
  `i18n/fr.json`, `mocks/seeds/settings.json` only). `grep -cve '^[[:space:]]*$'
  frontend/maquette/fixture-register.json` → **503**. `grep -n -A4 'cross_seed'
  frontend/maquette/design/src/mocks/seeds/settings.json` → `tracker.providers.lacale.cross_seed` (603), `.c411`
  (620), `.tr4ker` (671), `cross_seed.enabled` (807), each `raw: false` — **never edited by this phase**.
  `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/state.ts` → **398 of 400**: the scenario dial
  cannot live there (`conflict`, `sed -n 230,245p` and `sed -n 305,315p`, is the precedent dial). The roster the
  cases attach to is L16's (three trackers in the settings seed).
- **Points ≈ 13.** `mocks/seeds/cross-seed.json` — ten cases, ≈ 20 rows of ≈ 7 lines, ≈ 130 lines new 13; its
  fixture-register rows 1; the scenario dial in a module of its own that `mocks/state.ts` reads, ONE module shared
  with the default scenario (≈ 10 lines new) 1. `mocks/seeds/settings.json` gains **no** edit.
- **STOP D at this opening.** `mocks/state.ts` is 398 of 400 non-blank lines, so the dial's home is reported before
  anything moves: (a) a module of its own, as drawn, or (b) another home the steward names.

## Red today

~~None — a seed has no rule; `python3 scripts/check-mock-seeds.py` is the guard, read by OUTPUT.~~

## Move

1. Write `mocks/seeds/cross-seed.json` from the ten cases (DESIGN § 2.3): two trackers cross-seeding one title
   (one with its own active row, one without); a pair stopped by the switch's option; a pair stopped by the
   per-torrent cut; a tracker taking none for a kind of media; three refusals (one per family) plus one transport
   failure; a title with no candidate anywhere; a torrent never searched with a reason; an excluded pair and an
   excluded title; an identified title and an unidentified torrent; one obligation that is a cross-seed's, one that
   is not. **Every row is invented and says so**: the file's own header, one row per seed file in
   `frontend/maquette/fixture-register.json` (`x-unseeded`), and the contract's markers from phase 1.
2. The titles come from the mock's own library seeds; the trackers are the roster's. No row names a real torrent,
   and none is presented as lived data (§ 13).
3. The scenario dial, per the steward's STOP D word; **the DEFAULT scenario is the live states**; « le moteur est
   coupé » and each tracker's own switch-off are named scenarios reached through `window.__go`, never the default.

## ~~Mutation · Oracle~~

None — no surface reads the seed yet.

## Register

The fixture register carries the seed's rows as `x-unseeded`; nothing in `BUGS.md`.

## Gate — done when

~~Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py` (its `schema` arm holds the seed against phase 1's~~
contract; its `provenance` arm the four-way correspondence).

## Commit

`feat(maquette-l17): the invented cross-seed seed, every row marked, live states by default`
