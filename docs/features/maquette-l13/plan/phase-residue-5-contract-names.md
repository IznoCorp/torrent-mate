# Residue 5 — engine-shape's families take the contract's names

Pending Q5 (ruling 98): renamed b·13… inside L13b or the new sub-lot's letter when the operator decides.

**Kind**: CONVERSION (may be lot-sized). **Cost**: Estimate ≤ 15 points (measure 11). The mean of L13b's measured phase costs is 11 (b·9 13, b·10 3, b·11 21, b·12 6.5); a phase above the mean says why.

## Measured

Figures measured on `1cb0a2dc1` (rebased on main `72712bb51`) by a throwaway measurement script (per-name block sizes and product-file readers; not committed) — block sizes are non-blank lines of `engine/legacy.js` per top-level name; « readers » counts product files (features/, app/, lib/, ui/, mocks/) naming it, an UPPER bound for generic words (`render`, `toast`, `view`, `select`, `follows`).

- `engine/engine-shape.ts` 306 lines; 41 `toEngineShape` call sites in 14 files over 24 family labels
  (ACCOUNT 1, BLOCKED 2, CATS 1, DECISIONS_REGLEES 1, DONE_TODAY 2, FOLLOWS 1, INCOMPLETE 2, INFLIGHT 2, JOURNAL 1,
  LIBRARY 1, MAINT_ACTIONS 1, MOVING 3, NOTFOUND_REAL 2, NOT_A_FAMILY 1, PENDING_DECISIONS 1, PIPELINE 1,
  SCHEDULERS 1, SECRETS 1, SETTINGS 1, SETTLED_REAL 3, SHEETS_RAW 1, STUCK_REAL 3, SUGGESTIONS 1, TAKEABLE 2).
- Each family is ONE sub-phase: its query drops the projection and every component reading `t`, `st`, `o`/`a`,
  `declencheurs`… reads the contract's field, through `scripts/rename-identifiers.py`, the oracle at zero per family.
  At one sub-phase per family and the mean cost, this is 24 × ~3 points: the auditor's reading decides whether it is a
  sub-lot of its own.

## The proof first

no new rule per family; the surfaces' rules and `check-mock-seeds.py --arm lossless` (the projection's own proof) — the lossless arm dies with the last family.

## Named states and the oracle

The named states that draw each moved name are re-taken by grep at the phase's opening (`window.__go` ids under
`harness/states/`); oracle expectation: zero divergence per family; STOP B otherwise.

## Gate

Per INDEX « Gates »: contracts + oracle + the named rules, logs postdating the commit; mutations by name where a rule
was written or re-aimed.
