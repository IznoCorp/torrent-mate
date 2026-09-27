# Phase 11 — The exclusion memory

**A phase the first drawing did not carry** — the feed and its surface stood here before OPEN 4 = A struck them
(−24 points, phases 16–17 of the first cut). **Round 9 Q11 names a memory the first drawing never asked for**:
every cut is REMEMBERED, so the automatic engine does not relaunch a pair (or a whole title) the operator just cut.

**Opening measure (2026-09-27, on `1d1282567` — the cut is phase 10's):**

- **Commands.** `git grep -n -i 'exclu' -- personalscraper/acquire/cross_seed.py` → `exclude_recent_search_days`
  (fact 5's own file, a TIME window on the automatic sweep) — **no PERMANENT exclusion list exists anywhere on the
  backend today**; this is a genuinely new demand, not a reshape of an existing one (unlike demand B). `grep -n
  'registerVerb' frontend/maquette/design/src/features/acquisition/follow-verbs.ts` — the same verb pattern phase 10
  used, reused here for the undo (a verb with no confirmation, § 19 point 3: undoing is never destructive).
- **Points ≈ 11.** `writeCrossSeedExclusion` / `undoCrossSeedExclusion` declared new (§ 2.1) 2; the mock route(s) —
  the write reads a pair or a whole title, moves the seed's `excluded` flags, ≈ 25 lines new 2½; the gesture « Ne
  plus partager ce titre » on the origin row, cutting every `active` pair the SAME way phase 10's cut does (M4's
  confirmation, naming every ending obligation) and excluding the whole title, ≈ 20 lines new/edited 2; the undo
  gesture on an excluded row, no confirmation, ≈ 10 lines new 1; the state `torrents-cross-seed-exclude`, re-using
  phase 2's own excluded-pair and excluded-title seed rows, 1; R-L17-j, with its mutations, 3 → ≈ 11½, 11 by
  rounding down (the undo's own state is folded into the SAME named state, read both ways, rather than a second
  id).
- **Found.** « Ne plus partager ce titre » is on the ORIGIN row, never on a single tracker's own line — it acts on
  EVERY tracker at once. The origin torrent's own seeding is untouched (the same discipline phase 10's cut
  already draws): the confirmation says so.

## Red today

**R-L17-j — the exclusion is remembered, and undoes** (DESIGN § 5): a pair phase 10's cut stops is excluded from the
engine's future passes in the SAME call; « Ne plus partager ce titre » excludes the whole title, on every tracker;
the exclusion answers back after an undo, with no confirmation needed for the undo itself. Red against `main`: no
exclusion exists anywhere.

## Move

1. **The contract first**: `writeCrossSeedExclusion` and `undoCrossSeedExclusion` (§ 2.1), `x-unseeded`,
   `compare-contracts.py --write` / `--check`, counters before and after.
2. The mock routes; phase 10's own cut handler is edited so its exclusion write happens in the SAME call (never a
   second, separate one the reader would have to trust agrees).
3. « Ne plus partager ce titre » on the origin row, its confirmation (M4, reusing phase 10's own component); the
   undo gesture on an excluded row.
4. R-L17-j written first, seen red.

## Mutation

Commit first: leave a cut pair searchable again without an undo having been asked → falls; require a confirmation
on the undo → the undo hold falls; exclude only the tapped tracker when « Ne plus partager ce titre » is used →
the whole-title hold falls.

## Register

Demands `writeCrossSeedExclusion` and `undoCrossSeedExclusion` filed by the regenerated register.

## Oracle: states that diverge, declared by name

None by the oracle — an exclusion's flag moves no rectangle it reads; R-L17-j is what holds it.

## Gate

Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`; `--a11y`
on `torrents-cross-seed-exclude`.

## Commit

`feat(maquette-l17): a cut cross-seed is remembered, and a title can be excluded whole`
