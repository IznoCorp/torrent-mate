# Phase 13 — The switch, one write two doors

**No STOP C.** Round 9 Q1's second door, extended to `enabled` (RULINGS 2 kept).

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n "providers\.[a-z0-9.]*\.enabled" frontend/maquette/design/src/mocks/seeds/settings.json` → lines
  **594, 611, 670** (+ phase 2's three); `grep -n 'role="switch"' frontend/maquette/design/src/features/settings/panel-field.tsx`
  → line **74** (the switch drawn, `toggleSwitch`); `grep -n "PendingEditsBar" frontend/maquette/design/src/features/trackers/page.tsx`
  → the save bar's door (RULINGS 2).
- **Points ≈ 12.** R-L16bis-g 3; the switch at each row's end, `toggleSwitch`, its tap a pending edit of
  `tracker.providers.<name>.enabled` (≈ 20 lines) 3; « Désactivé » under an off row 1; states `tracker-active`,
  `tracker-off-by-operator`, `tracker-switch-pending`, `tracker-switch-write-failed`, `trackers-roster-one`,
  `tracker-composed` 3; `harness/trackers_roster.py`'s count re-aimed (two → six) 1; the report 1.
- **Readers.** `harness/trackers_policy.py` (R-L16-b, the policy's two doors) — the same door, unchanged; the
  three-choice leave confirmation (operator, 2026-09-29 Q4), once built, holds the pending switch too.

## Red today

R-L16bis-g over `tracker-active`: no switch on the row.

## Move

1. A tap toggles the pending value; the save bar writes it through `updateConfigurationFile`; Réglages' row and the
   roster read the same value in the next render.
2. The switch does not unfold the row it sits in (the tap is the switch's).

## Mutation

Write a second key from the roster → the two-door agreement falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

Every « Trackers » state (the switch), declared by script; the six new states.

## Commit

`feat(maquette-l16bis): each tracker has its activation switch, the same write as Réglages`
