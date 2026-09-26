# Phase 9 — The off switch

**Reads OPEN 2 (where the switch's control lives) — not ruled at this writing.** **No new operation under either reading**: the switch is the
setting `tracker.providers.<name>.cross_seed`, and its write already exists (DESIGN § 2.1, fact 7).

- **Reading A — on the Trackers page.** The tracker's head carries a control that calls `updateConfigurationFile` with `tracker:tracker.providers.<name>.cross_seed`,
  and the head says « pris en compte à la prochaine passe ». **10 points** as drawn below. A second door onto one setting: it holds while both
  doors write the same row (R-L17-e's agreement hold).
- **Reading B — in Réglages only.** The head READS the state and links to the setting through the addressed panel
  (`setting:<file>:<key>`, `frontend/maquette/design/src/app/addressed-panels.ts` — 151 non-blank lines) with `crossReference()`; no control, no confirmation copy.
  **6 points**: the link ≈ 12 lines new 1½, keys ½, the state 1, R-L17-e in its « no control writes here, the state follows the row » form 3.

**Opening measure (2026-09-27, on `46806a88d` — L16's head does not exist on this head):**

- **Commands.** `sed -n 71,112p frontend/maquette/design/src/mocks/handlers/configuration.ts` → `updateConfigurationFile` is keyed `<file>:<key>` and moves `raw`
  AND `displayedValue`. `sed -n 103,130p personalscraper/web/routes/config.py` → `"cross_seed": False` (113) and `"tracker": False` (130): the file takes effect on
  the next run, **not at once**, so a head that read « stoppé » the instant it was written would say more than the engine knows (NE-DOIT-PAS-1) — and the mock's
  handler sets `restartRequired = true` on every write, which is a divergence the phase reads and names, never copies. `git grep -n 'setting:' --
  frontend/maquette/design/src/app/addressed-panels.ts` → the producer registration L16's phase 6 reads as a STOP D. `grep -n 'crossReference'
  frontend/maquette/design/src/features/system/locks.tsx` → the helper Système already draws a path with.
- **Points ≈ 10 (A).** The control in `tracker-screen.tsx`'s head ≈ 30 lines new 3; keys ≈ 6 lines ½; the sentence « pris en compte à la prochaine
  passe » 1; the handler edit so the tracker's projections read the settings row the write moved ≈ 6 lines 1½; the state `tracker-cross-seed-switch-off` 1;
  R-L17-e 3 → 10.
- **Found.** The four states already read the switch (phases 5–6); this phase adds the way to change it, or the way to it.

## Red today

**R-L17-e — the off switch** (DESIGN § 5). A: the flip is ANSWERED on the network (`window.__mocks.answered()`, `updateConfigurationFile`), the Réglages row
and every projection of the tracker's state move in the SAME render, and the head says « pris en compte à la prochaine passe ». B: the Trackers page draws NO
control and its state follows the Réglages row when that row changes. Red against `main`: none of it exists.

## Move

1. A: the control and its answer, through the existing write; B: the link.
2. `tracker-cross-seed-switch-off` in `harness/states/trackers.ts`, under the scenario of phase 2 for the tracker whose switch is off.

## Mutation

Commit first. A: make the control message without calling → the network hold falls; move the Réglages row and not the projections → the agreement falls.
B: draw a control → the absence hold falls; read the state from a copy of the row → the follow hold falls.

## Register

—

## Oracle: states that diverge, declared by name

L16's `tracker-detail` head — accepted with « L17 § 3.2: the head reads the switch ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` on `tracker-cross-seed-switch-off`.

## Commit

`feat(maquette-l17): a tracker's cross-seed switch is read where the tracker is, and changed on the one setting`
