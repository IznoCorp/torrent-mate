# Phase 3 — The seeds, extracted and committed

## Scope

- `frontend/maquette/design/src/mocks/seeds/*.json` — one file per `served` family.
- `frontend/maquette/design/src/mocks/projections.json` — the key mapping, family by family.

## The projection

A rename and a regroup, never a re-derivation (D-L08-5). `t` → `title`, `f` → `secondaryLine`,
`c` → `category`. Every key of the source is either in the mapping or in that family's `dropped`
list with its reason. No value is recomputed, reformatted, parsed or split.

**The mapping is data, not code**, so the guard can read it and so a reader can see the whole
correspondence in one place rather than tracing it through a projector.

## The order

Smallest first, largest last. `ACCOUNT` (3 keys) before `SHEETS_RAW` (326 entries, 20 538 lines):
the projection's shape is settled on something a human can read whole, and the large families
then follow a rule that has already been exercised.

## What is not seeded, and it is named rather than discovered

The `derived*()` arrows, the getters and `TODAY` are not literals — they are computed at run time
against the scenario switch. They cannot be extracted, so they are not seeded; they become
declared scenario responses in phase 5 and are covered by R85, never by the seed guard. The
design's § 3 records this as an accepted limit.

## Done when

- Every `served` family in `register.json` has a seed file, and every seed file has a family.
- `projections.json` covers every key of every seeded family — mapped or dropped-with-reason.
- Re-extracting produces no diff.
- ACC-01, ACC-02, ACC-03 green.
