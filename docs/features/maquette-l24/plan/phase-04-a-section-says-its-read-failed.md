# Phase 4 — A section says its read failed (S2)

**No STOP C.**

**Opening measure (2026-09-29, on `e65130ab1`):**

- **Commands.** `grep -n "= \[\] } = use" frontend/maquette/design/src/features/system/page.tsx` → lines **44, 46,
  48, 49, 50**: every list defaults to empty on a failed read. `grep -cv '^\s*$' …/features/system/page.tsx` → **129**.
- **Points ≈ 9.** The rule R-L24-c 3; `page.tsx`: one derived row per failed section (≈ 10 lines edited) 2;
  `fr.json` « indisponible » and one secondary line per section 1; three named states, re-using phase 3's scenario
  (`system-disks-unavailable`, `system-index-unavailable`, `system-dependencies-unavailable`) 3.
- **Readers.** R67 (`harness/machine.py:112–113`) reads the disks and index rows from the cache; its holds must stay
  green over the healthy states — the new rows are drawn only when the read has FAILED.

## Red today

R-L24-c over `system-disks-unavailable`: the « Disques » heading draws over no row — `0 alert row(s)`.

## Move

Each section reads its query's error; a failed one draws one `Fact` row (`tone: alert`), the others unchanged.

## Mutation

`sh scripts/mutate.sh frontend/maquette/design/src/features/system/page.tsx "<the failed row dropped>"
frontend/maquette/harness/<R-L24-c's file>.py` → the named `FAIL` on the disks hold.

## Register

None.

## Oracle: states that diverge, declared by name

The three new states (new, recorded). `system` and `system-outage` at zero.

## Commit

`feat(maquette-l24): a Système section whose read failed says so`
