# r·5 — `window.__referentiel` and the nine slices die

Q5 = B (ruling 99, 2026-09-15): this is a phase of L13r — The engine's residue; renamed from `phase-residue-N`.

2026-09-15 (ruling 101): renumbered — r·3 was cut into r·3 (the engine's product verbs) and r·4 (the engine's frame verbs), and every later phase moved up one.

**Kind**: CONVERSION. **Cost**: Estimate ≤ 15 points (measure 11). The mean of L13b's measured phase costs is 11 (b·9 13, b·10 3, b·11 21, b·12 6.5); a phase above the mean says why.

## Measured

Figures measured on `1cb0a2dc1` (rebased on main `72712bb51`) by a throwaway measurement script (per-name block sizes and product-file readers; not committed) — block sizes are non-blank lines of `engine/legacy.js` per top-level name; « readers » counts product files (features/, app/, lib/, ui/, mocks/) naming it, an UPPER bound for generic words (`render`, `toast`, `view`, `select`, `follows`).

- 43–45 product files read `window.__referentiel`, through nine `features/*/reference.ts` slices (acquisition 31
  members, arrivals 41, settings 25, library 16, system 16, maintenance 12, releases 9, media 5, account 1) and 37
  `use…Reference()` calls; direct reads `render` ×10, `icons` ×9, `SETTINGS_STATE` ×7, `addVerb` ×1 — all
  re-homed by r·1–r·4, so this phase deletes the object, `app/reference.d.ts` (46 lines), the slices, their hook
  calls, and the boundaries arm's reference-slice arm (phase-b13 amendment 1).

## The proof first

no new rule; `check-frontend-boundaries.py` reference-slice arm deleted with its subject (said in the body), fan-in and cycles read after.

## Named states and the oracle

The named states that draw each moved name are re-taken by grep at the phase's opening (`window.__go` ids under
`harness/states/`); oracle expectation: zero divergence; STOP B otherwise.

## Gate

Per INDEX « Gates »: contracts + oracle + the named rules, logs postdating the commit; mutations by name where a rule
was written or re-aimed.
