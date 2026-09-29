# Phase 4 — The derivation moves to lib

**No STOP C.** A MOVE: nothing drawn changes, and the oracle proves it.

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.** `grep -n "^export function\|^function sameMedium" frontend/maquette/design/src/features/acquisition/arrival-slots.ts`
  → `slotArrivals` **24**, `todoCards` **43**, `setAsideCards` **54**, `sameMedium` **73**, `inFlightCards` **96**;
  `git grep -l 'arrival-slots"' -- 'frontend/maquette/design/src/*.ts' 'frontend/maquette/design/src/*.tsx'` → **5**
  importers, all in `features/acquisition/` (`acquisition-tabs.tsx`, `follow-facts.ts`, `now-tab.tsx`,
  `queries.ts`, `todo-tab.tsx`); `grep -cv '^\s*$' frontend/maquette/design/src/lib/queue.ts` → **390** (NOT the
  home: STOP D if a phase reaches for it).
- **Points ≈ 6.** The module moved WHOLE to its own `lib/` module (≈ 92 lines, moved not rewritten) 2; the five
  imports rewired 1; the file's header saying why it lives in `lib/` (four readers, two features, invariant 7) 1;
  the oracle run proving nothing moved 1; the report 1.
- **Readers.** Every reader of the five functions — listed by the command above; none outside `features/acquisition`
  yet (phase 6 adds `features/media`).

## Red today

None — a move has no rule; the oracle not moving is its proof.

## Move

1. `git mv` the module into `lib/`, under a name that says its question (« what is on its way »), and rewire the five
   imports.
2. The invariant-7 arm (`check-no-french.py` is not it — the import guard of `docs/reference/frontend-architecture.md`
   invariant 7) read by OUTPUT: `lib/` imports no feature.

## Mutation

None.

## Register

None.

## Oracle: states that diverge, declared by name

**None.** Any divergence is STOP A.

## Commit

`refactor(maquette-season-recovery): what is on its way is one derivation in lib, read by any feature`
