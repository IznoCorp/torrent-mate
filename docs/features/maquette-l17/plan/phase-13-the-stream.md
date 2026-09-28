# Phase 13 — The stream

**No OPEN question.** The two engine events are claimed whatever the operator ruled; OPEN 8 decided what the badge
does with a refusal, not whether the events move a surface. **F59 adds a THIRD event**: a search's own outcome, so
a `queued` pair (phase 15's act) is seen to resolve within the same visit.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.** `sed -n 130,148p frontend/maquette/design/src/features/acquisition/live.ts` →
  `acquisitionLiveExemptions.types` lists `RatioMeasured`, the three `SeedObligation*`, **`CrossSeedInjected`,
  `CrossSeedRejected`** and `TrackerAuthFailed`; the file is **148** non-blank lines. L16 claims the four ratio
  names; this phase claims the two cross-seed names and leaves `TrackerAuthFailed`. `grep -cve '^[[:space:]]*$'` →
  `app/live-updates.ts` **116**, `lib/live-rule.ts` **82**, `harness/fanout.py` **486** (R91's per-rule and
  exemption holds), `mocks/stream.ts` **399 of 400** — **no line of this phase goes into `stream.ts`**: an event is
  emitted by a named state or a rule through `window.__mocks.emit`.
- **Points ≈ 10.** `features/trackers/live.ts` (L16's file) gains the three rules ≈ 25 lines 2½; the exemption
  edited ≈ 12 lines 2½; R91 re-aimed 1; R-L17-h 3; two refresh keys 1 → 10 (the registration is L16's line).
- **Found.** The registers disagree on whether the two engine events reach the stream (DESIGN fact 10, demand I):
  the mock relay emits them regardless; the demand is the backend brief's. **The search-outcome event has no engine
  counterpart today** — the maquette's own invention, marked as such, standing in for what the backend must emit
  once `searchCrossSeed` (phase 14) exists.

## Red today

**R-L17-h — the events are claimed, injection, refusal and search-outcome** (DESIGN § 5): `CrossSeedRejected`,
`CrossSeedInjected` and the search-outcome event, each emitted through `window.__mocks.emit`, move the mark's rows
and the badge WITHOUT a refetch; a `queued` pair resolves within the SAME visit; none of the three names remains in
`acquisitionLiveExemptions`. Red: the exemption holds two of them and no surface moves.

## Move

1. The three rules in `features/trackers/live.ts`, each refreshing the summary read and the downloads read and
   nothing else — **never a third, media-block key: held for L18, F25**.
2. The two engine names leave `acquisitionLiveExemptions`; its `because` is rewritten to the authentication event
   that remains.
3. R91's fan-out reads the new rules; R-L17-h written first, seen red.

## Mutation

Commit first: leave a rule out of `features/trackers/live.ts` → the state stops moving and R-L17-h falls; put a
name back in the exemption → falls; make a rule refresh every key → the « nothing else » hold falls; leave a
`queued` pair unresolved past the visit → the same-visit hold falls.

## Register

**B-145's reading half** is what this phase serves; the row is annotated at the close (phase 18), never edited here.

## Oracle and gate — done when

Oracle: none — a live rule moves no rectangle. Gate: per INDEX « Gates »; the R91 fan-out under `--contracts`.

## Commit

`feat(maquette-l17): a cross-seed injection, refusal or search outcome moves the page it belongs to`
