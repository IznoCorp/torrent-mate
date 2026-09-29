# Phase 8 — One switch (D.1 #4), and L16-bis § 1.7 / § 1.8 corrected

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n 'role="switch"|toggleSwitch|fieldToggle|fieldKnob' -g '*.ts' -g '*.tsx'
  frontend/maquette/design/src` → `toggleSwitch` (`ui/variants/controls.ts:145`) used only at
  `features/releases/quality-screen.tsx:233, 251`; `fieldToggle` + `fieldKnob` (`features/settings/variants.ts:101–115`)
  at `features/settings/panel-field.tsx:72–80`; `grep -n "panel-field.tsx:74" docs/features/maquette-l16bis/DESIGN.md`
  → § 1.7 names `toggleSwitch` as the settings panel's — the code says otherwise.
- **Points ≈ 11.** `panel-field.tsx` onto `toggleSwitch` (≈ 10 lines, 2); `fieldToggle` / `fieldKnob` die (1);
  R-conformity-c (3); the `role="switch"`-outside-`ui/` arm and its test (2); L16-bis DESIGN § 1.7 / § 1.8 corrected in
  the same move — one dated line each (2); the RESUME (1).

## Red today

R-conformity-c over `settings-field-boolean` and `screen-profile`: both switches are the `ui` part (class and
geometry equal) — falls on the settings field. The switch arm: **1** hit (`panel-field.tsx:74` is a
`role="switch"` on a non-`ui` drawing — the arm reads the role beside a class that is not `toggleSwitch`, said in its
docstring).

## The one visible change

The settings switch is 46 × 28 with the `::after` knob instead of 48 × 28 with a child knob — the report names none;
if the oracle reads more than that 2 px, STOP A.

## Mutation

Re-add `fieldToggle` on the field → R-conformity-c falls by name.

## Oracle: states that diverge, declared by name

Every `settings-field-boolean`-family state drawing a boolean (built by script).

## Commit

`refactor(maquette-conformity): one switch, toggleSwitch — and L16-bis names it truly`
