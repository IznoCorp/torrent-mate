# Phase 3 — The mocks that move

**STOP C — Q4 (DESIGN § 7).** What the mock answers on a REFUSAL depends on whether the backend is asked to
pre-check tracker rules (reading B) or only to answer a plain refusal with its reason (reading A). This phase does
not open until Q4 is ruled — its own « Move » below is written for reading A, the D7 default, and is amended in
one line, never redrawn, if B is chosen instead.

**Opening measure — PROJECTED, re-taken at this phase's real opening.**

- **Commands.** `mocks/handlers/trackers.ts` (L17's own file, or a `mocks/handlers/cross-seed.ts` if L17's own
  400-line measure at ITS opening moved the cross-seed handlers there — L17's plan names this as its own STOP D,
  not yet resolved on this tree) is where `searchCrossSeed` and `cutCrossSeed` already move the seed by the time
  this phase opens; `uploadCrossSeed` is added BESIDE them, in the same file, never a third file for one more
  handler.
- **Points ≈ 8.** The handler, new (2); its success branch moving the seed's pair to `active` (≈ 8 lines edited)
  1½; its two failure branches, one per new code (≈ 10 lines edited) 2; the summary read's derived counts
  re-checked to still agree after the move (no new code, a re-run of an existing derivation) 1; the report
  1½.
- **Found.** Nothing yet to find — the mock is invented, exactly as L17's own cross-seed handlers were, and this
  phase's job is to make ONE more verb move the SAME seed L17's phase 3 already made move.

## Red today

None — a mock has no rule of its own.

## Move

1. `uploadCrossSeed(infoHash, tracker)`: on the scenario's chosen outcome (the seed's own dial, extended by phase
   2), moves the pair to `active` with `injectedAt` set (success), or to `error` with `creation_failed` or
   `publish_failed` set (failure) — the SAME single call, in the SAME render, that `cutCrossSeed` already answers
   with for its own write (L17 fact 7's own precedent: a handler moves `raw` and every projection together).
2. Under Q4 reading A: a refusal never reaches a SECOND check — the mock answers the seeded outcome directly, no
   pre-validation branch. Under reading B (if ruled before this phase opens): a rule-check branch answers a
   REFUSED-BEFORE-CALLING shape instead, named `tracker-rule-refused`, and this phase's own move gains one line
   for it.
3. Confirm the tracker summary read's `crossSeed.failed` count still sums correctly from the SAME rows after the
   move — no new derivation, a re-run of L17's own (phase 6 is where the SLOT itself is proven counted; this
   phase only confirms the move does not break the sum).

## Mutation

None — the handler exists nowhere to mutate yet; a later reader mutates it against the real code once this phase
has actually landed.

## Register

Nothing new — the operation was filed in phase 1; this phase only makes it answer.

## Oracle: states that diverge, declared by name

None — a mock moves no rectangle by itself; the surfaces that read it (phases 4–5) are where a rectangle exists.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`.

## Commit

`feat(maquette-l23): the upload operation moves the seed, success and both failures`
