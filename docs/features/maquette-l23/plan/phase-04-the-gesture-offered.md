# Phase 4 — The gesture offered

**STOP C — Q3 (DESIGN § 7).** Whether the gesture is drawn for every account holding `trackers.control`, or only
for one holding a NEW, narrower `trackers.upload`, decides which mock identity this phase proves the OFFER side
against (L18's own convention, « every rule proving a right names its two halves », DESIGN § 4 rule f). The
DRAWING itself (§ 2.3 of DESIGN) does not change; only the identity R-L23-f's offer-side hold reads against does.

**Opening measure — PROJECTED, re-taken at this phase's real opening.**

- **Commands.** `features/trackers/torrents-tab.tsx` (L17's own file, extending L16's) is where the per-pair
  mark's disclosure already draws « Chercher un cross-seed » on `noMatch`/`error`/`notSearched` rows by the time
  this phase opens (L17 DESIGN § 3.3) — this phase adds a SECOND act to the SAME disclosure, never a new row.
- **Points ≈ 8.** The act's markup, beside the existing one (≈ 15 lines new) 1½; the eligibility check reused
  (no new derivation, DESIGN § 4 rule b — a re-read of the SAME three-state gate `searchCrossSeed` already
  passes) 1; the exclusion check reused (S3-bis, L17's — an excluded pair offers neither act) ½; one new rule with
  its mutation (R-L23-b) 3; the two named states this makes real (`torrents-cross-seed-upload`, and the
  right-holder/non-holder pair proving R-L23-f's offer side — reusing an existing identity per Q3 = A, or a new
  seed row per Q3 = B) 1–2.
- **Found.** Nothing new — the row, the states and the exclusion mechanism are all L17's own, read, never
  redrawn; this phase's whole content is « one more act, same gate ».

## Red today

`torrents-cross-seed-upload` does not exist anywhere on `main`; the act it names is absent from every row, for
every identity — red for the same reason every other new state on this tree is red at its own phase's opening,
needing no mutation to be seen so.

## Move

1. Draw « Créer et publier un torrent » beside « Chercher un cross-seed », on the SAME three eligible states,
   absent on `active`/`stopped`/`trackerWithout` and on an excluded pair (S3-bis).
2. Gate the act's presence on the model's own right (`trackers.control` or `trackers.upload`, per Q3's ruling) —
   ABSENT from the DOM for a non-holder, never disabled.

## Mutation

**R-L23-b** — offer a pair reading `active` the act → the offer hold falls, naming the state it should have
refused. Offer it to a non-holder → the refusal-side half of R-L23-f (phase 5's own rule, proven together with
this phase's drawn absence) falls, naming the identity.

## Register

Nothing — no new demand, no new operation; this phase draws against what phase 1 already declared.

## Oracle: states that diverge, declared by name

None by the oracle over an EXISTING row — the disclosure's own height may grow by one act's worth of pixels; the
phase names this divergence explicitly if the oracle's reference (once re-recorded on THIS lot's own base) reads
it, per D8's own convention (a new act on an existing surface is a named, accepted divergence, never a silent
one).

## Gate

Per INDEX « Gates »; `--a11y` at 0 over the one new state this phase adds.

## Commit

`feat(maquette-l23): the upload gesture is offered, on the same gate as the search`
