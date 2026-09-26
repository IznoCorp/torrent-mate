# Phase 13 — The stream

**Reads no OPEN question.** The two events are claimed whatever the operator rules; OPEN 8 decides what the badge does with them, not whether they move a surface.

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `sed -n 130,148p frontend/maquette/design/src/features/acquisition/live.ts` → `acquisitionLiveExemptions.types` lists `RatioMeasured`, the three
  `SeedObligation*`, **`CrossSeedInjected`, `CrossSeedRejected`** and `TrackerAuthFailed`, with a `because` that says the ratio and cross-seed events belong to surfaces with no page
  yet; the file is **148** non-blank lines. L16's phase 10 claims the four ratio names and leaves these three; this phase claims the two cross-seed names and leaves
  `TrackerAuthFailed`. `grep -cve '^[[:space:]]*$'` → `app/live-updates.ts` **116** (`<feature>LiveRules` imported per feature), `lib/live-rule.ts` **82**,
  `harness/fanout.py` **486** (R91's per-rule and exemption holds), `mocks/stream.ts` **399 of 400** — **no line of this phase goes into `stream.ts`**: an event is emitted by a named
  state or a rule through `window.__mocks.emit` (`sed -n 225,232p frontend/maquette/design/src/mocks/stream.ts`).
- **Points ≈ 10.** `features/trackers/live.ts` (L16's file) gains the two rules ≈ 20 lines new 2; the exemption edited (two names leave, `because` rewritten) ≈ 12 lines edited 2½;
  R91 re-aimed at the two rules 1; R-L17-h 3; the registration is L16's line (already in `app/live-updates.ts`), so ≈ 0 → 8½. **`stream.ts` untouched.** Two events, three surfaces: add 1½ for the
  three refresh keys (the summary, the section, the media block) → 10.
- **Found.** The registers disagree on whether the events reach the stream (DESIGN fact 10, demand I): the maquette's mock relay emits them regardless; the demand is the backend brief's.

## Red today

**R-L17-h — the events are claimed** (DESIGN § 5): `CrossSeedRejected` emitted through `window.__mocks.emit` moves the roster's line, the section's rows and the badge WITHOUT a refetch;
`CrossSeedInjected` the same; neither name remains in `acquisitionLiveExemptions`. Red: the exemption holds both and no surface moves.

## Move

1. The two rules in `features/trackers/live.ts`, each refreshing the summary read and the section (and the block's key on `/media/…`) and nothing else.
2. The two names leave `acquisitionLiveExemptions`; its `because` is rewritten to the authentication event that remains.
3. R91's fan-out reads the new rules; R-L17-h written first, seen red.

## Mutation

Commit first: leave one rule out of `features/trackers/live.ts` → the state stops moving and R-L17-h falls; put a name back in the exemption → falls; make a rule refresh every key → the
« nothing else » hold falls.

## Register

**B-145's reading half** is what this phase serves; the row is annotated at the close (phase 19), never edited here.

## Oracle: states that diverge, declared by name

None — a live rule moves no rectangle.

## Gate

Per INDEX « Gates »; the R91 fan-out under `--contracts`.

## Commit

`feat(maquette-l17): a cross-seed injection or refusal moves the page it belongs to`
