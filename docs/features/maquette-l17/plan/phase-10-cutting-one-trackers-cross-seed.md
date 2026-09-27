# Phase 10 — Cutting one tracker's cross-seed

**A phase the first drawing did not carry** — the media block and its gate stood here before OPEN 1 = B struck them
(−22 points). **Round 9 Q5 and Q8 name a gesture the first drawing never drew**: a torrent's own « couper le
cross-seed sur ce tracker », narrower than L16's « Retirer de qBittorrent » (which removes the WHOLE torrent), and
**M4** requires it to close a running obligation « libérée » exactly as L16's own removal does.

**Opening measure (2026-09-27, on `1d1282567` — the mark is phase 6's, the switch is phase 9's):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print('release' in
  str(d['paths']), 'remove' in str(d['paths']).lower())"` → `False False` — no release AND no removal operation
  exists in the backend's own contract; the same on `frontend/maquette/contract/openapi.json` → `False False`
  before L16's own phase 6 declares its OWN removal (a different operation, a different subject). `sed -n
  1,45p docs/features/maquette-l16/plan/phase-06-remove-from-qbittorrent.md` → L16's own removal is single-entry,
  files-deleted-by-default, confirmed, closing an obligation « libérée » — **the SAME closing discipline this
  phase's own cut reuses, on a NARROWER subject (one tracker's entry, never the whole torrent, and never touching
  files)**. `grep -n 'registerVerb' frontend/maquette/design/src/features/acquisition/follow-verbs.ts` — the verb
  registration pattern this phase's cut follows.
- **Points ≈ 13.** `cutCrossSeed` declared new (§ 2.1) 2; its mock route new — removes the entry from the downloads
  seed if it was itself active there, moves the pair to `stopped`/`stoppedAt`/`stopCause: "removed"` on the origin's
  `crossSeed` array, closes any running obligation `released_at` set (never left in breach), and adds the pair to
  the exclusion seed (phase 11 reads that write; this phase's own mutation proves only the cut, not the exclusion's
  own hold) — ≈ 30 lines new 3; the gesture on the mark's row (« couper le cross-seed sur ce tracker »), its verb,
  ≈ 20 lines new/edited 2; the confirmation, naming the obligation whenever one is running (M4) and saying the
  origin torrent keeps seeding untouched (round 9 Q8) ≈ 25 lines new 2½; the state
  `torrents-cross-seed-cut-confirm`, needing a new seed row (a pair with a running obligation) 2; R-L17-f, with its
  mutations, 3 → ≈ 14½, cut to 13 by drawing the confirmation's two branches (with/without a running obligation) as
  one component with a conditional line, not two.
- **Found.** « Couper » is NEVER a full removal: the entry disappears from the Torrents tab if it had its own
  active row there, but the origin torrent's OWN seeding is untouched — the confirmation SAYS this (round 9 Q8),
  the same discipline M4 asks of every obligation-ending gesture in this codebase.

## Red today

**R-L17-f — cutting one tracker's cross-seed** (DESIGN § 5): the operation CALLED; the entry gone from the Torrents
tab if it was active there; the pair `stopped`, `stopCause: "removed"`, its own date; any running obligation closed
`released_at` set, NEVER left in breach; the confirmation names it; the pair excluded in the SAME call. Red against
`main`: no such gesture exists.

## Move

1. **The contract first**: `cutCrossSeed` (§ 2.1), `x-unseeded`, `compare-contracts.py --write` / `--check`,
   counters before and after.
2. The mock route: the removal, the pair's move to `stopped`, the obligation's close, the exclusion write — one
   call, every projection.
3. The gesture and its confirmation on the mark's row; `data-part="torrents/cross-seed-cut"`; the state.
4. R-L17-f written first, seen red.

## Mutation

Commit first: message without calling → the network hold falls; leave the obligation in breach → falls; skip the
confirmation's obligation name → falls; leave a sibling active entry present after the cut → the removal hold
falls; leave the pair included after the cut → phase 11's R-L17-j falls (proved there, once the exclusion exists).

## Register

Demand `cutCrossSeed` filed by the regenerated register.

## Oracle: states that diverge, declared by name

L16's `torrents-list` again, where a pair is cut — accepted with « L17 § 3.3: the cross-seed cut ». Any other
divergence is STOP A.

## Gate

Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`; `--a11y`
on `torrents-cross-seed-cut-confirm`.

## Commit

`feat(maquette-l17): a torrent's cross-seed on one tracker can be cut, and closes its obligation cleanly`
