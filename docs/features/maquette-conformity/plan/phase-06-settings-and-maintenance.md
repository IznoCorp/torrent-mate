# Phase 6 — Réglages and Maintenance

## What changes

1. **One switch** (D.1 #4): the settings field (`features/settings/panel-field.tsx:72–80`) draws `toggleSwitch`;
   `fieldToggle` / `fieldKnob` die (`features/settings/variants.ts:101–115`). **L16-bis DESIGN § 1.7 and § 1.8 are
   corrected in the same move** — they named `toggleSwitch` as the settings panel's while the code drew another.
2. **« actif / inactif »** at the settings field (« Activé / Désactivé », `:82–84`) and at Maintenance's « à blanc »
   (`features/maintenance/panel-action.ts:85`) — the pair phase 5 created.
3. **Five topic rows** → `ui` `TopicRow` (`features/settings/page.tsx:286–311`, `features/maintenance/page.tsx:113–116`).
4. **One back control** (D.1 #12): `backAction` + `Icon left` at `features/settings/page.tsx:133, 175`; « ← » leaves
   `screens.maintenance.allCommands` (`features/maintenance/page.tsx:73`).
5. **The banners are notices** (OPEN 3 = A): read-only, changed-on-disk, restart-required (`banners.tsx:49, 61, 70`)
   → the toned notice, no `role="alert"`.
6. **The save is `actionButton({ kind: "submit" })`** (OPEN 8 = A): `saveAction` and its literal `'Geist'` go.
7. **Tokens** (D.1 #16): `style={{ marginBottom: 12 }}`, `style={{ marginTop: 16 }}` (16 off-scale) → steps.

## Acceptance — red first on the old code

- R-conformity-c (new, `harness/one_switch.py`): on `settings-field-boolean` and `screen-profile` both switches are
  the `ui` part, one geometry.
- R-conformity-e (phase 5's) extended to the settings field and « à blanc »; R-conformity-j (new,
  `harness/back_control.py`): every `screen/back` carries the icon and no arrow glyph in its text; the notice's hold
  (`state_surfaces.py`): a non-error notice carries no `role="alert"`.
- `run.sh --rules settings.py settings_editing.py topics.py` green; R-conformity-a on the Réglages / Maintenance states.
- The oracle accepts by name: the switch's 2 px, the banners' tone, the save button, the back controls' arrow.

## Commit

`feat(maquette-conformity): Réglages and Maintenance — one switch, one back control, notices and the one save`
