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
| 1 | The recipe and the measuring core | `phase-01-recipe-and-core.md` | [x] |
| 2 | The regions, declared on `data-*` | `phase-02-regions.md` | [x] |
| 3 | Determinism — the settle signal first | `phase-03-determinism.md` | [x] |
| 4 | The three modes and the reference | `phase-04-modes-and-reference.md` | [x] |
| 5 | The gate, the reference, the mutation | `phase-05-gate-and-proof.md` | [x] |

### The order changed after phase 1, and the measurement is why

This plan first put the reference at 3 and the friction counter-measures at 4. **That order
cannot work**, and phase 1 proved it rather than suspecting it: driving `drawer-navigation` five
times and measuring `#drawer` returns five different values — `x = -148.1, -141.8, -141.2,
-140.4, -140.2` — because the two-frame settle floor captures the drawer MID-ANIMATION. At real
rest the answer is `x = 0`.

A reference recorded from a non-deterministic measurement is not a reference. So determinism
moves ahead of the reference, and the phase that was 4 is now 3.

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
counter-measure 1 forbids. Phase 3 replaces it for the oracle's path.

## What phase 1 found, and what it cost the plan

Three things, each measured:

1. **`#shell` resolved in every smoke state while measuring nothing** — 390x0, because it is the
   mount node for migrated SCREENS and is empty until one opens. « Resolved » and « measures
   something » are now reported apart.
2. **The measurement is not deterministic on an animated layer** (the five values above). It
   reordered the plan.
3. **The recovered 17-property subset is blind to an overlay opening.** `#scrim` between
   `lib-list` and `drawer-navigation`: 17/17 properties identical AND an identical bounding
   rectangle. Amended to 19 with `opacity` and `visibility`; evidence in `DESIGN.md`, flagged to
   the operator in the pull request. `#screen` is blind even then — its content changes, not the
   host — which is why phase 2 declares regions on a layer's CONTENT.
4. **`make lint` did not read `frontend/maquette/`**, only its `harness/` subdirectory, so
   `fidelity.py` and `serve.py` had never been linted. Widened; four violations fixed.


## What the later phases found, and what it cost each of them

**Phase 2.** The 51 regions of the retired probe were class-anchored, and importing them would
have broken the oracle at the moment it is needed — L07 replaces those classes with utilities.
33 regions instead: 15 from ids the shell already carries, 18 needing a `data-region` anchor at
21 sites. An ACCEPTANCE criterion was found VACUOUS before it could pass:
`check-markup-contracts.py` reads `data-*` values a handler forwards into a store field, and
`data-region` is read in Python. `oracle.py --contracts` holds both directions instead.

**Phase 3.** Two traps, both paid inside the phase. `img.decode()` on a LAZY image never resolves
— it PENDS, so a `.catch()` does nothing and the settle signal hung for ever on the library's
posters. And the boot TOAST made half the sweep depend on machine speed: `toast()` schedules a
5 s dismissal, no named state raises one, and it was visible for the first 28 states and hidden
for the last 54 — that timer and nothing else.

**Phase 4.** The reference is 35 650 lines, and that size IS the deliverable: one property per
line is what lets a reviewer read `font-size: 12px -> 13px` on a named region in the pull
request's diff. Compacting it to one line per measurement would divide the size by twenty-five
and destroy the only thing it is for. Measured: unsorted, the same content produces 7 083 lines
of difference on an UNCHANGED tree.

**Phase 5.** Neutralising once at open neutralised nothing — `.note` was back in 56 of 82 states,
the toast in 34 — so the reference recorded in phase 4 measured the prototype's scaffolding and
had to be re-taken. Neutralisation now runs on both sides of the settle, because the boot toast
is raised asynchronously and a single pass loses the race on the very first state.
