# Phase 16 — The feed: its contract and mock

**Reads OPEN 4 (a feed of injections and refusals, or none) — reading B only; not ruled at this writing.** Under reading A (none) phases 16 and 17 do not exist (−24 points) and demand F is not
filed: S3's rows already carry the date of an injection and the reason of a refusal, and organisation ruling 12 says Système's history is « la seule trace du passé ». **Under B the tension with
ruling 12 is the operator's to lift, and this phase does not start until he has.**

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([p for p in d['paths'] if 'event' in p.lower()])"` → `/api/pipeline/history` and `/api/pipeline/history/{runUid}` (Système's, L20), the run routes and no cross-seed event route. `grep -cve '^[[:space:]]*$'` → `mocks/handlers/pipeline.ts` **326** (the history's handler, the analogue of a list newest-first), `mocks/handlers/cross-seed.ts` after phase 3 (≈ 60 plus phase
  14's ≈ 30 under A of OPEN 3).
- **Points ≈ 10.** `readCrossSeedEvents` declared new 2; its mock route new 2; the handler ≈ 25 lines new 2½; the event rows — the history behind the section's LAST states, ≈ 30 lines new 3 (the seed of
  phase 2 keeps only a pair's last state, so the past is new seed) → ≈ 9½, 10.
- **Found.** The feed's rows come from the SAME pairs the section lists (one derivation): the last row of a pair's history is the state the section draws.

## Red today

None — a contract and a mock carry no rule; R-L17-j (phase 17) reads them.

## Move

1. The contract first: `GET /api/cross-seed/events` (demand F), `x-unseeded`, `--write` / `--check`, types, counters before and after.
2. The handler, and the history rows in the seed file, `x-unseeded` and registered.

## Mutation

None.

## Register

Demand F filed by the regenerated register.

## Oracle: states that diverge, declared by name

None.

## Gate

Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`.

## Commit

`feat(maquette-l17): the feed of cross-seed events is declared and answered`
