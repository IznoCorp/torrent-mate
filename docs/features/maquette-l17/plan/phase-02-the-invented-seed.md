# Phase 2 — The invented seed

**Reads OPEN 5 (a pair with nothing found) and OPEN 6 (what « stoppé » means) — neither ruled at this writing.** OPEN 5 = A (a fifth word):
the seed carries one row of the fifth kind per tracker, ≈ 6 rows, **+1 point (13)**. OPEN 5 = B (no row): none. OPEN 6 = A (by cause): a
« stoppé » row has no date; OPEN 6 = B (by history): three rows carry the date the cross-seed was stopped, **+1 point (13)**, and a
« tracker sans cross-seed » row carries none.

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `ls frontend/maquette/design/src/mocks/seeds | wc -l` → **48** seed files; none names a cross-seed
  (`git grep -n -i -l 'crossseed\|cross_seed\|cross-seed' -- frontend/maquette` → `features/acquisition/live.ts`, `i18n/fr.json`,
  `mocks/seeds/settings.json` only). `grep -cve '^[[:space:]]*$' frontend/maquette/fixture-register.json` → **503**. The derived rows
  this lot must NOT touch: `grep -n -A4 'cross_seed' frontend/maquette/design/src/mocks/seeds/settings.json` →
  `tracker.providers.lacale.cross_seed` (603), `.c411.cross_seed` (620), `.tr4ker.cross_seed` (671), `cross_seed.enabled` (807), each `raw:
  false`. `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/state.ts` → **398 of 400**: the scenario dial cannot be added there
  (`sed -n 230,245p` and `sed -n 305,315p` — `conflict` is the precedent dial). The tracker roster L16 seeds is the roster the cases attach to
  (L16's phase 1; three trackers in the settings seed).
- **Points ≈ 12.** The seed file `mocks/seeds/cross-seed.json` — the seven cases of DESIGN § 2.3, ≈ 14 rows of ≈ 7 lines — ≈ 100 lines new
  10; its fixture-register rows (≈ 8 lines) 1; the scenario dial in a module of its own that `mocks/state.ts` reads (≈ 8 lines new) 1.
  `mocks/seeds/settings.json` gains **no** edit.
- **Found (2026-09-27) — STOP D at this opening.** The DEFAULT mock reads the live configuration: the switches are off, so every row of
  every section reads « stoppé » (DESIGN § 2.3). The states that draw « actif », a refusal or a « tracker sans cross-seed » need a switch ON,
  and the switch has ONE source, the Réglages row. The design's reading is a **scenario dial** set by a named state through `applyState`
  (`frontend/maquette/design/src/harness/drive.ts:50`) that turns the switches on in the mock's STATE, never in the seed file; the dial's home
  is a new module because `mocks/state.ts` is 398 lines. The phase reports to the steward with the commands above and does NOT improvise
  another carrier: (a) the dial as drawn, or (b) another home the steward names.

## Red today

None — a seed has no rule; `python3 scripts/check-mock-seeds.py` is the guard, read by OUTPUT.

## Move

1. Write `mocks/seeds/cross-seed.json` from the cases. **Every row is invented and every row says so**: the file's own header, one row per
   seed file in `frontend/maquette/fixture-register.json` (`x-unseeded`, « invented: DESIGN § 2.3 »), and the contract's markers from phase 1.
2. The titles come from the mock's own library seeds (`media-sheets.json` holds 326 keys); the trackers are the roster's. No row names a
   real torrent, and none is presented as lived data (§ 13).
3. The scenario dial, per the steward's STOP D word; the default scenario is the live configuration.

## Mutation

None.

## Register

The fixture register carries the seed's rows as `x-unseeded`; nothing in `BUGS.md`.

## Oracle: states that diverge, declared by name

None — no surface reads the seed yet.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py` (its `schema` arm holds the seed against the contract of phase 1; its `provenance`
arm holds the four-way correspondence).

## Commit

`feat(maquette-l17): the invented cross-seed seed, every row marked`
