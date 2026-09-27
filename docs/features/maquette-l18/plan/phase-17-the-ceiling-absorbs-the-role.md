# Phase 17 — The ceiling absorbs the staging role

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `git grep -c "readOnly" -- frontend/maquette/design/src ':!*.d.ts' ':!*.json'` → **24 lines in 12 files** (`features/settings/banners.tsx` 4, `panel-secret.ts` 4, `panel-setting.ts` 5, `panel-field.tsx` 1, `queries.ts` 1, `state.ts` 1, `types.ts` 1, `variants.ts` 2, `harness/settings-reset.ts` 1, `harness/states/settings.ts` 1, `mocks/handlers/configuration.ts` 1, `mocks/state.ts` 2).
- `git grep -n "readOnly = true" -- frontend/maquette/design/src` → `harness/states/settings.ts:113` alone: the flag is set true by ONE named state, `settings-read-only`, and by nothing served. `readConfigurationStatus` answers `{readOnly, restartRequired}` from the mock's own `readOnly` (false, `mocks/state.ts:319`) — **the two are not connected** (DESIGN § 0.2 fact 6).
- `sed -n 396,402p frontend/maquette/harness/settings.py` → the existing rule that reads « lecture seule » on the banner; it is re-aimed onto the ceiling dial, its assertion unchanged.
- § 17: the ceiling subtracts every write, whatever the role. **The engine's A18 policy (acquisition and decision writes open on staging) is not asked here**: DESIGN § 6.2 row N proposes the engine follow.
- **Points ≈ 15.** 24 lines in 12 files leave `readOnly` for the model's ceiling (5) + `readAccount`'s answer carries the ceiling from the dial (1) + the ceiling's statement, one sentence (1) + three states — `ceiling-operator`, `settings-read-only` re-driven, and its neighbour (3) + R-L18-o with its mutations (3) + R-L18-b gains its `readOnly` source hold (1) + `harness/settings.py`'s read-only hold re-aimed (1).
- **What to cut if the opening measure exceeds 15.** At 15. Cut: R-L18-b's `readOnly` hold moves to the close (phase 29).

**DESIGN § 3.7 — the second mechanism dies.** `SETTINGS_STATE.readOnly` and the mock's `readOnly` are replaced by the model's ceiling; `settings-read-only` becomes a state that turns the dial (`setCeiling(true)`). **Every write is absent on a ceilinged instance, for every role, the Operator included**, because the ceiling subtracts before the role adds; and it SAYS WHY, once, where a write would have been (the settings banner stays) — § 17 point 2 at its strongest: an Operator who finds no lever must not conclude the application is broken.

## Red today

**R-L18-o — the ceiling absorbs the role**: with the ceiling on, on Système, Réglages, Maintenance, the library and every Acquisition act, no write is offered **for the Operator**; the statement of why is drawn; **`SETTINGS_STATE.readOnly` and the mock's `readOnly` do not exist** (source hold); every write is refused (R-L18-c).

**Red against `main`**: the flag exists and only Réglages reads it.

## Move

The 24 sites, the ceiling on the answer, the statement, the states, the source hold.

## Mutation

With the commit made first: re-add a settings-only flag → the source hold falls; leave one lever offered under the ceiling → R-L18-o falls naming it.

## Register

—

## Oracle: states that diverge, declared by name

**`settings-read-only` and the settings states that draw the banner** (the flag was a module state, the ceiling is served) — « L18 § 3.7: the flag dies ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`refactor(maquette-l18): the staging role becomes the model's ceiling — one authorisation path`
