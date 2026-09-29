# Phase 13 — One completeness (NE-DOIT-PAS-1, § 13)

**No STOP C.** A SOURCE change: the season figures move to the operation the engine answers, nothing drawn moves.

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `grep -rn "completeness\"" frontend/maquette/design/src/features frontend/maquette/design/src/mocks`
  → **nothing** before phase 1; `grep -cv '^\s*$'` on `features/media/media-library-facts.tsx`,
  `features/acquisition/follow-facts.ts`, `features/media/queries.ts`, `features/acquisition/queries.ts` →
  **245, 160, 126, 356**.
- **Points ≈ 9.** R-L24-i 3; `readFollowCompleteness` read beside the sheet's own queries (≈ 10 lines new) 1; the
  sheet's season figures and the follow sheet's read it for a followed medium (≈ 25 lines edited) 5.
- **Readers.** `followsheet-complete`, `followsheet-gaps` and the media sheet's states read the figures; the oracle
  must read them UNCHANGED — the seed of phase 2 carries the same figures.

## Red today

R-L24-i: the two surfaces derive the figures locally — `0 read(s)` of the operation.

## Move

One query, two readers; a medium nobody follows keeps its sheet's own figures, said so in the module's comment.

## Mutation

Compute the follow sheet's figure locally again → the agreement hold falls by name.

## Register

The map's NE-DOIT-PAS-1 and DOIT-11 « complétude par saison » halves; proposed at phase 19.

## Oracle: states that diverge, declared by name

None — a source change is a conversion; a divergence is STOP A.

## Commit

`refactor(maquette-l24): the season figures read the one completeness`
