# Phase 6 — The legend moves to ui

**No STOP C.**

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n "export const legend\b\|export const legendSwatch" frontend/maquette/design/src/features/media/variants.ts`
  → lines **346, 358**; `git grep -ln "legendSwatch\|legend(" -- 'frontend/maquette/design/src/features/*'` → its
  users, all in `features/media/`; `grep -cv '^\s*$' frontend/maquette/design/src/ui/variants/surfaces.ts` → **373**
  (the legend does NOT land there — a module of its own under `ui/variants/`).
- **Points ≈ 4.** The two factories moved, unchanged (≈ 25 lines) 1; a `Legend` component in `ui/` that takes
  `{tone or swatch, word}[]` and draws only what it is given (≈ 20 lines) 2; the media imports re-pointed 1.
- **Readers.** `harness/surfaces.py` and `harness/run_history.py` read `legend` — the class token and the part kept.

## Red today

None — a move changes no drawing; the oracle proves it.

## Move

1. Move, never redraw: the class strings are byte-identical, read by `git diff --color-moved`.
2. The season matrix draws through the new component; its states do not move.

## Mutation

None — a move; the oracle holds it.

## Register

None.

## Oracle: states that diverge, declared by name

None: every season state is unchanged. One that moves is STOP A.

## Commit

`refactor(maquette-l16bis): the season legend becomes the interface's legend`
