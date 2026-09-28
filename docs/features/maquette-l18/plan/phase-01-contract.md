# Phase 1 — The contract

**Amended 2026-09-27** (DESIGN.md's own amendment): `Follow` and every `QueueCard` gain a `requesters: AccountId[]`
field, plural from the start (F27 — round 9 Q16 lands several requesters per follow before this lot opens);
`reassignRequester` moves ONE requester off a list, one on. A fourth operation is declared new alongside the three
below: `setAcquisitionPause` (demand P, round 10 Q6 precision — the same shape as `setAcquisitionQuality`, one
more schema, ≈ +2 points). `readAccount`'s re-shape now carries the account's RIGHTS (not a role string plus two
options) and a forbidden-writes LIST (not a ceiling boolean) — ruling 20, ruling 23; the `Account`/role schemas
change accordingly. Re-estimated at **14** (was 12); the opening measure below is re-taken at this phase's own
start against the head it actually opens on.

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(m in ('get','post','put','patch','delete') for v in d['paths'].values() for m in v))"` → **63** operations (34 reads, 29 writes); `'403' in responses` on **62** of them, `takeQueued` (`POST /api/acquisition/to-handle/{mediaId}/take`) on none.
- `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(json.dumps(d['components']['schemas']['Account']))"` → `name`, `email`, `avatar`, all required; the file is 5 874 lines. `docs/reference/frontend-backend-demands.md` is 221 lines, 134 of them table rows.
- `git grep -ci requester -- frontend/maquette/contract` → no match (L22's phase 1 adds it: the card's answers carry a requester from then on). The contract has 0 occurrences of « quality » (`python3 -c "import re;print(len(re.findall('quality',open('frontend/maquette/contract/openapi.json').read(),re.I)))"`).
- The card's identity in the contract: `QueueCard` has `ids` and the routes are keyed `{mediaId}` / `{followedId}` — **two identities, so `reassignRequester` may be two rows**.
- **Points ≈ 12.** three operations declared new — `signInWithPlex`, `reassignRequester`, `setAcquisitionQuality` (6) + two operations edited — `readAccount` re-shaped, `takeQueued` gains its `403` (2) + the `Account` schema and its small shared schemas, ≈ 30 new lines (3) + the register regenerated, `--write` then `--check` (1).
- **What to cut if the opening measure exceeds 15.** If the card's identity is two (mediaId and followedId), `reassignRequester` is two rows (+2 → 14, still under 15).

**Amended (steward, L22's close, 2026-09-28): `takeQueued` is GONE.** L22b phase 33 retired it in favour of
`grabForFollow` (`POST /api/acquisition/followed/{followedId}/grab`), which already declares its own `403` — this
opening measure's « `takeQueued` gains its `403` » edit and its point are stale; **re-take the whole measure when
this phase opens**, since the contract has grown past 63 operations since it was last read (`docs/features/maquette-l18/DESIGN.md` § 6.2 row L, § 2.1 — both re-aimed at `grabForFollow`, settled, not conditional).

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
