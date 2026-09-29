# Phase 1 — The contract

**STOP C: OPEN 1** (rates or volumes) — the two fields of down / up are named only once it is ruled.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.**
  `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
  → **75** operations; `d['components']['schemas']['Download']['properties']` → 16 fields, none of `addedAt`,
  `swarmSeeds`, a rate or a volume; `Tracker` → 8 fields, `identifierRefusedSince` among them, no `enabled`.
  The engine: `grep -n "added_on\|swarm_seeds" personalscraper/api/torrent/_base.py` → lines **48, 77**;
  `AcquisitionDownload` in `frontend/openapi.json` carries neither.
- **Points ≈ 9 / 8.** `Download` edited — `addedAt`, `swarmSeeds`, `swarmLeechers`, the two down / up fields — 1;
  `Tracker` edited — `enabled`, `disabled {by, reason, message, since}`, `identifierRefusedSince` folded into it — 1;
  the `422` refusal of `updateConfigurationFile` described (its `Problem.detail` the engine's words) 1; every
  description saying which field the engine HAS and which it is asked for (DESIGN § 2.1) 2; the register regenerated,
  counters before and after 1; the types regenerated 1; the report 1; under OPEN 1 A, the rates' stream demand on
  `TorrentProgress` 1.
- **Readers.** `identifierRefusedSince` is read by `features/trackers/queries.ts` (`alertOf`), `trackers-tab.tsx:190–192`
  and `harness/trackers_alert.py` — the fold is typed here; phase 14 moves the reads.

## Red today

None — a contract has no rule; `python3 scripts/compare-contracts.py --check` is the guard, read by OUTPUT.

## Move

1. Edit the two schemas in `frontend/maquette/contract/openapi.json`, camelCase, each new field nullable (a client
   that does not say is `null`, never `0`).
2. Keep `identifierRefusedSince` readable until phase 14 (the type derives it from `disabled`) — no reader breaks
   here.
3. `python3 scripts/compare-contracts.py --write`, then `--check`; regenerate the types.

## Mutation

None.

## Register

Demands T3 (the entry) and the `disabled` half of T2 filed by the regenerated
`docs/reference/frontend-backend-demands.md`.

## Oracle: states that diverge, declared by name

None — a contract moves no surface.

## Commit

`feat(maquette-l16bis): an entry's date, sources and exchange, and a tracker's activation and failure`
