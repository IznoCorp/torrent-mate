# Phase 11 — A filling disk on the badge

**STOP C: OPEN 2.** Reading A (5 points): a disk « bientôt plein » and index anomalies count in the menu's badge.
Reading B: the phase is dropped, and phase 19 records it.

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `grep -n "_KEY = " frontend/maquette/design/src/features/system/badge.ts` → **LOCKS, SERVICES,
  DEPENDENCIES** — the badge reads three answers, no disk, no index; `grep -cv '^\s*$' …/badge.ts` → **83**;
  the seed already carries a filling disk (`disks.json`, « Disk2 — bientôt plein »).
- **Points ≈ 5.** The rule 3; two terms in `systemBadge()` (≈ 8 lines) 1; `system-disk-filling` re-using the seed 1.
- **Readers.** `menu-system-badge` and `menu-clear` (the named states of L22's badge rule) — `menu-clear` must stay
  at zero; if the seed's filling disk makes it non-zero, that is STOP D (a seed row to move, reported first).

## Red today

The badge over `system-disk-filling` reads the services' count only — `badge 0, expected 1`.

## Move

The two terms, each read on the fact's own `tone`, never on its words.

## Mutation

Drop the disk term → the filling hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

`system-disk-filling` (new), and `menu-system-badge` if its count moves — declared, never discovered.

## Commit

`feat(maquette-l24): a filling disk speaks on the menu's badge`
