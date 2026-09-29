# Phase 14 — A failing tracker says why

**STOP C: DECIDED 6** (2026-09-29, PR #637 — DESIGN § 5): a tracker off by FAILURE counts ONE in the Trackers badge,
like the refused identifier — the existing badge mechanism ADAPTED, not rebuilt.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n "identifierRefusedSince" -r frontend/maquette/design/src/features/trackers` → the alert's
  reads (`queries.ts`, `trackers-tab.tsx:190–192`); `grep -n "refused" frontend/maquette/harness/trackers_alert.py | head`
  → R-L16-d's unit hold (M5).
- **Points ≈ 13.** R-L16bis-h 3; « Désactivé — <raison> depuis le … » under an off-by-failure row 1; the
  re-activation's refusal drawn under the row, in the engine's words, staying (≈ 15 lines) 2; the alert's reads moved
  from `identifierRefusedSince` to `disabled` 1; R-L16-d re-aimed OUT LOUD (the unit read on `disabled.reason`) 1;
  states `tracker-off-by-failure`, `tracker-reactivate-refused` 2; the badge's term extended to every `disabled`
  tracker (`by: failure`, whatever the `reason`; `by: operator` excluded — DECIDED 6), and its hold 3.
- **Readers.** `harness/trackers_alert.py` (R-L16-d) and the bar's badge (`bar-trackers-alert`).

## Red today

R-L16bis-h over `tracker-reactivate-refused`: the switch turns on before the answer and no reason is drawn.

## Move

1. The switch stays off until the write answers; a `422` draws its `detail` under the row until the next change.
2. `poseRecovered` (phase 3): the same tap then succeeds — the switch on, the reason gone.

## Mutation

Turn the switch on optimistically → the refusal hold falls by name; toast the refusal instead → falls too.

## Register

None.

## Oracle: states that diverge, declared by name

`tracker-identifier-refused` (its words now the engine's reason), `bar-trackers-alert` (DECIDED 6's extended count);
the new states.

## Commit

`feat(maquette-l16bis): a tracker switched off by failure says why, and refuses to come back while it fails`
