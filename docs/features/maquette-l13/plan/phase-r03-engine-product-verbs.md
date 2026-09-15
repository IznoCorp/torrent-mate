# r·3 — the engine's product verbs: the settings machine, the add and delete verbs, the press

Q5 = B (ruling 99, 2026-09-15): this is a phase of L13r — The engine's residue; renamed from `phase-residue-N`.

2026-09-15 (ruling 101): renumbered — r·3 was cut into r·3 (the engine's product verbs) and r·4 (the engine's frame verbs), and every later phase moved up one. `SETTINGS_STATE` and `settingId` stay published on `__referentiel` from their module, owed to r·5.

**Kind**: BEHAVIOUR (b·1–b·12's shape). **Cost**: Estimate ≤ 15 points (measure 11). The mean of L13b's measured phase costs is 11 (b·9 13, b·10 3, b·11 21, b·12 6.5); a phase above the mean says why.

## Measured

Figures measured on `1cb0a2dc1` (rebased on main `72712bb51`) by a throwaway measurement script (per-name block sizes and product-file readers; not committed) — block sizes are non-blank lines of `engine/legacy.js` per top-level name; « readers » counts product files (features/, app/, lib/, ui/, mocks/) naming it, an UPPER bound for generic words (`render`, `toast`, `view`, `select`, `follows`).

- **The settings machine**: `SETTINGS_STATE` 10 (11 readers), `resetSettings` 8, `settingId` 1 (4),
  `displayedValue` 6 (5), `fileName` 3 (5), `changedFiles` 8 (6), `typedValue` 18 (3) → `features/settings/`.
- **The search mount and the press**: `addVerb` 24 (4) → `features/acquisition/` via `fr.json`; `mountSearch` 27 dies
  (`follows-filters.tsx` owns `#follq` and its handler); `mountLoaders` 22, `pressArbitration` 24,
  `panelUnderFinger` 7 → `lib/press-arbitration.ts`.
- **The library's delete**: `actionDelete` 14 (2) → `features/library/` via `fr.json`.
- **The names no reader has** (measured 2026-09-15 on c29a5c5c7): `follows`, `queued`, `suggestions`, `setOpen`, `cadre`,
  `sugVerb`, `navigationRows`, `openSheet` (a tripwire that throws) — they die.

## The proof first

RULE FIRST where no hold exists: the phase's opening grep lists the moved functions no rule taps (b·12's retry verb was born without one); each such hold is written and seen red against the engine before its move, mutations by name.

## Named states and the oracle

The named states that draw each moved name are re-taken by grep at the phase's opening (`window.__go` ids under
`harness/states/`); oracle expectation: zero divergence at rest; the rule-first line names the one behaviour each move could lose (the settings edit, the redraw after an act, the search's first result) — divergence is STOP B.

## Gate

Per INDEX « Gates »: contracts + oracle + the named rules, logs postdating the commit; mutations by name where a rule
was written or re-aimed.
