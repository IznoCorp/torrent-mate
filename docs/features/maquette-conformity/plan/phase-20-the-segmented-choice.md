# Phase 20 — One segmented choice: `segmentSmall` into `viewSwitch` (D.1 #14, the operator's OPEN 4 = A)

**Ruled 2026-09-29** (`/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` § Q4, verbatim « A »):
`segmentSmall` merges into `viewSwitch`, which gains a « text » size; its three uses are rewired; the acquisition
feature's declaration goes. A conversion.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "segmentSmall" -g '*.ts' -g '*.tsx' frontend/maquette/design/src` → declared at
  `features/acquisition/variants.ts:101`, used at `features/acquisition/add-screen.tsx:256, 344` and
  `app/drawer.tsx:163` — the FRAME importing a feature's variant (`app/drawer.tsx:48`); `viewSwitch` /
  `viewSwitchButton` at `ui/variants/controls.ts:369–372` (**397 / 400** non-blank lines — STOP D near: the size
  variant lands only if phase 6 moved lines out of that file; otherwise the two variants move with it, said).
- **Points ≈ 9.** A `size: { icon, text }` on `viewSwitch` / `viewSwitchButton` (≈ 8 lines, 2); three uses rewired
  (≈ 8 lines, 2); `segmentSmall` and its import from `app/` gone (1); `alignSelf` inline style at `add-screen.tsx:344`
  → the variant (1); R-conformity-o (3).
- **Readers.** `appearance.py` and the drawer rules read `segment-small` — the part is kept.

## Red today

R-conformity-o on `acq-add-results`, `drawer-navigation` and `lib-grid`: every segmented choice is `viewSwitch`'s
drawing, one geometry per size; `app/` imports nothing from `features/*/variants.ts` (a HOLD, read over the source
as `common.design_source()` reads it) — falls.

## Mutation

Re-import `segmentSmall` into `app/drawer.tsx` → falls by name.

## Oracle: states that diverge, declared by name

None expected — the same drawing, one declaration. A divergence is STOP A.

## Commit

`refactor(maquette-conformity): one segmented choice, viewSwitch, with a text size`
