# Phase 10 — The back control (D.1 #12)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "backAction\(" -g '*.tsx' frontend/maquette/design/src` → **11** sites; the seven screens
  carry `Icon left`; `features/maintenance/page.tsx:73` carries « ← » in the copy
  (`jq -r '.screens.maintenance.allCommands' frontend/maquette/design/src/i18n/fr.json`); `features/settings/page.tsx:133,
  175` carry no arrow.
- **Points ≈ 6.** Three sites onto `backAction` + `Icon left` (≈ 8 lines, 2); « ← » leaves `fr.json` (1);
  R-conformity-h (3).
- **Readers.** Eleven rules read `screen/back`; Maintenance's and Réglages' back controls carry other parts — both
  re-read at the opening.

## Red today

R-conformity-h over every state drawing a back control: an icon, and no arrow glyph in the text — falls on
`maintenance-topic` and the settings rubric states.

## Mutation

Put « ← » back in `allCommands` → falls by name.

## Oracle: states that diverge, declared by name

`maintenance-topic`, `maintenance-delete`, and every settings rubric state (built by script).

## Commit

`refactor(maquette-conformity): one back control, an icon and a word`
