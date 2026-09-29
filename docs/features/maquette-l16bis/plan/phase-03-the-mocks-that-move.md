# Phase 3 — The mocks that move

**No STOP C.**

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -cv '^\s*$' frontend/maquette/design/src/mocks/handlers/{trackers.ts,configuration.ts}` →
  **77, 135**; `grep -n "pose[A-Z][a-zA-Z]*" frontend/maquette/design/src/mocks/handlers/trackers.ts` → the L16 poses
  (`poseBrokenObligation`, `poseIdentifierRefused`, …).
- **Points ≈ 12.** `readTrackers` answers `enabled` from the SAME settings seed the write moves (≈ 10 lines) 2;
  `updateConfigurationFile` on `…enabled = true` for a tracker off by failure answers `422` with the seed's
  message, and moves nothing (≈ 12 lines) 2; `poseLongName` (the 132-character real name of DESIGN § 0.1 item 6) 1,
  `poseUnlinked` 1, `poseEntryState(state)` for the six non-seeding tokens 1, `poseOneEntry` 1 — each declared a
  derivation in its docstring; `poseIdentifierRefused` re-written onto `disabled` 1; the report 2; the harness drive
  typings 1.
- **Readers.** `harness/states/trackers.ts` calls `poseIdentifierRefused` (`tracker-identifier-refused`) — the name
  kept, its body moved.

## Red today

None — a mock has no rule of its own; phase 13's and 14's rules read what it moves.

## Move

1. One seed, several projections (L16 § 2.4): the roster's `enabled` and Réglages' row read the same value.
2. The refusal persists while the seed says the failure does; `poseRecovered(name)` lifts it (for phase 14's
   successful re-activation).

## Mutation

None.

## Register

None.

## Oracle: states that diverge, declared by name

None expected; a state that moves is STOP A.

## Commit

`feat(maquette-l16bis): the activation write moves the roster, and a failing tracker refuses it`
