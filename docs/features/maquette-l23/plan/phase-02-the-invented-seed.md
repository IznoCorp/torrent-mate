# Phase 2 — The invented seed

**STOP C — Q1 and Q3 (DESIGN § 7).** This phase seeds the IDENTITIES the later phases prove against — which
account holds the upload right, and whether the seeded torrents needing an upload path are all currently-seeding
copies (Q1 reading A) or include a dispatched, torrent-less medium (Q1 reading B). Neither is chosen: this phase
does not open until the operator has ruled at least Q1 (the shape of what a seed row represents) and Q3 (whether
a NEW identity, holding `trackers.upload`, is needed beside the ones L18's own plan already seeds, or whether
`trackers.control`'s existing holder suffices).

**Opening measure — PROJECTED against L17's plan, re-taken at this phase's real opening.**

- **Commands (as they will read once L17 has landed).**
  `python3 scripts/check-mock-seeds.py --list features/trackers` (a command L17's own phase 2 introduces; not
  runnable on this tree — `frontend/maquette/design/src/features/trackers` does not exist, measured phase 1's own
  opening). The seed file L17's plan describes (`docs/features/maquette-l17/plan/phase-02-the-invented-seed.md`)
  is the one this phase EXTENDS, never replaces.
- **Points ≈ 9** (projected). Two new seeded cases (a pair moving `noMatch → active` by upload, one moving
  `noMatch → error` by each of the two new codes) — three rows, each a new named state needing a new seed row (2
  · 3 = 6); the register's fixture list extended, one line each (3 rows, 1 line total ≈ ½); one new identity, IF
  Q3 rules a new right needed (2), held pending. **9 assumes Q3 = A** (reuse `trackers.control`, no new identity);
  a Q3 = B reading raises this to ≈ 11, still under the ceiling — the phase's own re-measure at opening reports
  which.
- **Found.** Nothing — this phase invents its own cases, from DESIGN § 3's own list, the same discipline L17's
  own phase 2 followed for cross-seed with no fixture to seed from.

## Red today

None — a seed has no rule of its own; `python3 scripts/check-mock-seeds.py` is the guard.

## Move

1. Add, to the seed L17's own plan builds, three rows marked `x-unseeded`: one pair that an upload SUCCEEDS on
   (moving to `active`, `via: "upload"` if Q6 has ruled the field real by then, otherwise the plain `active` row
   L17 already draws); one that fails at CREATION (`creation_failed`); one that fails at PUBLICATION
   (`publish_failed`). Per Q1's ruling, seed either an active-torrent-only case (reading A) or add one dispatched,
   torrent-less medium too (reading B).
2. Per Q3's ruling: reuse an existing identity (`izno`, Admin) if `trackers.control` is the gate, or seed one new
   identity holding `trackers.upload` alone (an account that can control cross-seed generally but NOT upload, and
   the reverse) if a new right is ruled.
3. `python3 scripts/check-mock-seeds.py` — its provenance arm refuses a row carrying neither `x-seeded-from` nor
   `x-unseeded`.

## Mutation

None.

## Register

The fixture register (`docs/features/maquette-l23/plan/` itself, once merged into the running lot's own fixture
log) gains three rows, named by state id (DESIGN § 3).

## Oracle: states that diverge, declared by name

None — a seed moves no rectangle.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`.

## Commit

`feat(maquette-l23): the upload's three cases are seeded, marked invented`
