# Residue 2 — the unconverted fixture families leave the engine

Pending Q5 (ruling 98): renamed b·13… inside L13b or the new sub-lot's letter when the operator decides.

**Kind**: CONVERSION. **Cost**: Estimate ≤ 15 points (measure 11). The mean of L13b's measured phase costs is 11 (b·9 13, b·10 3, b·11 21, b·12 6.5); a phase above the mean says why.

## Measured

Figures measured on `1cb0a2dc1` (rebased on main `72712bb51`) by a throwaway measurement script (per-name block sizes and product-file readers; not committed) — block sizes are non-blank lines of `engine/legacy.js` per top-level name; « readers » counts product files (features/, app/, lib/, ui/, mocks/) naming it, an UPPER bound for generic words (`render`, `toast`, `view`, `select`, `follows`).

- Eleven families are register class `served` with a seed ALREADY on disk and no `converted` stamp — the engine's
  literal is a copy the correspondence arm still compares: `ACCOUNT` 36 → `account.json`, `JOURNAL` 41 →
  `deletion-journal.json`, `SERVICES` 55 → `services.json`, `DISKS` 30 → `disks.json`, `INDEX` 37 →
  `index-health.json`, `DEPENDENCIES` 23 → `dependencies.json`, `ERRORS` 16 → `errors.json`, `EXECUTIONS` 59 →
  `pipeline-executions.json`, `SECRETS` 42 → `secrets.json`, `LIB_TOTAL` 13 → `library-total.json`,
  `CADENCE_CRON` 1 → `grab-cadence.json`. For each: its product readers (3–6 files, through the reference slices)
  read the served query instead, the literal is deleted, the register row stamped `converted`.
- `POSTERS_HD` 54 (class `asset`) → `posters-high-definition.json`, same movement.
- `TODAY` 158 (class `unserved`) → the mock scenario's own date (`scenario().now`), which the layer already answers
  with; `mocks.py` re-aimed there (the phase-b13 list names it).

## The proof first

the surfaces' existing rules (system, maintenance, account, secret_acts, settings) stay green; `check-mock-seeds.py`'s classification count falls from 32 by exactly the families moved, read before and after.

## Named states and the oracle

The named states that draw each moved name are re-taken by grep at the phase's opening (`window.__go` ids under
`harness/states/`); oracle expectation: per surface, ZERO divergence (the seeds were held equal to the literals by the correspondence arm); STOP B otherwise.

## Gate

Per INDEX « Gates »: contracts + oracle + the named rules, logs postdating the commit; mutations by name where a rule
was written or re-aimed.
