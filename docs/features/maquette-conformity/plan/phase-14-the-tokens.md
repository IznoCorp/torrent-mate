# Phase 14 — The tokens (D.1 #16)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n 'style=\{\{' -g '*.tsx' frontend/maquette/design/src/features frontend/maquette/design/src/app
  frontend/maquette/design/src/ui | wc -l` → **46** (phases 7, 8, 12 lower it — re-taken); off-scale first:
  `features/settings/page.tsx:143` (16), `features/acquisition/add-screen.tsx:381` (9, 16);
  `rg -n 'from "class-variance-authority"' -g '*.ts' frontend/maquette/design/src` → `features/system/variants.ts:8`
  and `ui/cva.ts`; `rg -n "'Geist'" -g '*.ts' frontend/maquette/design/src/features` → `features/settings/variants.ts:148`.
- **Points ≈ 13.** Inline `style` onto steps, the off-scale ones first (≈ 40 lines, 8); `text-<tone>` → `text-<tone>-text`
  on text in feature variants (2); `ui/cva` import (1); the `'Geist'` literal goes (1); R-conformity-l (the count held
  at its new floor) (1). Above 15 at the opening: cut by directory, the orchestrator told.

## Red today

R-conformity-l: the inline-style count above its floor; the off-scale steps.

## The one visible change

None named by the report; an on-scale rounding (9 → 8/10, 16 → 14/18) moves a few pixels on `acq-add-*` and one
settings state — declared by name, else STOP A.

## Mutation

Put one inline `style` back → falls by name.

## Oracle: states that diverge, declared by name

The states of the files converted (built by script).

## Commit

`refactor(maquette-conformity): sizes and colours from the scale, never typed`
