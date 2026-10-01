# Phase 14 — « Chercher un cross-seed »: its contract and mock

**OPEN 3 = A, unconditional.** « Chercher un partage croisé » is renamed « Chercher un cross-seed » (round 9 Q10),
addressed per torrent AND per tracker (a pair, never the whole torrent at once). **F45 narrows the bounds**: the
act is held ONLY by the engine's daily quota and its delay between searches — never by the 3-day exclusion window,
which governs the AUTOMATIC sweep alone, not a hand-provoked search.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.** `sed -n 33,60p personalscraper/conf/models/watch_seed.py` → `CrossSeedConfig`:
  `max_searches_per_day` default **250**, `min_delay_between_searches_s` default **30** — the engine's own bounds,
  which NE-DOIT-PAS-8 makes the surface's (DESIGN clause 10); **`exclude_recent_search_days` (default 3) is NOT
  drawn here** (F45) — it belongs to the automatic sweep, and this phase's own act ignores it by design, said so in
  the demand's own description so a later reader does not reintroduce it as a bound. `python3 -c` over
  `frontend/maquette/contract/openapi.json` → **no** search-of-a-torrent route (`[p for p in d['paths'] if 'cross'
  in p]` → `[]`). `grep -cve '^[[:space:]]*$'` → `mocks/handlers/acquisition-verbs.ts` **250** (the pattern for a
  verb whose answer MOVES the queue).
- **Points ≈ 8.** `searchCrossSeed` declared new, addressed by `infoHash` in the path and `tracker` in the body
  (fact 17: the identity already exists on L16's downloads read, no new field needed for it) 2; its mock route new
  2; the handler ≈ 30 lines new 3 (a throttled answer that is a visible « en file », and the duplicate refusal — the
  ONE refusal DOIT-4 allows); the mark's read edited to carry the quota (`remaining`, `perDay`) 1.
- **Found.** « Occupé » is never an answer (NE-DOIT-PAS-3); an engine throttling answers « en file » with the time it
  will run, and a second tap on the same pair is the duplicate. The demand's own description says, in one line, that
  the 3-day exclusion window is the AUTOMATIC sweep's, never this act's.

## Red today

None — a contract and a handler carry no rule; R-L17-i (phase 15) reads them.

## Move

1. The contract first: `POST /api/torrents/{infoHash}/cross-seed/search` (demand E), body `{tracker}`, `x-unseeded`,
   `compare-contracts.py --write` / `--check`, types, counters before and after.
2. The handler, and the quota field on the mark's read.

## ~~Mutation~~

None.

## Register

Demand E filed by the regenerated register.

## ~~Oracle: states that diverge, declared by name~~

None.

## Gate

~~Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`.~~

## Commit

`feat(maquette-l17): a cross-seed search is declared, bounded by the engine's quota and delay only`
