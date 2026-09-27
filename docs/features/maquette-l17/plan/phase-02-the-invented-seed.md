# Phase 2 — The invented seed

**Every OPEN question this phase touched is ruled.** OPEN 5 = A (a fifth word) and round 10 Q5 = A (a sixth): the
seed carries rows of both new kinds. OPEN 6 = B (by history): three rows carry `stoppedAt` and `stopCause`.

**The DEFAULT scenario is REVERSED from the first drawing (round 9 Q9).** The first cut read the operator's live
configuration (every switch off) as his own setting and made the mock's DEFAULT read « stoppé » everywhere. The
operator's own words on 2026-09-27 supersede that: the off values are untouched EXAMPLES, never his choice, and his
instance turns cross-seed active only AT THE SWITCHOVER. **The default seed now shows the LIVE states** (switches
on, a mix of the six words as an ordinary library would show); « le moteur est coupé » becomes a NAMED scenario, not
the default.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.** `ls frontend/maquette/design/src/mocks/seeds | wc -l` → **48** seed files; none names a cross-seed
  (`git grep -n -i -l 'crossseed\|cross_seed\|cross-seed' -- frontend/maquette` → `features/acquisition/live.ts`,
  `i18n/fr.json`, `mocks/seeds/settings.json` only). `grep -cve '^[[:space:]]*$'
  frontend/maquette/fixture-register.json` → **503**. `grep -n -A4 'cross_seed'
  frontend/maquette/design/src/mocks/seeds/settings.json` → `tracker.providers.lacale.cross_seed` (603), `.c411`
  (620), `.tr4ker` (671), `cross_seed.enabled` (807), each `raw: false` — **the operator's own untouched example
  values (round 9 Q9), never edited by this phase's default**. `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/mocks/state.ts` → **398 of 400**: the scenario dial cannot be added there (`sed -n
  230,245p` and `sed -n 305,315p` — `conflict` is the precedent dial). The tracker roster L16 seeds is the roster
  the cases attach to (three trackers in the settings seed).
- **Points ≈ 13.** The seed file `mocks/seeds/cross-seed.json` — the ten cases of DESIGN § 2.3 (two more than the
  first drawing's seven: the excluded pair, the excluded title, the never-searched pair with a reason), ≈ 20 rows of
  ≈ 7 lines — ≈ 130 lines new 13; its fixture-register rows (≈ 10 lines) 1; the scenario dial in a module of its own
  that `mocks/state.ts` reads, carrying the LIVE default and the named off-scenarios (≈ 10 lines new) 1. Cut to 13
  by drawing the dial as one module shared with the default scenario, not a second one. `mocks/seeds/settings.json`
  gains **no** edit — the operator's own off values stand untouched.
- **Found (2026-09-27) — STOP D at this opening, narrowed by round 9 Q9.** The first drawing's STOP D asked
  whether the switch-on scenario needed a dial; the reversed default answers half of it (the dial now carries the
  NAMED off-scenarios, not the default), but `mocks/state.ts` is still 398 of 400 non-blank lines, so the dial's
  home is still a module of its own the phase reports before moving: (a) as drawn, or (b) another home the steward
  names.

## Red today

None — a seed has no rule; `python3 scripts/check-mock-seeds.py` is the guard, read by OUTPUT.

## Move

1. Write `mocks/seeds/cross-seed.json` from the ten cases (DESIGN § 2.3): two trackers cross-seeding one title
   (one with its own active row, one without); a pair stopped by the switch's option; a pair stopped by the
   per-torrent cut; a tracker taking none for a kind of media; three refusals (one per family) plus one transport
   failure; a title with no candidate anywhere; a torrent never searched with a reason; an excluded pair and an
   excluded title; an identified title and an unidentified torrent; one obligation that is a cross-seed's, one that
   is not. **Every row is invented and every row says so**: the file's own header, one row per seed file in
   `frontend/maquette/fixture-register.json` (`x-unseeded`), and the contract's markers from phase 1.
2. The titles come from the mock's own library seeds; the trackers are the roster's. No row names a real torrent,
   and none is presented as lived data (§ 13).
3. The scenario dial, per the steward's STOP D word; **the DEFAULT scenario is the live states**; « le moteur est
   coupé » and each tracker's own switch-off are named scenarios reached through `window.__go`, never the default.

## Mutation

None.

## Register

The fixture register carries the seed's rows as `x-unseeded`; nothing in `BUGS.md`.

## Oracle: states that diverge, declared by name

None — no surface reads the seed yet.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py` (its `schema` arm holds the seed against the contract of
phase 1; its `provenance` arm the four-way correspondence).

## Commit

`feat(maquette-l17): the invented cross-seed seed, every row marked, live states by default`
