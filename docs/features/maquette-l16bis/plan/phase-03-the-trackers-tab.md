# Phase 3 — The « Trackers » tab: the roster, its switch, its failure, its panel, its legend (S7, S3)

**Opening measure** (taken on `9234341fc`; re-taken at the real opening):
`python3 -c "import json;print([t['name'] for t in json.load(open('frontend/maquette/design/src/mocks/seeds/trackers.json'))])"`
→ `['c411', 'tr4ker']`; `grep -n "providers.lacale.enabled" frontend/maquette/design/src/mocks/seeds/settings.json` →
**594**; `grep -n "identifierRefusedSince" frontend/maquette/design/src/features/trackers/*.ts*` → `queries.ts:133`,
`trackers-tab.tsx:192`; `grep -c "^export const" frontend/maquette/design/src/features/trackers/variants.ts` → **9**
(fewer after phases 1–2 and the train's phase 11).

## What changes

1. **The data** (DESIGN § 2.2, § 2.3): `Tracker` gains `enabled` and `disabled {by, reason, message, since}`,
   `identifierRefusedSince` folded into it; `updateConfigurationFile` on `…enabled = true` for a tracker still failing
   answers `422` with the engine's words. Seeds: `lacale` from the operator's configuration (off after a failure,
   declared), `v3x.club` active, `draupnirr.xyz` off by the operator, `digitalcore.club` off by failure — the three
   COMPOSED, declared in `frontend/maquette/fixture-register.json`. Mocks: the roster's `enabled` read from the SAME
   settings seed the write moves; the refusal; `poseRecovered`; `poseIdentifierRefused` re-written onto `disabled`.
2. **The switch, one write two doors** (S7): `toggleSwitch` (the train's one switch) at each row's end, a pending
   edit of `tracker.providers.<name>.enabled`, the save bar and the three-choice leave confirmation shared with
   Réglages; « Désactivé » under a row off by the operator.
3. **A failing tracker says why** (S7; DECIDED 6): « Désactivé — <raison> depuis le … » under an off-by-failure row;
   re-activating it waits for the answer and draws the `422`'s words under the row, staying — never a toast; the
   Trackers badge counts one per `disabled.by: failure` tracker, the refused identifier's mechanism adapted; the
   alert's reads moved to `disabled`.
4. **The row opens a panel** (DECIDED 3): the row's body opens `tracker:<name>` — the policy rows (RULINGS 2's door
   unchanged), the places of cross-seed (L17) and uploads (L23), the broken obligations, « Voir les torrents »; the
   switch stays on the row; a landing naming a tracker opens its panel.
5. **The legend on « Trackers »** (S3): the roster's codes, off states included, through the same tone map.
6. **The design system swept** (DESIGN § 1.8): every factory of `features/trackers/variants.ts` still unused is
   deleted, the file removed if empty; the register row « a component redrawn » (DESIGN § 6) with its family.

## Acceptance — red first on the old code, then green

- **R-L16bis-g** — red on `tracker-active` (no switch); **R-L16bis-h** — red on `tracker-reactivate-refused`;
  **R-L16bis-c** extended to `trackers-legend`; **R-L16bis-i** (the page's parts from `ui/`) — red on
  `torrents-list` while a feature factory still draws.
- Re-aimed OUT LOUD: `trackers_roster.py` (two rows → six), `trackers_alert.py` (R-L16-d's unit read on
  `disabled.reason`), `trackers_policy.py` and the broken-obligation holds (onto the panel), `deferred_reason.py`
  (the landing opens the panel).
- Named states: every S7 id and `trackers-legend`; `bar-trackers-alert` (the badge's new term) by name.
- Walked by finger: the switch → the save bar → Réglages shows the same value; leaving with a pending switch → the
  three-choice confirmation; a row → its panel → Retour closes it.

## Commit

`feat(maquette-l16bis): each tracker has its switch, says why it failed, and opens its panel`
