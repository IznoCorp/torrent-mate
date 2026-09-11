# Phase 1 — The contract

**Nothing in this wave can be called before the interface declares it.** D7: the interface
DECLARES what it requires, seeded from the running backend's shapes, and every difference is a
demand rather than a reconciliation.

## What lands

Three operations in `frontend/maquette/contract/openapi.json`, seeded from `frontend/openapi.json`:

| operationId | Path | Requires |
| --- | --- | --- |
| `grabSeasonForFollow` | `POST /api/acquisition/follows/{followedId}/seasons/{season}/grab` | 201, and a QUEUED 202-equivalent under a busy pipeline |
| `requeueJourney` | `POST /api/acquisition/journeys/{infoHash}/requeue` | 202 `{ runUid }` |
| `rescrapeJourney` | `POST /api/acquisition/journeys/{infoHash}/rescrape` | 202 `{ runUid }` |

They wear the neighbours' spelling (`grabForFollow`, `searchForFollow` are already there) and
camelCase path parameters, because that is what the maquette's contract uses and what
`setOperationOutcome` will key on.

**No 409 is declared on the two journey operations.** The backend answers one when a requeue is
already in flight; NE-DOIT-PAS-3 and §20 forbid the interface showing it. The contract declares the
queued answer, and the difference becomes demand 2.

## The steps, in this order

1. Edit `contract/openapi.json` by hand.
2. `npm run generate-contract-types` in `frontend/maquette/design/`.
3. `python3 scripts/compare-contracts.py --write`.
4. **Commit the three together** — `--check` refuses a register that does not match the contract,
   so they cannot separate.

## The three demands, recorded and NOT reconciled

1. **Identity.** The interface knows a follow by its TITLE and a journey by the title too; the
   backend wants `followed_id` (a rowid) and `info_hash`. § 2b's spelling demand plus an identity
   demand. **No id is invented here** — the mock keys by title, as `followFor` already does.
2. **No 409.** « The backend answers 409 where the interface requires a queued 202. »
3. **The season grab's 201.** A creation in the backend's reading; the interface treats it as a
   state move like the other two.

## Mocks

A NEW FILE under `mocks/handlers/` — `mocks/handlers/acquisition-verbs.ts` — never a growth of
`acquisition.ts` (233 non-blank, soft line 250) past the soft line without saying why. It answers
the three operations, keyed by title, deterministically, and it MOVES STATE: the season leaves
`to_grab`, the journey's stages advance a `now` pip where a `todo` was. A mock that answers 202
and moves nothing would let every rule in phases 2 and 3 pass over a build that called it and
ignored the answer.

## Gate

- `python3 scripts/compare-contracts.py --check` — zero difference between register and contract.
- `python3 scripts/check-mock-seeds.py --arm correspondence --arm classification`.
- `run.sh --contracts`, then the oracle at **zero divergence** — this phase draws nothing, so a
  divergence anywhere is a defect and a STOP.

## Commit

`feat(maquette-l21): the three operations the tunnel's verbs require, declared and mocked`
