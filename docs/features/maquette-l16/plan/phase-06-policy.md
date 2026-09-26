# Phase 6 — The policy panel

`min_ratio` and `min_seed_time` writable from the tracker's own screen (DOIT-3 — « agir là où l'on observe »), plus the ratio alert
threshold in the SAME panel (§ 13, one derivation, one save — DESIGN § 4.3, § 4.5). **The write's operation is declared here**, with
the surface that calls it (INDEX, « Why fifteen phases »); it is the second of the five demand rows filed across the lot (DESIGN
§ 2.3 item 2).

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `sed -n '216,231p' personalscraper/conf/models/api_config.py` → `TrackerEconomyConfig{target_ratio: float, min_ratio: float
  = 1.0, min_seed_time: int, hit_and_run_grace: int = 0}`, the write's own field set (line 216 is the class). `grep -n economy
  config.example/tracker.json5` → lines 16 and 26, both commented out: no tracker in the shipped example has a ratio policy configured,
  which is the state this panel must handle as a real one (an unset policy is not an error). `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/features/settings/panel-field.tsx` → 182 and `panel-setting.ts` → 335: the number field primitive this
  panel reuses (§ 13 — never a second one). `git grep -n 'setting:' -- frontend/maquette/design/src` → `app/addressed-panels.ts:69`.
- **Found (2026-09-26) — STOP D, one to report at the opening.** DESIGN § 3 writes the panel's address as `/trackers/$name?panel=setting:policy`.
  **The kind `setting` is the settings feature's**: `app/addressed-panels.ts` keys its openers by kind (`follow`, `journey`, `setting`,
  `action`), `setting` opens through `panel.produce("setting", subject)` and answers `panel.holds("setting", subject)` — and a settings
  subject is a `<file>:<key>` identity (`features/settings/catalog.ts`, `settingIdentifier`), which `policy` is not. The phase measures
  whether this panel takes a kind of its own (one more opener in that registry, one more line in `app/panel-contributions.ts`) or a subject
  the settings kind can hold, **and reports the answer to the steward before it moves**; it does not improvise. The cost is the same either
  way (≈ 5 lines new in the registry, counted below). The ordering claim in DESIGN § 3 — an ADJUSTING panel, D1b rule 1, nothing pushed —
  holds under both.
- **Points ≈ 15.** The write declared new (the summary's policy, DESIGN § 2.3 item 2) 2 and its mock route new — it moves the seed the summary
  read projects back (§ 2.4) 2; `features/trackers/policy-panel.tsx` (≈ 50 new — three fields on the settings primitive, the guidance line, the
  save; analogue `panel-field.tsx`) 5; the panel's wiring — the opener, its contribution line, the path from the detail (≈ 10 new, 3 edited) 1½;
  **one new rule, R-L16-d** (DOIT-3: the write, and the tracker's OWN read reflecting it in the same render) with its mutation 3; the state
  `tracker-policy-panel` 1; `fr.json` (the field labels where the settings primitive's own do not fit a per-tracker context, the guidance line)
  1. **At the ceiling; what to cut**: the write's declaration and its mock (4) as their own phase.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (its phase 4) 9 → this phase **15**: moved by **the scale** (the first drawing did not
  count the write's operation and its mock here — it declared them in its phase 1, as one of « five demand rows » at ≈ 0.6 each); no ruling
  touched it. Its « `?panel=setting:policy` » is now a finding, above.

A BEHAVIOUR change: no write exists anywhere in this domain today; this phase is the first to call it.

## The proof FIRST

Its label R-L16-d is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From `/trackers/$name`, open the policy panel, change `min_ratio`, save.
- **What it reads.** The panel's save calling the tracker policy write (`window.__mocks.answered()`), and the tracker's OWN read — the
  roster's row, the detail's head — reflecting the new value in the render that follows (§ 13's agreement, the same shape R-L20-g held for the
  lock); the panel opening ADJUSTS and pushes nothing (`history.length`, D1b rule 1).
- **Red today.** No panel, no write, no read to reflect it — the hold fails against `main` for exactly that reason.
- **Mutation.** `scripts/mutate.sh` makes the save button message success without calling the operation. The network hold must fall, naming
  the operation.

## The move

- **The write**, declared in `frontend/maquette/contract/openapi.json` and answered by a route in `mocks/handlers/trackers.ts` that MOVES the
  seed — `min_ratio`, `min_seed_time` and the alert threshold — which the summary read projects back. `compare-contracts.py --write` regenerates
  the register (the row for § 2.3 item 2 is filed by that edit).
- **`features/trackers/policy-panel.tsx`** — `min_ratio`, `min_seed_time` (the settings feature's existing `number` field primitive, reused per
  § 13), the ratio alert threshold (phase 9 reads it; this phase is where it is SET, in the same save so the two never disagree), and a guidance
  line naming what the floor means (« Le seuil en dessous duquel un média peut être libéré, pas une cible. »).
- **The panel opens** at the address the STOP D above settles, on `/trackers/$name` — a query parameter, D1b rule 1.
- **`data-part`**: `policy`, `policy/min-ratio`, `policy/min-seed-time`, `policy/alert-threshold`, `policy/save`.
- **`i18n/fr.json`** — `screens.tracker.policyGuidance`, the field labels if the settings primitive's own do not already fit.

## Mutation

`scripts/mutate.sh` makes the save handler respond without calling the write operation. The network hold must fall, naming the operation it
expected and did not see.

## Register

DOIT-3's row gains its L16 half — « the tracker policy set from the ratio surface » — `served`, reported precisely by phase 15.

## Oracle: states that diverge, declared by name

**None.** `tracker-policy-panel` is NEW, and the panel opens over the detail screen phase 4 recorded — a query-parameter adjustment, so the
underlying screen's own region is UNCHANGED beneath it. Any divergence on `tracker/body` itself is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `tracker-policy-panel`.

## Commit

`feat(maquette-l16): the tracker's policy, writable from the surface that shows its ratio`
