# Phase 22 — The primary buttons are `actionButton` (D.1 #15, the operator's OPEN 8 = A)

**Ruled 2026-09-29** (`/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` § Q8, verbatim « A »):
`candidatePick` (the rounded-full pill) goes; « Choisir » becomes `actionButton({ kind: "panelAction", tone:
"primary" })` at 44 px; `saveAction` becomes `actionButton({ kind: "submit" })`, its literal `'Geist'` font gone. A
« pill » shape on `actionButton` is refused. The pill-to-button change is visible: accepted BY NAME.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "candidatePick|saveAction" -g '*.ts' -g '*.tsx' frontend/maquette/design/src` →
  `features/acquisition/variants.ts:221` used at `features/acquisition/resolution-cards.tsx:118` (`card/pick`);
  `features/settings/variants.ts:147` used at `features/settings/banners.tsx:109` (`data-save`).
- **Points ≈ 8.** Two call sites onto `actionButton` (≈ 6 lines, 2); two variants and the font literal gone (1);
  R-conformity-p (3); the RESUME (1); mutation (1).
- **Readers.** `settings_editing.py` (the save), `resolution_card.py` (the pick) — the parts and
  data attributes are kept; re-read at the opening.

## Red today

R-conformity-p on `acq-resolution-tie` and `settings-edited`: the pick and the save are the `ui` action button, the
pick at ≥ 44 px — falls.

## Mutation

Restore `candidatePick` → falls by name.

## Oracle: states that diverge, declared by name

The resolution states drawing a pick, `settings-edited` and the settings states showing the save bar (built by
script) — accepted by name.

## Commit

`refactor(maquette-conformity): the primary buttons are the one action button`
