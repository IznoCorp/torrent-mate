# Phase 10 — Cutting one tracker's cross-seed

**Round 9 Q5 and Q8** name a torrent's own « couper le cross-seed sur ce tracker », narrower than L16's « Retirer de
qBittorrent » (which removes the WHOLE torrent); **M4** requires it to close a running obligation « libérée »
exactly as L16's removal does.

**Opening measure (2026-09-27, on `1d1282567` — the mark is phase 6's, the switch is phase 9's):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print('release' in
  str(d['paths']), 'remove' in str(d['paths']).lower())"` → `False False` — no release and no removal operation in
  the backend's contract; the same on `frontend/maquette/contract/openapi.json` before L16's phase 6 declares its
  OWN removal (a different operation, a different subject). `sed -n 1,45p
  docs/features/maquette-l16/plan/phase-06-remove-from-qbittorrent.md@f3d8fed01` → L16's removal is single-entry,
  files-deleted-by-default, confirmed, closing an obligation « libérée » — the SAME closing discipline this cut
  reuses on a NARROWER subject (one tracker's entry, never the whole torrent, never touching files). `grep -n
  'registerVerb' frontend/maquette/design/src/features/acquisition/follow-verbs.ts` — the verb pattern followed.
- **Points ≈ 13.** `cutCrossSeed` declared new (§ 2.1) 2; its mock route ≈ 30 lines 3; the gesture and its verb ≈
  20 lines 2; the confirmation ≈ 25 lines 2½; the state `torrents-cross-seed-cut-confirm`, needing a new seed row (a
  ~~pair with a running obligation) 2; R-L17-f with its mutations 3 → ≈ 14½, cut to 13 by drawing the confirmation's~~
  two branches (with/without a running obligation) as one component with a conditional line.

## What it builds

- **`cutCrossSeed`**, one call, every projection: removes the entry from the downloads seed if it was itself active
  there; moves the pair to `stopped` / `stoppedAt` / `stopCause: "removed"` on the origin's `crossSeed` array;
  closes any running obligation with `released_at` set (never left in breach); adds the pair to the exclusion seed
  (phase 11 reads that write and proves it).
- **The gesture** « couper le cross-seed sur ce tracker » on the mark's row, `data-part="torrents/cross-seed-cut"`.
- **The confirmation** names the obligation whenever one is running (M4) and says the origin torrent keeps seeding
  untouched (round 9 Q8): « couper » is NEVER a full removal.

## Red today

**R-L17-f — cutting one tracker's cross-seed** (DESIGN § 5): the operation CALLED; the entry gone from the Torrents
tab if it was active there; the pair `stopped`, `stopCause: "removed"`, its own date; any running obligation closed
`released_at` set, NEVER left in breach; the confirmation names it; the pair excluded in the SAME call. Red against
`main`: no such gesture exists.

## Move

1. **The contract first**: `cutCrossSeed`, `x-unseeded`, `compare-contracts.py --write` / `--check`, counters.
2. The mock route; the gesture and its confirmation; the state.
3. R-L17-f written first, seen red.

## ~~Mutation~~

Commit first: message without calling → the network hold falls; leave the obligation in breach → falls; skip the
confirmation's obligation name → falls; leave a sibling active entry present after the cut → the removal hold
falls; leave the pair included after the cut → phase 11's R-L17-j falls (proved there, once the exclusion exists).
**Register**: demand `cutCrossSeed` filed by the regenerated register.

## ~~Oracle and gate — done when~~

~~Oracle: L16's `torrents-list`, where a pair is cut, accepted with « L17 § 3.3: the cross-seed cut »; any other~~
~~divergence is STOP A. Gate: per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`;~~
~~`python3 scripts/check-mock-seeds.py`; `--a11y` on `torrents-cross-seed-cut-confirm`.~~

## Commit

`feat(maquette-l17): a torrent's cross-seed on one tracker can be cut, and closes its obligation cleanly`
