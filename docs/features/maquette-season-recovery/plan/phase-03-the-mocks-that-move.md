# Phase 3 — The mocks that move

**STOP C: OPEN 1, 3, 5** (DESIGN § 5). Written for A, A, A. Under OPEN 5 = B the absorption writes no pointer and
phase 5 compares lines; under OPEN 1 = B `readJourney` keeps its title key; under OPEN 3 = B the season's journey
lists nothing absorbed (≈ 2 points less).

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.** `grep -n "found === undefined" frontend/maquette/design/src/mocks/handlers/acquisition-verbs.ts` →
  line **209** (the one-off guard); `grep -cv '^\s*$' frontend/maquette/design/src/mocks/handlers/acquisition-verbs.ts`
  → **233** non-blank lines; `grep -n '"readJourney"\|"readReleases"' frontend/maquette/design/src/mocks/handlers/acquisition.ts`
  → the two routes re-answered.
- **Points ≈ 13.** `grabSeasonForFollow` re-answered — ONE season card for a followed series too (requester
  `follow`), no second card on a second ask (the one-off's rule generalised), `reused` answered 1+2; the absorption —
  every in-flight and takeable card of that medium and season gets `absorbedBy`, the takeable ones leave (the
  engine's R5 closes `available`), `absorbedCount` counted from them 3; the ladder moves the season card to « rangé »
  under the existing stage verbs, the rows' owned count follows 2; `readJourney` keyed by the acquisition, the
  absorbed episode's stages frozen where they stood, the season's journey listing its absorbed (OPEN 3 = A) 2;
  `readReleases` unchanged (the picker filters, phase 10) 0; the handler's own test hold 1; the report 1; a new
  module if `acquisition-verbs.ts` crosses 300 non-blank lines 1.
- **Readers.** `harness/season_grab.py` (R125) and `harness/season_grab_unfollowed.py` (R158) read the answer's
  `absorbedCount` and the follow's `acquiring` — both still true; `harness/queued_ask_mark.py` (R138) reads `queued`
  — unchanged.

## Red today

None — the rules that read these answers open at phases 5, 6 and 8.

## Move

1. Lift the `found === undefined` guard for the queueing, not for the status write (the follow still reads
   « En cours d'acquisition »).
2. Absorb by the card's `season` / `episode` fields and provider identity — never by title alone.

## Mutation

None — the rules come with the surfaces.

## Register

None.

## Oracle: states that diverge, declared by name

None at rest (no drawing reads the new answers until phase 5); the handler's hold is the proof.

## Commit

`feat(maquette-season-recovery): a season asked of a followed series queues its card and absorbs its episodes`
