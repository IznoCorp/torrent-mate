# Phase 18 — The desktop is fully functional (DOIT-9)

**No STOP C.** Ruled OPEN 6 = A (2026-09-29): the proof only that nothing breaks wide — the galleries widen, no
desktop layout. The desktop adaptation of the screens is a milestone after the drawn lots, not a phase of this plan.
Q1 (the drawer alone) is not re-opened.

**Opening measure (2026-09-29, on `77e7b8436`):**

- **Commands.** `grep -n "viewport" frontend/maquette/harness/states.py` → line **18**, `390 × 844`, `is_mobile`,
  `has_touch` — every named state is walked at the phone's width only; `git grep -h -A1 '^\s*\[$' --
  'frontend/maquette/design/src/harness/states/*.ts' | grep -c '^\s*"[a-z][a-z0-9-]*",$'` → **120** declared ids;
  `grep -cv '^\s*$' frontend/maquette/harness/desktop_frame.py` → **972** (R140, the harness's own switch).
- **Points ≈ 5.** R-L24-k 3 — every named state at 1280 × 800, pointer, no touch, through R140's desktop switch:
  content drawn, no horizontal overflow, no JS error, the galleries wider than at 390; every page reached through the
  drawer (Q1); the report 2 (the walk's time measured, because 120+ states at a second width doubles `states.py`'s
  cost).
- **Readers.** R140/R141 (`desktop_frame*.py`) hold the switch and its memory — read, never re-aimed.

## Red today

Read at the opening; a state that overflows at 1280 is a DEFECT found, reported to the steward first.

## Move

The rule only.


## Register

The map's DOIT-9 « Open: B-235 / Q1 » is stale (Q1 answered 2026-08-30); proposed at phase 20.


## Commit

`test(maquette-l24): every state holds at a desktop width`
