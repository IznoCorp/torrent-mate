# Phase 1 — The reads' contract

**Reads OPEN 1 (the media block's gate) and OPEN 6 (what « stoppé » means) — neither ruled at this writing.** What each reading costs THIS
phase: OPEN 1 = A (the block is drawn at L17): `readMediaCrossSeed` is declared, 2 points; OPEN 1 = B (held until L18): it is not, and the
phase is **11**. OPEN 6 = A (by cause): the `state` enum and the rows carry no date of a past stop; OPEN 6 = B (by history): the row schema
gains a `stoppedAt` (≈ 1 line, +1 with its sentence in the demand) — **the phase stays under 15 either way**.

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
  → **63** operations declared before this phase; `sed -n 20,29p docs/reference/frontend-backend-demands.md` → « required and missing »
  **16** (L22 and L16 move both before L17 opens — re-take). `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([p for p in d['paths'] if any(x in p.lower() for x in ('cross','tracker','seed'))])"`
  → `[]`: **no route names the cross-seed or a tracker on this head**; L16's phase 1 declares the tracker summary read, so on the day this
  phase opens the summary EXISTS and this phase EXTENDS it. `grep -c 'x-unseeded' frontend/maquette/contract/openapi.json` → **33**: the
  provenance marker every new operation carries. `grep -cve '^[[:space:]]*$' frontend/maquette/contract/openapi.json` → **5 873** non-blank
  lines. The patterns to follow: `sed -n 150,160p frontend/maquette/contract/openapi.json` (an operation carrying its `x-unseeded` sentence).
- **Points ≈ 13.** The summary read edited (a `crossSeed` sub-object: `enabled`, `engineEnabled`, `seeding`, `refused`, `lastInjectedAt`) 1;
  `readTrackerCrossSeed` declared new 2; `readMediaCrossSeed` declared new 2 (OPEN 1, A); the schemas — the four-word state enum, the
  reason enum of twelve codes (`sed -n 386,411p personalscraper/acquire/events.py`), the row, the block's row, the sub-object — ≈ 60 lines
  new 6; the two `x-unseeded` sentences (≈ 4 lines edited) 1; the register regenerated, its counters read before and after 1.
- **Found (2026-09-27).** The reason enum is CLOSED and carries twelve codes, eleven reachable; **none is a tracker policy** (DESIGN fact 3):
  the contract declares the twelve as the engine emits them and adds no thirteenth. `CrossSeedInjected.source_tracker` names the TARGET
  tracker (DESIGN fact 2): the contract's field is `tracker`, and the difference is written in the demand's `description`, not hidden.

## Red today

None — a contract has no rule of its own. `scripts/compare-contracts.py --check` is the guard and it is read by hand.

## Move

1. The contract first (D7): declare the operations and schemas in `frontend/maquette/contract/openapi.json`, each new operation carrying
   `x-unseeded` (« invented: no fixture exists for the cross-seed, DESIGN § 2.3 »). Demand D (the obligations read's `crossSeedOf`) is NOT
   filed here — it is filed in phase 8, where it is drawn.
2. `python3 scripts/compare-contracts.py --write`, then `--check`, then `npm --prefix frontend/maquette/design run
   generate-contract-types`. **Read the counters and put them in the report, before and after** (« required and missing » moves by the
   operations declared new: +2, or +1 under OPEN 1 = B).

## Mutation

None.

## Register

Demands A, B and C of DESIGN § 6.2 filed by the regenerated `docs/reference/frontend-backend-demands.md`; nothing else is edited.

## Oracle: states that diverge, declared by name

None — a contract moves no surface.

## Gate

Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py` (its `provenance` arm refuses
an operation carrying neither `x-seeded-from` nor `x-unseeded`).

## Commit

`feat(maquette-l17): the cross-seed reads are declared, invented and marked`
