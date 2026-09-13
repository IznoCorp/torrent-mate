# Phase a·6 — The identity demand

A CONVERSION: the contract declares fields that nothing reads yet. `ids` and `poster` are added to
seven list schemas and `title` to `MediaSheet`; the types, the seeds and the demands register are
regenerated (DESIGN § 5.2; § 3, row 15).

## The proof FIRST

- `npm run generate-contract-types` regenerates the generated types, which the size ledger's
  GENERATED entry already exempts.
- `python3 scripts/compare-contracts.py --write`, then `--check` exit 0. The demand appears in
  `docs/reference/frontend-backend-demands.md` § 2 on regeneration, because the register is COMPUTED
  from the contract and is never written by hand.
- `python3 scripts/check-mock-seeds.py` exit 0 on every arm. The byte-level arms were not run by the
  design (DESIGN § 5.1), so they are run here and their output goes in the report.
- **The oracle**: zero divergence. No surface reads the new fields in this phase, so a divergence
  is STOP B.
- **Hold counts**: `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  no movement.

## The move

The contract `frontend/maquette/contract/openapi.json` gains exactly these fields (DESIGN § 5.2):

| Operation | Schema | Added |
| --- | --- | --- |
| `readAcquisitionQueue`, `readStaging` | `QueueCard` | `ids`, `poster` |
| `readLibraryItems` | `LibraryItem` | `ids`, `poster` |
| `readLibraryRecent` | `LibraryRow` | `ids`, `poster` |
| `readLibraryIncomplete` | `IncompleteShow` | `ids`, `poster` |
| `readFollows` | `Follow` | `ids` **required**, `poster` |
| `searchProviders` | `SearchResult` | `ids`, `poster` |
| `readSuggestions` | `Suggestion` | `ids`, `poster` |
| `readMediaSheet` | `MediaSheet` | `title` |

- **The field types.** `ids` is the existing `ProviderIds`. It is nullable everywhere except
  `Follow`, where the operator's B-366 ruling (« le suivi sans fiche n'est pas un état possible »)
  makes it required. `poster` is a URL or null.
- **Seeds are projected, never hand-edited.** `scripts/build-mock-seeds.py` projects `ids` and
  `poster` by a title join from `media-sheets.json` and `posters.json`, and the handlers pass the
  fields through.
- **A follow that joins no sheet cannot be seeded.** R156 (`follow_has_sheet.py`) holds that no such
  follow exists today, so the builder refusing one is STOP D, not a nullable escape.
- **Handlers that BUILD a follow.** The phase re-takes every mock handler that creates a `Follow`
  (the follow verb from a search result or a suggestion). Each must carry the `ids` of its source.
  A source with `ids: null` is the case c·7 makes unrepresentable, and it is reported here, not
  resolved.
- **Out of scope.** No product reader switches in this phase: each surface phase (a·9–a·16) switches
  its own readers. No drawing and no engine line changes.

## Gate

Per INDEX « Gates ». In addition, `compare-contracts.py --check` and `check-mock-seeds.py` exit 0,
with their output in the report.

## Commit

`refactor(maquette-l13): the list schemas declare the provider identity and the poster`
