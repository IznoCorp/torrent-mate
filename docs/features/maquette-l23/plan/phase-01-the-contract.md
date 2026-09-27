# Phase 1 — The contract

**No STOP C.** Nothing this phase declares is contingent on DESIGN § 7: the new operation and the two new reason
codes are ruled already (round 8 Q8, Q18) — what changes with § 7's own answers is what LATER phases build on top
of this contract, never this phase's own shape.

**Opening measure (2026-09-27, on `7d40969f4`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
  → **67** operations declared today; `[p for p in d['paths'] if any(x in p.lower() for x in ('cross','tracker','seed'))]`
  → **`[]`** — no tracker or cross-seed route exists on `main`, because L16's and L17's own contract demands are
  not yet filed (their PLANS file them when THEY open, before L23's own phase can run). **This phase's own move is
  therefore projected against L17's DESIGN § 2.1, not against a file this tree holds** — the day this phase
  actually opens, both `crossSeed{…}` (the tracker summary) and `CrossSeedTrackerState[]` (the downloads read's
  array) already exist, filed by L17's own phase 1, and this phase EXTENDS them; the re-take at that opening
  replaces this projection.
- **Points ≈ 10.** The new operation, `POST /api/torrents/{infoHash}/cross-seed/{tracker}/upload` →
  `uploadCrossSeed`, declared new (2); the reason enum's two new codes, `creation_failed` and `publish_failed`,
  filed into the SAME family as `inject_failed`/`obligation_write_failed` (≈ 6 lines new, schema plus two
  `x-unseeded` sentences) 1; the register regenerated, its counters read before and after 1; the report naming
  what is DEFERRED (the `via` field of DESIGN § 2.1 demand S, contingent on § 7 Q5 — declared only if L23's own
  opening finds the operator has ruled it) 1½ — the deferral itself costs nothing to STATE, but the report's own
  line does.
- **Found.** Round 8 Q8's own words settle the family (« cas A »): neither code is an ordinary mismatch, both
  belong to « the engine could not finish ». DESIGN § 2.1's demand S (the `via` field) is NOT filed here — it
  reaches into L16's origin-colour question (§ 7 Q5), open, and a demand filed for a reading the operator has not
  chosen is a demand this document is forbidden to invent (DESIGN Non-goals).

## Red today

None — a contract has no rule of its own; `scripts/compare-contracts.py --check` is the guard, read by hand.

## Move

1. Declare `uploadCrossSeed` in `frontend/maquette/contract/openapi.json`, extending L17's own `CrossSeedTrackerState`
   shape as its DESIGN § 2.1 left it (one torrent, one tracker, one call; the answer shape mirrors `searchCrossSeed`'s
   own « queued » discipline). Extend the closed reason enum with `creation_failed` and `publish_failed`, each
   carrying `x-unseeded` (« invented: no fixture exists for the upload, DESIGN § 2.2 »).
2. `python3 scripts/compare-contracts.py --write`, then `--check`, then `npm --prefix frontend/maquette/design run
   generate-contract-types`. Read the counters, before and after, into the report.

## Mutation

None.

## Register

Demand Q (§ 2.1 of DESIGN) filed by the regenerated `docs/reference/frontend-backend-demands.md`; demand R (the
two codes) filed the same way; demand S is NOT filed (deferred, § 7 Q5).

## Oracle: states that diverge, declared by name

None — a contract moves no surface.

## Gate

Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`.

## Commit

`feat(maquette-l23): the upload-to-tracker operation and its two failure codes are declared`
