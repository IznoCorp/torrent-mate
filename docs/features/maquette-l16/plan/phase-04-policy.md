# Phase 4 — The policy panel

`min_ratio` and `min_seed_time` writable from the tracker's own screen (DOIT-3 — « agir là où l'on
observe »), plus the ratio alert threshold in the SAME panel (§13, one derivation, one save —
DESIGN § 4.3, § 4.5).

**Opening measure (2026-09-15, on `08400a22a`):**

- **Commands.** `sed -n '216,231p' personalscraper/conf/models/api_config.py` →
  `TrackerEconomyConfig{target_ratio: float, min_ratio: float = 1.0, min_seed_time: int,
  hit_and_run_grace: int = 0}`, the write's own field set. `cat config.example/tracker.json5` →
  `providers.<name>.economy` is commented out for both `c411` and `tr4ker` today — no tracker in
  the shipped example has ratio policy configured, which is the state this panel must handle as a
  real one (an unset policy is not an error). `grep -rn "topicRow\|panel=setting:"
  frontend/maquette/design/src/features/settings/` — the existing panel-parameter precedent (L20 §
  4.1's `?panel=setting:<settingId>`) this phase's `?panel=setting:policy` follows.
- **Points ≈ 9.** New panel component + its query-param wiring ≈ 3; one new rule (R-L16-d, DOIT-3 —
  the write, and the tracker's own read reflecting it in the SAME render) with its mutation ≈ 3; one
  named state (the panel reuses the settings feature's `number` field primitive, so it needs no
  loading/error state of its own, per DESIGN § 4.3) ≈ 1; fr.json keys ≈ 2. Under 15, no cut.

A BEHAVIOUR change: no write exists anywhere in this domain today (phase 1 filed it as a demand);
this phase is the first to call it.

## The proof FIRST

Its label is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From `/trackers/$name`, open the policy panel, change `min_ratio`, save.
- **What it reads.** The panel's save calling the tracker policy write
  (`window.__mocks.answered()`), and the tracker's OWN read — S1's row, S2's head — reflecting the
  new value in the render that follows (§13's agreement, the same shape R-L20-g held for the lock).
- **Red today.** No panel, no write, no read to reflect it — the hold fails against `main` for
  exactly that reason.
- **Mutation.** `scripts/mutate.sh` makes the save button message success without calling the
  operation. The network hold must fall, naming the operation.

## The move

- **`features/trackers/policy-panel.tsx`** — `min_ratio`, `min_seed_time` fields (the settings
  feature's existing `number` field primitive, reused per §13 rather than a second one invented),
  the ratio alert threshold (phase 6 reads it; this phase is where it is SET, filed in the same
  save so the two never disagree), a guidance line naming what the floor means (« Le seuil en
  dessous duquel un média peut être libéré, pas une cible. »).
- **The panel opens at `?panel=setting:policy`** on `/trackers/$name` — a query parameter, D1b rule
  1 (adjusting a surface replaces, it does not push).
- **`data-part`**: `policy`, `policy/min-ratio`, `policy/min-seed-time`,
  `policy/alert-threshold`, `policy/save`.
- **`i18n/fr.json`** — `screens.tracker.policyGuidance`, the field labels if the settings
  primitive's own labels do not already fit a per-tracker context.

## Mutation

`scripts/mutate.sh` makes the save handler respond without calling the write operation. The
network hold must fall, naming the operation it expected and did not see.

## Register

DOIT-3's row gains its L16 half — « the tracker policy set from the ratio surface » — `served`,
reported precisely by phase 8.

## Oracle: states that diverge, declared by name

**None.** `tracker-policy-panel` is NEW, and the panel opens over the detail screen phase 3 already
recorded — a query-parameter adjustment, D1b rule 1, so the underlying screen's own region is
UNCHANGED beneath it (the same shape L20's `?panel=setting:<settingId>` holds for the bound's
editor). Any divergence on `tracker/body` itself is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `tracker-policy-panel`.

## Commit

`feat(maquette-l16): the tracker's policy, writable from the surface that shows its ratio`
