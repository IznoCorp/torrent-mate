# Phase 14 — « Provoke »: its contract and mock

**Reads OPEN 3 (what « provoke » means on the surface) — reading A only; not ruled at this writing.** Under reading B (no act) phases 14 and 15 do not exist (−17 points) and demand E is
not filed. Under A this phase is the operation and its answer; phase 15 is the act on a row.

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `sed -n 33,60p personalscraper/conf/models/watch_seed.py` → `CrossSeedConfig`: `max_searches_per_day` default **250**, `min_delay_between_searches_s` default **30**,
  `exclude_recent_search_days` default **3** — the engine's own bounds, which NE-DOIT-PAS-8 makes the surface's (DESIGN clause 10); `grep -n 'daily_searches_remaining'
  personalscraper/acquire/cross_seed.py` → the engine reads its quota per sweep. `python3 -c` over `frontend/maquette/contract/openapi.json` → **no** `cross`/`search`-of-a-torrent
  route (`[p for p in d['paths'] if 'cross' in p]` → `[]`). `grep -cve '^[[:space:]]*$'` → `mocks/handlers/acquisition-verbs.ts` **250** (the pattern for a verb whose answer MOVES the
  queue: `sed -n 235,250p`), `mocks/handlers/cross-seed.ts` after phase 3 (≈ 60).
- **Points ≈ 8.** `searchCrossSeed` declared new 2; its mock route new 2; the handler ≈ 30 lines new 3 (a throttled answer that is a visible « en file », and the duplicate refusal — the ONE
  refusal DOIT-4 allows); the section's read edited to carry the quota (`remaining`, `perDay`) 1.
- **Found.** « Occupé » is never an answer (NE-DOIT-PAS-3); an engine throttling answers « en file » with the time it will run, and a second tap on the same torrent is the duplicate.

## Red today

None — a contract and a handler carry no rule; R-L17-i (phase 15) reads them.

## Move

1. The contract first: `POST /api/trackers/{name}/cross-seed/search` (demand E), `x-unseeded`, `compare-contracts.py --write` / `--check`, types, counters before and after.
2. The handler, and the quota field on the section's read.

## Mutation

None.

## Register

Demand E filed by the regenerated register.

## Oracle: states that diverge, declared by name

None.

## Gate

Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`.

## Commit

`feat(maquette-l17): a cross-seed search is declared, bounded and answered`
