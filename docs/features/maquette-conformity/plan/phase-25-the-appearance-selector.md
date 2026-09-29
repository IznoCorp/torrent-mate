# Phase 25 — The Appearance selector redraws after a choice (a regression, the operator's defect)

**Reported 2026-09-29** (rulings file § « TWO DEFECTS », defect B): on any phone, choosing Système / Clair / Sombre
changes the theme but NOT the selector's pressed state. **Kind: defect, a REGRESSION** — dated before it is repaired.
Next to phase 24, which rewires the same selector onto `viewSwitch`.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `sed -n 74p frontend/maquette/design/src/app/drawer.tsx` → `const appearance = currentAppearance();`
  read once per render; `sed -n 170,178p frontend/maquette/design/src/app/drawer.tsx` → `aria-pressed={appearance ===
  mode}`, and the redraw left to `store.touch()` (**:177**); **the date**: `git log -S "store.touch()" --oneline --
  frontend/maquette/design/src/app/drawer.tsx` and the store's `touch` / `useUiState` history, then a bisect ON THE
  RED RULE if the text search does not name it — the commit named in the report and the RESUME.
- **Points ≈ 9.** The rule first — the selector's `aria-pressed` read AFTER a tap, on `drawer-navigation`, for each of
  the three choices (3); the repair (≈ 4 lines, 1); the dating (2); `BUGS.md` per order 57 — escaped from « aucune
  règle ne lit l'état du sélecteur APRÈS le choix », family « un contrôle qui change l'état sans se redessiner » (2);
  the RESUME (1).
- **Readers.** `appearance.py` (reads the theme, not the selector — the gap), `drawer.py`.

## Red today

R-conformity-t on `drawer-navigation`: after « Sombre » is tapped, « Sombre » is the pressed one — falls.

## Mutation

Revert the repair → falls by name.

## Oracle

Nothing drawn moves at rest.

## Commit

`fix(maquette-conformity): the Appearance selector shows the choice just made`
