# Phase 12 — A filling disk on the badge (S2)

**No STOP C.** Ruled OPEN 2 = A (2026-09-29): a disk « bientôt plein » and a library-index anomaly count in the
menu button's badge (Système).

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -n "_KEY = " frontend/maquette/design/src/features/system/badge.ts` → **LOCKS, SERVICES,
  DEPENDENCIES** — the badge reads three answers, no disk, no index; `grep -cv '^\s*$' …/badge.ts` → **83**; the
  seed already carries a filling disk (`disks.json`, « Disk2 — bientôt plein »).
- **Points ≈ 5.** R-L24-m 3; two terms in `systemBadge()` (≈ 8 lines) 1; `system-disk-filling` re-using the seed 1.
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
