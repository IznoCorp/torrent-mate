# Phase 5 — The gesture answered

**STOP C — Q1 and Q3 (DESIGN § 7).** The confirmation's own copy names what Q1 rules eligible, and whether a
doomed call is stopped BEFORE it fires (Q3 reading B) or only answered afterwards with a reason (reading A)
changes this phase's own move in a way § 4's rule `c` and `d` both depend on. **The refusal-side call's own gate
is NOT one of them**: `trackers.upload` is settled (DESIGN § 0.2), and R-L23-f's second half is proven against
whichever role holds it, per phase 2's own seed. This is the plan's LARGEST phase (12 points) precisely because it
is where most of what remains open converges on one gesture's own act.

**Opening measure — PROJECTED, re-taken at this phase's real opening.**

- **Commands.** The confirmation primitive (`ui/` — this codebase's existing confirm-dialog component, the SAME
  one L16's « Retirer de qBittorrent » and L17's own switch-off confirmation already use) is read, never
  reinvented; `features/trackers/live.ts` (L17's own) is where a `queued` pair already resolves within the same
  visit for a search's own outcome (F59) — this phase reuses that resolution path for an upload's own outcome
  too, never a third one.
- **Points ≈ 12.** The confirmation, naming the tracker and the files (≈ 20 lines new) 2; the call, answered on
  the network, never messaged without one (R-L23-c, one new rule + mutation) 3; the visible « en file » state,
  reusing the search act's own queued-resolution mechanism (1 new named state, reusing a seed row) 1; the
  refusal's own reading — the two new codes' sentences drawn on an `error` row exactly as L17's twelve already are
  (R-L23-a, one new rule + mutation) 3; the right's refusal side, `403` when forced (R-L23-f's second half, one
  new rule + mutation, shared with phase 4's offer-side proof) 3.
- **Found.** Nothing new to find — every mechanism this phase calls on (the confirm primitive, the queued
  resolution, the refusal reading) already exists, drawn by L16, L17 or earlier lots; this phase's own content is
  wiring one more act through all three, never building any of them again.

## Red today

`torrents-cross-seed-upload-confirm`, `-queued`, `-refused-creation`, `-refused-publish` exist nowhere; every hold
below is red for the reason every new state on this tree already is, needing no mutation to be seen so.

## Move

1. Confirmation: names the tracker, that the medium's own files will be packaged and published, and — if Q1
   rules a broader eligibility (reading B) — the medium's OWN eligibility fact, read from wherever that reading's
   own surface lives (§ 7 Q1's cost note in `plan/INDEX.md`).
2. On confirm: call `uploadCrossSeed`; answer a visible « en file » (`torrents-cross-seed-upload-queued`), never
   « occupé »; resolve within the SAME visit via the search act's own event-driven mechanism (F59), never a poll.
3. On success: the pair reads `active`, dated, on the SAME row (no new row, no new state beyond what phase 4
   already named as reachable).
4. On refusal: the pair reads `error`, drawing `creation_failed`'s or `publish_failed`'s own sentence — the SAME
   reading discipline L17's own `torrents-cross-seed-refused` state already carries (its kind of trouble, the
   candidate's tracker — here, the target tracker itself — and the source medium), never a bare code.
5. Forced by hand, without the right: `403`, the reason naming the missing right (L18's own reserved-place
   sentence table, reused, never retyped).

## Mutation

**R-L23-c** — message the « en file » without calling → the network hold falls, naming the operation.
**R-L23-a** — draw the code instead of the sentence on a refused row → falls. **R-L23-d** — confirm without
naming the tracker → falls. **R-L23-f** (refusal half) — force the call as a non-holder and answer 200 → the
refusal hold falls, naming the identity.

## Register

Nothing new filed here — the operation and the two codes were filed in phase 1; this phase only proves them
answered.

## Oracle: states that diverge, declared by name

`torrents-cross-seed-upload-confirm`, `torrents-cross-seed-upload-queued`,
`torrents-cross-seed-upload-refused-creation`, `torrents-cross-seed-upload-refused-publish` — four NEW states,
recorded by the oracle as new, proving nothing about them (D8's own rule for a wholly new surface); no EXISTING
state diverges.

## Gate

Per INDEX « Gates »; `--a11y` at 0 over the four states this phase adds; every mutation above replayed and named.

## Commit

`feat(maquette-l23): the upload gesture is confirmed, called and read on both outcomes`
