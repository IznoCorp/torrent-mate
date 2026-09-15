# r·4 — the engine's frame verbs: the redraw, the state read, the message and the layers' old verbs

Q5 = B (ruling 99, 2026-09-15): this is a phase of L13r — The engine's residue; renamed from `phase-residue-N`.

2026-09-15 (ruling 101): renumbered — r·3 was cut into r·3 (the engine's product verbs) and r·4 (the engine's frame verbs), and every later phase moved up one. `render` → `app/` with one `lib/` door for its 18 product readers; `applyState` → `app/layers.ts` (ruling 86-bis); the harness's bare names (`state`, `store`, `view`, `applyState`, `render`, `closeSheet`, `showSignIn`, `toast`) republished from `harness/publish.ts` under the same names. The MIDPOINT full suite follows this phase.

**Kind**: BEHAVIOUR (b·1–b·12's shape). **Cost**: Estimate ≤ 15 points (measure 11). The mean of L13b's measured phase costs is 11 (b·9 13, b·10 3, b·11 21, b·12 6.5); a phase above the mean says why.

## Measured

Figures measured on `1cb0a2dc1` (rebased on main `72712bb51`) by a throwaway measurement script (per-name block sizes and product-file readers; not committed) — block sizes are non-blank lines of `engine/legacy.js` per top-level name; « readers » counts product files (features/, app/, lib/, ui/, mocks/) naming it, an UPPER bound for generic words (`render`, `toast`, `view`, `select`, `follows`).

- **The redraw and the state read**: `render` 63 (the `__referentiel.render` reads: 10), `currentState` 43,
  `applyState` 14 (ruling 16 re-dated here), `beforeReset` 33, `view`/`select`/`setOpen`/`navigationRows` →
  `app/` or the harness (applyState is the harness's since b·12).
- **The message and the layers' old verbs**: `toast` 5, `toastUndo` 8, `closeSheet` 44, `showSignIn` 19,
  `__navEchec`'s initialisation → their doors (`lib/shell-doors.ts`) and their features; ruling 88's « who else answers ».

## The proof first

RULE FIRST where no hold exists: the phase's opening grep lists the moved functions no rule taps (b·12's retry verb was born without one); each such hold is written and seen red against the engine before its move, mutations by name.

## Named states and the oracle

The named states that draw each moved name are re-taken by grep at the phase's opening (`window.__go` ids under
`harness/states/`); oracle expectation: zero divergence at rest; the rule-first line names the one behaviour each move could lose (the settings edit, the redraw after an act, the search's first result) — divergence is STOP B.

## Gate

Per INDEX « Gates »: contracts + oracle + the named rules, logs postdating the commit; mutations by name where a rule
was written or re-aimed.
