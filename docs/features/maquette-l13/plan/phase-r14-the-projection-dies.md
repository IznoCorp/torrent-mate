# r·14 — The projection dies

2026-09-15 (ruling 109): r·13 measured ≈ 18–19 and was cut — r·13 the sheet (conversion only), r·14 « the projection dies » (new), r·15 « the file dies ».

**Kind**: DELETION. **Cost**: Estimate ≈ 7–9 points (ruling 109, measure 11, ≤ 15).

## Measured

On `67b27fe34` (ruling 109's STOP D): with SHEETS_RAW converted at r·13, `engine/engine-shape.ts` has no product caller.
What dies with it: `engine/engine-shape.ts` and its test; `check-mock-seeds.py --arm lossless` (the arm, the ARM
table entry, its test in `tests/scripts/test_check_mock_seeds.py`, the docstring); the 49 families and the
`$card`/`$fact` shorthands of `frontend/maquette/fixture-projections.json`; `check-frontend-boundaries.py`'s two JSON
read exemptions for `engine-shape.ts` and its test, and its `FAN_IN_EXEMPT` entry; `harness/switchover.py`'s comment.
`scripts/build-mock-seeds.py` reads the families (`projection_for`, the seeds' `join`; CI path `ci.yml:103`) — what it
reads instead is MEASURED at this phase's opening, one STOP D.

## The proof first

no new rule; `grep -rn "engine-shape" frontend/maquette/design/src` lists nothing; the guards that read the deleted
names exit 0 on the tree and their tests pass under the tests lock.

## Gate

Per INDEX « Gates »: contracts + oracle + the rules that read the deleted names (none expected — said by grep), logs
postdating the commit.
