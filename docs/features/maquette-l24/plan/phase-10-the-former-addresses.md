# Phase 10 — The former addresses answer not-found (S4, PROOF)

**RULED OPEN 9 = A + the no-backward-compatibility PRINCIPLE** (operator, 2026-09-29,
`docs/features/maquette-l24/rulings-2026-09-29.md`, verbatim « A, pas de gestion de rétro-compatibilité ! »): the new
version handles NO backward compatibility of former addresses or links — no alias, no redirect (precedents
`/arrivals`, the French addresses of OPEN 4 = A). **S4 dies as a surface**: no table, no five states, no code —
`destinationOf` already answers the not-found page for every path outside `PAGE_PATHS`, which is every former
production address. `/media?decision=<id>` is not a former address (`/media` exists today): its id is dropped like
any unknown dial (D1), same as `/media?media=<id>`.

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -n "\"/control\|\"/pipeline" frontend/maquette/design/src/lib/addresses.ts` → **nothing**;
  `grep -n "NOT_FOUND_PAGE)" …/lib/addresses.ts` → line **357**; `destinationOf` falls to `NOT_FOUND_PAGE` for
  anything outside `PAGE_OF_PATH` (`addresses.ts:361`) — measured true for `/control`, `/pipeline`, `/config`,
  `/medias`, `/systeme`, `/controle` today, with zero code added.
- **Points ≈ 4.** R-L24-d, one rule proving every dead production path answers `not-found` (no successor named
  anywhere) 3; the report ½. No table, no new state, no `lib/` module.
- **Readers.** R59 (`harness/back.py`) reads Back; the not-found state `not-found` is what every one of these paths
  already answers.

## Red today

Nothing is red: `destinationOf` already answers `not-found` for every dead path (measured above). R-L24-d is the
first PROOF over that fact — it does not exist yet, so it is red until written, green on the first run.

## Move

None. A PROOF phase adds a rule, not a behaviour.


## Register

None.


## Commit

`test(maquette-l24): a former production address answers not-found, proved`
