# Phase 11 — The block's gate

**Reads OPEN 1 (the block's gate) — reading A only.** Under reading B this phase does not exist (phase 10's note). What A costs this phase, said once:
an administrator fact on the account, a SECOND mock identity, and the block absent for it — the small rights model L22's OPEN 11 and L16's OPEN 2 (both
ruled A: no right declared before L18) refused for the same reason. That is the operator's to weigh; this phase does not.

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(json.dumps(d['components']['schemas']['Account']))"` →
  `name`, `email`, `avatar`: **no role**. `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(json.dumps(d['paths']['/api/auth/me'])[:400])"` →
  one string map (`username`). `grep -n 'role' personalscraper/web/models/config.py` → lines 147, 160: the DEPLOYMENT role of the instance
  (`GET /api/config/status`), not an account's. `grep -cve '^[[:space:]]*$'` → `mocks/handlers/authentication.ts` **15**, `mocks/seeds/account.json` **5**,
  `harness/drive.ts` **262**; `sed -n 44,60p frontend/maquette/design/src/harness/drive.ts` → `applyState`, the dial mechanism a second identity would ride.
- **Points ≈ 11.** `readAccount` edited (an `admin` fact) 1; the schema ≈ 4 lines ½; the account seed ≈ 2 lines edited ½; the account handler re-answered 1; the identity
  dial in `harness/drive.ts` ≈ 12 lines new 1½; the media route answering nothing for an identity that is not the administrator's ≈ 6 lines edited 1½; the state
  `media-cross-seed-hidden` (a seed row: the second identity) 2; R-L17-f 3 → ≈ 11. **Demand J** (DESIGN § 6.2) is filed here, as the first consumer of L22's demand D.
- **Found.** The block is ABSENT for the other identity — not disabled, not empty (§ 17 point 1: the offer disappears; a 403 after a gesture is an interface defect) —
  while the Trackers page itself is shown by rights, which is L18's.

## Red today

**R-L17-f — the block, for the administrator only** (DESIGN § 5): on `media-cross-seed`, one block per tracker, each reading the SAME field as the roster; on
`media-cross-seed-hidden`, the block is absent from the DOM for the other identity; a title not owned draws no block and says so. Red: the gate does not exist.

## Move

1. The contract first: `readAccount` extended (demand J), `compare-contracts.py --write` / `--check`, counters before and after.
2. The identity dial, the account handler's answer, the media route's role-aware answer.
3. The gate in the media slot; the two states; R-L17-f written first, seen red.

## Mutation

Commit first: show the block to every identity → the absence hold falls; draw one block for all trackers → the per-tracker hold falls; hide it with `disabled`
instead of removing it → the DOM hold falls.

## Register

Demand J filed by the regenerated register.

## Oracle: states that diverge, declared by name

None by the oracle — a removed element and an identity dial move no rectangle it reads (DESIGN § 4.1 says so before this phase does); R-L17-f is what holds it.

## Gate

Per INDEX « Gates »; `python3 scripts/compare-contracts.py --check`; `python3 scripts/check-mock-seeds.py`; `--a11y` on both states.

## Commit

`feat(maquette-l17): the media sheet's cross-seed block is the administrator's alone`
