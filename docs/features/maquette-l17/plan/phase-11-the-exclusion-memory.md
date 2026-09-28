# Phase 11 — The exclusion memory

**Round 9 Q11**: every cut is REMEMBERED, so the automatic engine does not relaunch a pair (or a whole title) the
operator just cut.

**Opening measure (2026-09-27, on `1d1282567` — the cut is phase 10's):**

- **Commands.** `git grep -n -i 'exclu' -- personalscraper/acquire/cross_seed.py` → `exclude_recent_search_days`
  (fact 5, a TIME window on the automatic sweep) — **no PERMANENT exclusion list exists on the backend today**; this
  is a genuinely new demand (demand K), not a reshape. `grep -n 'registerVerb'
  frontend/maquette/design/src/features/acquisition/follow-verbs.ts` — phase 10's verb pattern, reused for the undo.
- **Points ≈ 11.** The two operations declared new (§ 2.1) 2; the mock route(s) ≈ 25 lines 2½; « Ne plus partager ce
  titre » ≈ 20 lines 2; the undo ≈ 10 lines 1; the state, re-using phase 2's excluded-pair and excluded-title rows,
  1; R-L17-j with its mutations 3 → ≈ 11½, 11 by folding the undo into the SAME named state, read both ways.

## What it builds

- **`writeCrossSeedExclusion` / `undoCrossSeedExclusion`**: the write reads a pair or a whole title and moves the
  seed's `excluded` flags. Phase 10's cut handler is edited so its exclusion write happens in the SAME call (never a
  second one the reader would have to trust agrees).
- **« Ne plus partager ce titre »** on the ORIGIN row, never on a single tracker's line — it acts on EVERY tracker at
  once, cuts every `active` pair the SAME way phase 10 does, with M4's confirmation naming every ending obligation
  (phase 10's component reused), and says the origin torrent's own seeding is untouched.
- **The undo** on an excluded row: a verb with no confirmation (§ 19 point 3: undoing is never destructive).
- **Named state**: `torrents-cross-seed-exclude`.

## Red today

**R-L17-j — the exclusion is remembered, and undoes** (DESIGN § 5): a pair phase 10's cut stops is excluded from
the engine's future passes in the SAME call; « Ne plus partager ce titre » excludes the whole title, on every
tracker; the exclusion answers back after an undo, with no confirmation for the undo itself. Red against `main`: no
exclusion exists anywhere.

## Move

1. **The contract first**: both operations, `x-unseeded`, `compare-contracts.py --write` / `--check`, counters
   before and after.
2. The mock routes and phase 10's handler edit.
3. « Ne plus partager ce titre » and its confirmation; the undo.
4. R-L17-j written first, seen red.

## Mutation

Commit first: leave a cut pair searchable again without an undo having been asked → falls; require a confirmation
on the undo → the undo hold falls; exclude only the tapped tracker when « Ne plus partager ce titre » is used → the
whole-title hold falls. **Register**: both demands filed by the regenerated register.

## Oracle and gate — done when

Oracle: none — an exclusion's flag moves no rectangle it reads; R-L17-j holds it. Gate: per INDEX « Gates »;
`python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`; `--a11y` on
`torrents-cross-seed-exclude`.

## Commit

`feat(maquette-l17): a cut cross-seed is remembered, and a title can be excluded whole`
