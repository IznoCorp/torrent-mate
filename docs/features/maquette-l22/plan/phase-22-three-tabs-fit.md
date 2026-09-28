# Phase 22 — Three tabs and a lit badge fit, at 390 and 369 px (B-557)

**Born 2026-09-27 from the operator's report** on tm-design (~15:05, main `a6fb6fc1d`, four tabs): « Menu d'onglets:
cassé voir capture » — « À traiter » truncated, its badge clipped, « Découvrir » cramped. It is A4 of round A22, which
19-bis-b already repaired by taking « Découvrir » out of the tabs; **this phase repairs nothing — it PROVES** (the
steward, adopting the auditor's precision).

**Opening measure (estimate — given to the steward at the opening):**

- R206 (R-L22-e, the tabs' labels) reads three tabs at 390 px. It gains: the same at **369 px**, with « À traiter »'s
  badge LIT with the longest plausible count, each label and its badge unclipped (`scrollWidth ≤ clientWidth`, the
  badge's box inside its tab's box), no horizontal overflow.
- **Points ≈ 5**: two holds on R206 with a mutation 3; the count's seed or override 1; BUGS.md 1.

## Red

Against main's four tabs (the operator's screenshot): the badge clipped. On this branch the holds are expected GREEN;
the proof that they bite is the mutation.

## Mutation

With the commit made first: a fourth tab put back (or a label lengthened past its budget) → R206 falls at 369 px.

## Commit

`test(maquette-l22): three tabs and a lit badge fit at 390 and 369 px`
