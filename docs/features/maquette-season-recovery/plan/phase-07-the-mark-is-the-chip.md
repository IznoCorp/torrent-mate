# Phase 7 — The mark is the chip

**STOP C: OPEN 7** (DESIGN § 5). Written for A: `queuedMark` dies, the rows draw `chip({ tone: "info" })`. Under B
the variant MOVES to `ui/` unchanged (≈ same points) and phase 10 imports it from there.

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.** `git grep -n "queuedMark" -- 'frontend/maquette/design/src/*.ts' 'frontend/maquette/design/src/*.tsx'`
  → **8** lines: the variant (`features/media/variants.ts:198`, and its mention at `:207`) and its import and two call sites in each of `panel-seasons.tsx` and `season-list.tsx`;
  `grep -n "info:" frontend/maquette/design/src/ui/variants/surfaces.ts` → the chip's `info` tone, line **74**.
- **Points ≈ 5.** The call sites rewired 1; the variant deleted, its header's reasoning kept where the chip's
  `info` tone is declared (the muted-season remark of `:204–210` re-pointed) 1; the harness reads of `queuedMark`
  (R138, R158, R-b) re-aimed OUT LOUD to the chip's class 2; the report 1.
- **Readers.** `grep -ln "queuedMark\|season/queued\|season/asked" frontend/maquette/harness/*.py` → **3**:
  `acted_surface_redraws.py`, `queued_by_hand.py`, `queued_ask_mark.py` — each re-read for a class it names.

## Red today

None of its own — a refactor; R-season-recovery-f (phase 10) is its rule.

## Move

1. `data-part="season/queued"` and `data-part="season/asked"` are KEPT: the parts are the rows', the drawing is the
   chip's.

## Mutation

None here — R-f's, at phase 10.

## Register

None.

## Oracle: states that diverge, declared by name

Every state drawing « En file » or « Demandée » (the chip gains its dot), declared by script.

## Commit

`refactor(maquette-season-recovery): « Demandée » and « En file » are the info chip, not a copy of it`
