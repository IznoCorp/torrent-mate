# Phase 4 — The strip counts its cells

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** `sed -n 95,102p frontend/maquette/design/src/ui/variants/card.ts` → line 99:
  `grid-cols-[repeat(5,minmax(0,1fr))]` — the strip's grid is written for five cells. `git grep -c strip -- frontend/maquette/design/src/ui/card.tsx frontend/maquette/design/src/ui/variants/card.ts frontend/maquette/design/src/ui/card-markup.ts`
  → 11, 9, 9 lines. `StripState` = `done` · `now` · `blocked` · `pending` (`stageState` in
  `features/acquisition/card-markup.ts:52` and, copied, in `features/arrivals/arrival-card.tsx:46`). The strip labels each
  cell under its dot (`stripDot`, `stripLabel`, `stripStep`). Consumers today: the acquisition list cards and the
  Arrivées card, five cells each, always labelled. `ui/variants.test.ts` exists (the unit-test home of `ui/` variants).
- **Points ≈ 6.** About 22 site-lines across the three `ui/` files ≈ 4; one unit test with its mutation 2.

**A primitive change with no consumer of its new shape yet.** Phase 5 draws ten cells; the primitive must be able to first,
and it is its own phase so phase 5 moves no primitive and the ladder's oracle divergence names the ladder alone. **It
knows no domain** (invariant 10): cells, an optional label per cell, and two more cell states, with domain-free names.

## Red today

**A unit test** (in the family of `ui/variants.test.ts`), not a harness rule — a primitive with no consumer of the new
shape is one no rule can hold (L20's own reason for building its disclosure primitive beside its only consumer):

- a strip of ten cells lays out on ten columns; a strip of five is unchanged;
- a cell with no label draws none (no empty label element that still takes space);
- two cell states exist beyond the four — `waiting` (queued behind a bound or a maintenance run) and `aside` (set aside
  by the operator) — each with its own tone from the scale (a raw value outside the scale is refused, invariant 3).

**Red against `main`**: the grid is `repeat(5, …)`, and there is no `waiting` or `aside`.

## Move

`ui/variants/card.ts` — the grid columns follow the cell count; `ui/card.tsx` and `ui/card-markup.ts` — the label is
optional; the two cell states and their tones. **At five labelled cells the rendered markup is byte-identical to today's.**

## Mutation

With the commit made first: hard-code five columns again. The unit test must fall, naming the ten-cell strip.

## Register

—

## Oracle: states that diverge, declared by name

**None** — unchanged at five labelled cells. A divergence on any state is STOP A: it would mean the primitive changed what
five labelled cells look like.

## Gate

Per INDEX « Gates »; `vitest` over `ui/variants.test.ts`; `python3 scripts/check-frontend-boundaries.py`.

## Commit

`feat(maquette-l22): the card strip counts its cells and knows two more states`
