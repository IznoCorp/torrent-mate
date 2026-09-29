# Phase 12 — The sheet says what it is (DOIT-11)

**No STOP C.** A PROOF over the media sheet as it stands.

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `grep -n "year\|trailer" frontend/maquette/design/src/features/media/media-hero.tsx | head` → the
  year and its failure words (lines **69–74**), the trailer row (**149**); `grep -cv '^\s*$'` on `media-hero.tsx`,
  `media-details.tsx`, `harness/states/media.ts` → **181, 184, 61**; `git grep -ln "synopsis" -- frontend/maquette/harness` → `content.py` (R63, the library rows),
  `priming.py` (R119, the sheet's parts IN FLIGHT), `resolution_card.py` — none reads the sheet's fields at rest.
- **Points ≈ 4.** R-L24-h 3 — one hold per field of DOIT-11 (title, year, synopsis, director, trailer; seasons,
  episodes, status for a series), each accepting the field OR its failure words; the report 1.
- **Readers.** `harness/gallery.py` (the path to the sheet) — untouched.

## Red today

Read at the opening; if every field is drawn, the red is the mutation's.

## Move

The rule only.

## Mutation

Drop the director row → its hold falls by name.

## Register

The map's DOIT-11 « unproved » content half is proved; proposed at phase 19.

## Oracle: states that diverge, declared by name

None.

## Commit

`test(maquette-l24): the media sheet says what the medium is`
