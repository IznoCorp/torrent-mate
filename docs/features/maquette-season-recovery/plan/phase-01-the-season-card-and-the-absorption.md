# Phase 1 — « En cours »: the season's card and the absorption (S2, S3, S6's card)

**DECIDED 8 = A** (DESIGN § 5, 2026-09-30): the card's « auto » in its subtitle.

**Opening measure** (taken on `9234341fc`; re-taken at the real opening):
the contract's `QueueCard` → 13 fields, none of `season`, `episode`, `absorbedBy`, `trigger`; the grab answers `201`
only, no `reused` (DESIGN § 2); `grep -n "found === undefined" frontend/maquette/design/src/mocks/handlers/acquisition-verbs.ts`
→ **209** (the one-off guard); `grep -n "^export function inFlightCards\|^function sameMedium"
frontend/maquette/design/src/features/acquisition/arrival-slots.ts` → **96**, **73**; Silo: `pending`, S03 7 aired /
6 owned, no card in any queue list (DESIGN § 0.1 item 8).

## What changes

1. **The data** (DESIGN § 2; DECIDED 5, 6): `QueueCard` gains `season`, `episode`, `absorbedBy`, `trigger`, each
   nullable, each description saying what the engine holds and what it is asked (SR1, SR5); the grab's `200`
   (`reused`) declared; `compare-contracts.py --write`, then `--check`. Seeds (the DENSE world): « Silo » · `S03`
   (requester `follow`, `trigger` `manual`), « Silo » · `S03E07` (`absorbedBy` the season card), each declared in
   `frontend/maquette/fixture-register.json`; an automatic recovery's card POSED, never seeded. Mocks:
   `grabSeasonForFollow` queues ONE season card for a followed series too, a second ask queues nothing and answers
   `reused`; the absorption writes `absorbedBy` on every in-flight or takeable card of that medium and season.
2. **The derivation moves to `lib/`** (DESIGN § 1.7): `features/acquisition/arrival-slots.ts` WHOLE into its own
   `lib/` module, the five importers rewired, unchanged in behaviour, before anything is extended.
3. **The absorption** (S3; DECIDED 5): the derivation drops every card whose `absorbedBy` names a card on its way;
   « En cours » and its count read that one answer. No label is compared.
4. **The season's card** (S2; DECIDED 6): the acquisition card unchanged in anatomy; « S03 · auto » as its subtitle
   when `trigger` is `automatic`, nothing more when `manual`, nothing when `null`.
5. **The card's end** (S6): closed short (the fallback's episodes ordinary cards, not absorbed), abandoned (the card
   and the mark go, nothing revived).
6. **Its register rows** (order 57): « a season asked of a FOLLOWED series draws no card and no mark », « « En cours »
   draws an episode card beside the recovery of its season » (DESIGN § 6).

## Acceptance — red first on the old code, then green

- **R-season-recovery-a** (exclusive in « En cours ») — red on `season-recovery-absorbs-episode`;
  **R-season-recovery-e** (one card per season) — red on a second ask; **R-season-recovery-g**, its card half — red on
  `season-card-automatic`.
- Re-aimed OUT LOUD: R224 (`now_holds_in_flight.py`, its world now holds a season card).
- Named states: every S2 id; `season-recovery-before-ask`, `season-recovery-absorbs-episode`;
  `season-recovery-closed-short`, `season-recovery-abandoned` — declared beside the « En cours » states
  by name.
- Walked by finger from `season-recovery-before-ask`: the follow panel → « Récupérer la saison 3 » → the toast → the
  `S03E07` card gone, « Silo · S03 » at the top of « En vol », its count moved by zero.

## Commit

`feat(maquette-season-recovery): one card for a season's recovery, and the episodes it covers leave « En cours »`
