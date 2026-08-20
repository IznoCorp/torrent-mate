# L01 — implementation plan

Design: `docs/features/maquette-l01/DESIGN.md`
Lot: `docs/reference/frontend-architecture.md` § Phase 0 → L01 · `IN PROGRESS` · runs alone

## Why the phases are in this order

The oracle is useless if it is green over nothing, so each phase ends with the instrument
measuring **more** than the last, and each proves what it added rather than asserting it.

Phase 1 makes it measure *something real* on a handful of regions — before any region list
exists, so the core cannot be tuned to fit a list. Phase 2 then declares the real regions
against a core that already works. Phase 3 gives it a memory. Phase 4 makes that memory
trustworthy. Phase 5 wires it into the gate and fires the one mutation the architecture file
names as this lot's definition of done.

| # | Phase | Plan | Done |
| - | ----- | ---- | ---- |
| 1 | The recipe and the measuring core | `phase-01-recipe-and-core.md` | [ ] |
| 2 | The regions, declared on `data-*` | `phase-02-regions.md` | [ ] |
| 3 | The three modes and the reference | `phase-03-modes-and-reference.md` | [ ] |
| 4 | The five friction counter-measures | `phase-04-friction.md` | [ ] |
| 5 | The gate, the reference, the mutation | `phase-05-gate-and-proof.md` | [ ] |

## Verified before planning, not assumed

Run on 2026-08-20 against the built prototype served on 8899:

- `window.__states()` returns **82** ids, 82 unique — the count by EXECUTION, which is the only
  one the design accepts.
- `document.documentElement.clientWidth === 390` holds, so `assertBeforeMeasuring` passes.
- `common.PHONE` already equals the recovered `probe.viewport` (390 × 844, DPR 2, mobile, touch)
  and pins `color_scheme: "dark"` deliberately.
- `window.__go(id)` resets to seed by default, so a measurement never inherits the previous one.

**And one defect found while checking**: `common.open_page()` ends on
`await pg.wait_for_timeout(250)` — a delay in milliseconds, which is exactly what friction
counter-measure 1 forbids. Phase 4 replaces it for the oracle's path.
