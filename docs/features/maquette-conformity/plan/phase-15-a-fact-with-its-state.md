# Phase 15 — A fact with its state at the row's end (D.1 #6)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "keyValueRow|statusDot" frontend/maquette/design/src/features/media/media-library-facts.tsx
  frontend/maquette/design/src/features/library/page.tsx` → « ● oui / non » at `media-library-facts.tsx:118–122,
  127–132, 155–160, 217–220`; the Incomplets count line's `statusDot` + inline `b` at `features/library/page.tsx:51–54`,
  its `marginLeft: 12` at `:89`.
- **Points ≈ 8.** Four rows onto the chip at the row's end (≈ 16 lines, 3); the count line's count part (1); the
  inline styles go (1); R-conformity-g (3).
- **Readers.** `acted_surface_redraws.py`, `requester_line.py`, `one_ladder.py` read `status-dot` — on other
  surfaces; the rule's opening re-reads them against this diff.

## Red today

R-conformity-g on `mediasheet-movie` and `mediasheet-series`: the ownership row's state is a chip at the row's end,
never a dot and a bare word — falls.

## Mutation

Put the dot and the word back on one row → falls by name.

## Oracle: states that diverge, declared by name

Every media sheet state drawing the library facts, and `lib-incomplete` (built by script).

## Commit

`refactor(maquette-conformity): a fact's state is the chip at its row's end`
