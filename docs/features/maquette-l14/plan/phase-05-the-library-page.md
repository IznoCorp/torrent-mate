# Phase 5 — The library page · **conversion**

**Owns**: `features/library/page.tsx` 613 → under 400. **Constitution**: §15, §12 (P24 survives the
cut: `LibraryList` moves with its `VirtualRows` call and its sentinel).

## What changes

| File                  | Carries                                                                                                                                                                                                  |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `library-head.tsx`    | `LibraryHead` — the lenses, the search field with its native handler, the pills, the mode switch                                                                                                         |
| `library-list.tsx`    | `LibraryList` whole — the listing, the sentinel effect, the paging registration, the windowed rows, the footer                                                                                           |
| `library-count.tsx`   | `CountLine` and `SortLabel`                                                                                                                                                                              |
| `library-empty.tsx`   | `EmptyLibrary`                                                                                                                                                                                           |
| `incomplete-lens.tsx` | the « Incomplets » body (the note, the grid or the list of `INCOMPLETE`), with `INCOMPLETE_COUNT` beside it — the count line above it stays in the page, which reads the same constant through an export |

`page.tsx` keeps `LibraryPage`: the three lenses' composition, the count lines, the notes.
`GRANDFATHERED["features/library/page.tsx"]` is removed in the same commit. **`drawKey` is NOT
touched here** — that is phase 7's behaviour change; this phase moves `drawKey={version}` as it is.

## Definition of done

- `grep -cve '^\s*$' frontend/maquette/design/src/features/library/page.tsx` → **< 400**
  (estimate ~110); no new file over 250.
- `python3 scripts/check-frontend-boundaries.py --arm size` → 3 at or over the ceiling.
- The oracle: zero divergence across the library states. **R117** (`harness/virtual.py`) green,
  **R94** (scroll memory) green, `library_load.py`, `library_sort.py`, `selection.py`, `filters.py`
  green in the contracts run or run alone.
- `run.sh --contracts` green; `npm run check` green.
- One commit: `refactor(maquette-l14): the library page — five files beside it, nothing moved`.
