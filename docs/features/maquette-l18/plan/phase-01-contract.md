# Phase 1 — The contract

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(m in ('get','post','put','patch','delete') for v in d['paths'].values() for m in v))"` → **63** operations (34 reads, 29 writes); `'403' in responses` on **62** of them, `takeQueued` (`POST /api/acquisition/to-handle/{mediaId}/take`) on none.
- `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(json.dumps(d['components']['schemas']['Account']))"` → `name`, `email`, `avatar`, all required; the file is 5 874 lines. `docs/reference/frontend-backend-demands.md` is 221 lines, 134 of them table rows.
- `git grep -ci requester -- frontend/maquette/contract` → no match (L22's phase 1 adds it: the card's answers carry a requester from then on). The contract has 0 occurrences of « quality » (`python3 -c "import re;print(len(re.findall('quality',open('frontend/maquette/contract/openapi.json').read(),re.I)))"`).
- The card's identity in the contract: `QueueCard` has `ids` and the routes are keyed `{mediaId}` / `{followedId}` — **two identities, so `reassignRequester` may be two rows**.
- **Points ≈ 12.** three operations declared new — `signInWithPlex`, `reassignRequester`, `setAcquisitionQuality` (6) + two operations edited — `readAccount` re-shaped, `takeQueued` gains its `403` (2) + the `Account` schema and its small shared schemas, ≈ 30 new lines (3) + the register regenerated, `--write` then `--check` (1).
- **What to cut if the opening measure exceeds 15.** If the card's identity is two (mediaId and followedId), `reassignRequester` is two rows (+2 → 14, still under 15).

The contract comes first because `scripts/compare-contracts.py --check` refuses the artefacts apart and because the demands are what make the design's proposals decisions rather than discoveries. **DESIGN § 6.2 rows D, E, I, K, L.** `readAccount` gains the role (operator, household member, guest, none), the two options, the Plex link's state and the instance's ceiling (carried by the one read — one path, NE-DOIT-PAS-7). Demand F (`readAccounts`) is filed by phase 10, G and H by phase 22: **a demand is filed where its surface is drawn**.

## Red today

**Red today**: no operation of the contract carries a role, an option, a Plex sign-in, a reassignment or a per-acquisition quality choice, and `takeQueued` is the one operation that does not declare its `403`. `python3 scripts/compare-contracts.py --check` is green today and must stay green — the phase is red in the sense that the three artefacts (contract, register, mocks) disagree the moment the contract moves, until the register is regenerated.

## Move

Edit `openapi.json`; run `--write`; run `--check` and `python3 scripts/check-mock-seeds.py` (the `schema` arm holds every seed against its operation's schema: `seeds/account.json` must still satisfy the re-shaped `Account`, which is why the new fields are OPTIONAL at this phase or the seed gains them here — the opening measure says which). **No surface reads any of it yet.**

## Mutation

**Nothing to mutate** — a contract is not a behaviour. The mutation is by hand: drop a required field from `Account` → `--check` and `check-mock-seeds.py` fall; **a guard's exit code is read by hand** (B-273, `mutate.sh` cannot judge a guard).

## Register

—

## Oracle: states that diverge, declared by name

**None** — no surface reads the new fields. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`docs(maquette-l18): the contract of accounts — the role, the Plex sign-in, the requester's reassignment`
