# Phase 15 — « Chercher un cross-seed »: the act

**OPEN 3 = A, unconditional.** **F45 narrows WHERE it is offered**: only on a pair reading « sans correspondance »,
« erreur de cross-seed » or « pas encore cherché » — never on `active`, `stopped` or `trackerWithout`, since nothing
is offered the engine would refuse to act on anyway (§ 17 point 1). **F59 closes the visit**: a queued search
resolves within the SAME visit, through phase 13's search-outcome event.

**Opening measure (2026-09-27, on `1d1282567` — the mark's rows are phase 6's):**

- **Commands.** `grep -n 'answered' frontend/maquette/design/src/mocks/answered.ts | head -3` → the network probe
  R-L17-i counts calls with. `sed -n 1,30p frontend/maquette/design/src/features/acquisition/follow-verbs.ts` → the
  shape of a verb registered against an element's `data-*` (`registerVerb`). `sed -n 240,248p
  frontend/maquette/design/src/mocks/handlers/pipeline.ts` → « a strict duplicate the interface may refuse — so it
  is answered 409 » — the one refusal the maquette's mocks allow already.
- **Points ≈ 10.** The button on a mark's row (offered on three of the six states only, a conditional read) ≈ 22
  lines new 2; the verb ≈ 15 lines new 1½; `fr.json` ≈ 6 lines ½; two states —
  `torrents-cross-seed-search`, `torrents-cross-seed-search-queued` — 2; R-L17-i, including the offer-only-where-
  eligible hold, 3; the search-outcome event's own consumption (reading phase 13's rule, resolving `queued` within
  the visit) ≈ 6 lines 1 → 10.
- **Found.** The act asks ONCE; the quota is drawn (« 212 recherches restantes aujourd'hui »); a throttled answer is
  a visible « en file », never « occupé »; a search that finds nothing is SEEN to end (F59), never left reading « en
  file » past the visit.

## Red today

**R-L17-i — « Chercher un cross-seed » is bounded, answered, visible and offered only where the engine allows it**
(DESIGN § 5): a tap asks ONCE (`answered()` counts one call); a throttling engine answers a visible « en file »; a
second tap on the same pair is the one refusal (a duplicate); the quota is drawn; the act is offered ONLY on
`noMatch`, `error` or `notSearched` rows. Red: no act.

## Move

1. « Chercher un cross-seed » on a mark's row, drawn only when its state is one of the three eligible ones; the
   verb; the states.
2. R-L17-i written first, seen red; the quota line in the mark's foot.
3. The search-outcome event resolving a `queued` pair, reading phase 13's rule.

## ~~Mutation~~

Commit first: let a double tap send two → R-L17-i falls; answer « occupé » on throttle → falls; hide the quota →
the quota hold falls; offer the act on an `active` row → the offer hold falls; leave a `queued` pair unresolved
past the visit → the same-visit hold falls.

## Register

—

## ~~Oracle: states that diverge, declared by name~~

`torrents-cross-seed` — a row gains its act — accepted with « L17 § 3.3: « Chercher un cross-seed » on a row ». Any
~~other divergence is STOP A.~~

## Gate

Per INDEX « Gates »; `--a11y` on the two states.

## Commit

`feat(maquette-l17): a cross-seed search on a row, once, bounded, visible, and resolved in the same visit`
