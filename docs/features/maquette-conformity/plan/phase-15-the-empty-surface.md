# Phase 15 — The empty surface (D.1 #10)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "noInfo\(|runs/empty" -g '*.ts' -g '*.tsx' frontend/maquette/design/src` → `noInfo` at
  `features/media/season-list.tsx:231, 243, 247, 251` (the report's four), `media-details.tsx:148`,
  `media-hero.tsx:171, 177`, `media-cast.tsx:107, 109`; the runs' empty `guidance` at
  `features/system/run-list.tsx:161` (moved by phase 2 — re-taken).
- **Points ≈ 7.** Every empty `noInfo` onto `emptyNote` (≈ 12 lines, 3; a `noInfo` wrapping a skeleton is a LOADING
  place and stays — said in the commit); the runs' empty → `emptyNote` (1); R-conformity-h (3).
- **Readers.** `audit.py`, `screen_addresses.py`, `priming.py` read `no-info` — the part is kept.

## Red today

R-conformity-h on `runs-empty` and `mediasheet-no-trailer`: the empty part is `emptyNote` — falls.

## Mutation

Restore `noInfo` on one site → falls by name.

## Oracle: states that diverge, declared by name

Every media sheet state and `runs-empty` (built by script).

## Commit

`refactor(maquette-conformity): an empty place is the empty note, everywhere`
