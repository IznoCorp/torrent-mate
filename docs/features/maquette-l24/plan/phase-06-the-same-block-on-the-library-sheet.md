# Phase 6 — The same block on the Médiathèque sheet (S1)

**No STOP C.** Ruled OPEN 1 = C: once the medium leaves Acquisition, the same block reads on its Médiathèque sheet.

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -cv '^\s*$' frontend/maquette/design/src/features/media/{media-screen.tsx,media-library-facts.tsx,media-details.tsx}`
  → **330, 245, 184**; `git grep -ln "features/acquisition/" -- frontend/maquette/design/src/features/media` →
  **`season-grab.ts`** alone — a cross-feature import already stands; `grep -cv '^\s*$' …/harness/states/media.ts`
  → **61**.
- **Points ≈ 7.** R-L24-b 3; the media sheet imports the block and draws it under its facts (≈ 8 lines edited) 2;
  `media-sheet-decision`, re-using phase 2's shelved row 1; the report 1.
- **Readers.** R-L24-h (phase 13) reads the same sheet's fields later — its list is built from this phase's DOM.

## Red today

R-L24-b over `media-sheet-decision`: the Médiathèque sheet draws no block — `0 block(s)`.

## Move

The same component, the same derivation, the same words: the medium's decision found by its choice's provider and
id; no second module, no retyped word (§ 13).


## Register

None.


## Commit

`feat(maquette-l24): the Médiathèque sheet reads the same decision`
