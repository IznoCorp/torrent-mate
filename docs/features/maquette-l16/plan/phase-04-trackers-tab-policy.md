# Phase 4 — The tracker's policy and alert threshold

`min_ratio` and `min_seed_time` writable from the tracker's own entry (DOIT-3 — « agir là où l'on
observe »), plus the ratio alert threshold in the SAME save (§ 13, one derivation — DESIGN § 4.2,
§ 4.5, round 9 Q2). **This phase files the alert threshold's own config-key demand** (DESIGN § 2.3
item 2); the write ITSELF is not a new operation — it is `updateConfigurationFile`, already declared
and mocked (F11), and this phase's first job is establishing that rather than assuming a new one.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `sed -n '216,231p' personalscraper/conf/models/api_config.py` →
  `TrackerEconomyConfig{target_ratio: float, min_ratio: float = 1.0, min_seed_time: int,
  hit_and_run_grace: int = 0}` — no `alert_threshold` field: round 9 Q2's own key is missing from the
  model, not from the write path. `grep -n economy config.example/tracker.json5` → lines 16 and 26,
  both commented out: no tracker in the shipped example has a policy configured, the state this entry
  must handle as real (§ 8). `sed -n '590,712p' frontend/maquette/design/src/mocks/seeds/settings.json`
  → the `economy.target_ratio` / `.min_ratio` / `.min_seed_time` rows ALREADY seeded, `file:
  "tracker"`, keyed `tracker.providers.<name>.economy.<field>` — read through `GET /api/config/schema`
  and written through `PUT /api/config/files/{name}` (`updateConfigurationFile`), already declared
  and mocked (`mocks/handlers/configuration.ts:50,71`; `git grep -n updateConfigurationFile --
  frontend/maquette/design/src` → `features/settings/queries.ts:129`, `contract/types.d.ts:3483`, the
  mock route). `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/features/settings/panel-field.tsx`
  → 182 (the `FieldBlock` this entry reuses, registered on `ui/panel`'s block map under the kind
  `"field"`); `frontend/maquette/design/src/ui/disclosure.tsx` → 34 non-blank lines, its own header:
  « IT KNOWS NO DOMAIN. What the summary says and what is folded are the caller's » — the accordion
  primitive this phase wraps, unmodified.
- **Found (2026-09-27) — STOP D, one to report at the opening.** DESIGN § 3 leaves open whether the
  three fields (`min_ratio`, `min_seed_time`, the new `alert_threshold`) compose by opening the
  EXISTING settings bottom panel at a coarser subject (the tracker's whole `economy` block, alongside
  the `<file>:<key>` subject the `setting` kind already holds — one more line in
  `app/panel-contributions.ts`) or by the Trackers feature registering its OWN block kind on
  `ui/panel`'s block map, the `field` block's own precedent (`panel-field.tsx:26-30`, `declare module
  "../../ui/panel/contract"`). Both keep the disclosure open with the SAME three rows drawn either
  way; the phase measures which composes without a second settings-identity shape to keep honest
  against the first, and reports the answer before it moves.
- **Points ≈ 13.** The disclosure's body — three fields on the reused primitive, the guidance line, the
  save (≈ 45 new; analogue `panel-field.tsx`) 4½; the composition chosen by the STOP D (≈ 10 new, 3
  edited either way) 1½; **one new rule, R-L16-b** (DOIT-3: the write, and the SAME setting's own
  read — this entry, and Réglages' own row — reflecting it in the same render) with its mutation 3;
  the state `trackers-entry-open` re-using phase 3's seed 1, `trackers-policy-unset` needing a new
  seed row (a tracker with no `economy` block at all) 2; « Voir les torrents » (≈ 8 new, a
  `crossReference()` setting both dials) 1; `fr.json` (`screens.trackers.floorGuidance`, corrected
  against F57, and the field labels where the settings primitive's own do not fit a per-tracker
  context) 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's phase 6 (15, « the policy panel »)
  declared a NEW write operation and its mock (2+2 of its 15). **This redraw drops that entirely**
  (F11: the write already exists) and spends the freed points on the alert threshold's own field and
  on the disclosure's composition, landing lower (13) despite drawing MORE (three fields, not two).
  The prior phase's STOP D (the panel kind `setting` not fitting the subject `policy`) is REPLACED by
  the STOP D above, on the SAME question moved one level: not « what address », but « what composes »
  (DESIGN § 3).

A BEHAVIOUR change: no surface offers these three fields together anywhere today; this phase is the
first to draw them beside the ratio they govern.

## The proof FIRST

Its label R-L16-b is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From `/trackers?tab=trackers`, open a tracker's disclosure, change `min_ratio`,
  save; separately, open the SAME setting from Réglages.
- **What it reads.** The save calling `updateConfigurationFile` (`window.__mocks.answered()`), and the
  SAME setting's own read reflecting the new value in the render that follows — on THIS entry, and on
  Réglages' own row (§ 13's agreement, one write, two doors — round 9 Q2); the disclosure opening
  ADJUSTS and pushes nothing (`history.length`, D1b rule 1).
- **Red today.** No entry, no disclosure, no field to read — the hold fails against `main` for exactly
  that reason.
- **Mutation.** `scripts/mutate.sh` makes the save button message success without calling the
  operation. The network hold must fall, naming the operation. A second mutation disagrees this
  entry's read from Réglages' own row after a save (a stale local copy) — the agreement must fall too.

## The move

- **The alert threshold's demand**: a new key, `tracker.providers.<name>.economy.alert_threshold` (or
  equivalent), in the SAME `economy` block — filed as a config-shape row (§ 2.3 item 2), never a new
  operation.
- **`features/trackers/trackers-tab.tsx`** — the disclosure body: `min_ratio`, `min_seed_time` and the
  alert threshold, on the settings feature's existing field primitive, composed per the STOP D's
  answer; a guidance line, corrected against F57: « Le ratio à partir duquel un torrent peut être
  retiré sans dette envers le tracker — un plancher, pas une cible. »
  (`screens.trackers.floorGuidance`); the unset state (« Aucune politique réglée pour ce tracker. »,
  `screens.trackers.policyUnset`); « Voir les torrents » setting `?tab=torrents&tracker=$name`.
- **`data-part`**: `trackers/policy`, `trackers/policy-min-ratio`, `trackers/policy-min-seed-time`,
  `trackers/policy-alert-threshold`, `trackers/policy-save`, `trackers/see-torrents`.
- **`harness/states/trackers.ts`** — `trackers-entry-open`, `trackers-policy-unset`.
- **`i18n/fr.json`** — `screens.trackers.floorGuidance`, `.policyUnset`, `.seeTorrents`, the field
  labels if the settings primitive's own do not already fit.

## Mutation

Two, as above — each committed and restored separately.

## Register

DOIT-3's row gains its L16 half — « the tracker policy set from the ratio surface » — `served`;
`backend-demands-architecture.md` § 4's own correction (the write exists, only the threshold key is
missing) is this PR's edit, not this phase's — phase 16 reports the row, item 3 of the plan carries
the file edit.

## Oracle: states that diverge, declared by name

**None.** `trackers-entry-open` and `trackers-policy-unset` are NEW, drawn inside a roster row phase 3
already recorded — accepted, named, with the reason « L16 phase 4: a tracker's entry opens its policy
». Any divergence on a CLOSED entry is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for both new states.

## Commit

`feat(maquette-l16): the tracker's policy and alert threshold, set where its ratio lives`
