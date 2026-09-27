# Phase 7 — A refusal is readable

**No OPEN question remains conditional**, but this is where OPEN 8 = A's substance shows: the row separates « the
files are not the same » (never counted) from « the attempt failed » and « the engine could not finish » (both
counted) — DESIGN § 2.2, which is exactly what the badge's derivation (phase 12) reads.

**Opening measure (2026-09-27, on `1d1282567` — the mark is phase 6's):**

- **Commands.** `sed -n 386,411p personalscraper/acquire/events.py` → the twelve reason codes; `grep -n
  'skip_reason = ' personalscraper/acquire/cross_seed.py` → seven assignments, eight values, **none an event** (a
  skip is logged, never emitted — DESIGN fact 4); `grep -n 'in clear French' docs/features/maquette-l16/DESIGN.md` →
  the backend's `stalled-grabs` already answers a `reason` in clear French (L16's own precedent for a sentence, not
  a code).
- **Points ≈ 10.** The refusal row's opened form ≈ 30 lines new 3; the kind-of-trouble line ≈ 12 lines new 1½; two
  family sentences rewritten in `fr.json` 2 (the three family names were keyed at phase 4, the two SENTENCES that
  explain them are the drawing); the candidate/source line ≈ 10 lines 1; the state
  `torrents-cross-seed-refused` re-using phase 2's seed 1; R-L17-c 3; R-L17-a re-aimed at the reasons on rows 1 →
  ≈ 11, cut to 10 by drawing the two family sentences as one.
- **Found.** § 19 point 1: « un cross-seed rejeté parce que la disposition des fichiers ne correspond pas n'est pas
  la même chose qu'un rejet pour politique de tracker ». The engine has no policy code (DESIGN fact 3), so the
  contrast R-L17-c reads is between the families the engine DOES have; the policy case is the STATE (« stoppé »,
  « tracker sans cross-seed »), on its own row, never a reason. **The « files are not the same » family is drawn
  identically whether it counts or not** (it never does, § 2.2) — the badge's own narrowing is phase 12's, not a
  second wording here.

## Red today

**R-L17-c — a refusal is readable with its reason** (DESIGN § 5): on `torrents-cross-seed-refused` the row draws
the sentence of ITS code, its kind of trouble, the candidate's tracker and the source; a layout mismatch and a
transport failure read differently. Red against `main`: no such row.

## Move

1. The opened refusal in `torrents-cross-seed.tsx`; the two family sentences and the candidate line in `fr.json`.
2. `torrents-cross-seed-refused` in `harness/states/trackers.ts`, run under the live-states default of phase 2 (a
   refusal is part of the default scenario now, not a switch-on special case).
3. R-L17-c written first, seen red; R-L17-a re-aimed at the reasons.

## Mutation

Commit first: draw one constant sentence for every code → the contrast hold falls; drop the reason → it falls; draw
the code → R-L17-a falls too.

## Register

—

## Oracle: states that diverge, declared by name

L16's `torrents-list` again where a refusal row is drawn — accepted with « L17 § 3.3: the cross-seed mark ». Any
other divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` on `torrents-cross-seed-refused`.

## Commit

`feat(maquette-l17): a refused cross-seed says why, in words, by the kind of trouble`
