# Residue 1 — the interface constants and the helpers find homes

Pending Q5 (ruling 98): renamed b·13… inside L13b or the new sub-lot's letter when the operator decides.

**Kind**: CONVERSION. **Cost**: Estimate ≤ 15 points (measure 11). The mean of L13b's measured phase costs is 11 (b·9 13, b·10 3, b·11 21, b·12 6.5); a phase above the mean says why.

## Measured

Figures measured on `1cb0a2dc1` (rebased on main `72712bb51`) by a throwaway measurement script (per-name block sizes and product-file readers; not committed) — block sizes are non-blank lines of `engine/legacy.js` per top-level name; « readers » counts product files (features/, app/, lib/, ui/, mocks/) naming it, an UPPER bound for generic words (`render`, `toast`, `view`, `select`, `follows`).

- **Interface constants** (register class `interface`), each to the ONE feature that reads it or to `lib/`
  when two do: `ST_LABEL` 10 / `ST_LABEL_MOVIE` 5 / `ST_TONE` 10 (4 readers), `URGENCY` 10 (2), `GROUPS` 22 (2),
  `EP_LABEL` 9 (4) / `EP_ORDER` 8 (1) / `EP_SWATCH` 28 (0), `REASON_LABEL` 6 (4) / `REASON_TONE` 6 (3) /
  `REASON_DETAIL` 11 (2), `DECISION_STATE` 5 (4) / `DECISION_STATE_DETAIL` 7 (2), `VIA_LABEL` 40 (3),
  `MAINT_TOPICS` 37 (3), `MOIS` 14 (0), `RESOLUTIONS` 1 (2), `AUDIOS` 117 (2), `LIB_PAGE` 38 (1),
  `SERVICES_PANNE` 13 (3, unregistered). French copy goes to `fr.json` (CLAUDE.md § Language), tokens stay code.
- **Helpers**: `svgIcon` 2 (7), `escapeHtml` 9 (7), `baseTitle` 5 (12), `initialsOf` 6 (0), `cadenceFR` 19 (2),
  `nextSearchFR` 14 (2), `stLabel` 7 (4), `stFraction` 8 (3), `gridBadge` 19 (2), `dateFR` 5 (0) — pure
  functions, moved with a vitest each where none exists; names with French stems renamed through
  `scripts/rename-identifiers.py`.
- **Zero-reader names die** instead of moving (`initialsOf`, `EP_SWATCH`, `MOIS`, `dateFR`), each confirmed dead by
  grep over `design/src` AND `harness/`.

## The proof first

no new rule (a conversion): the contracts tier + the named rules that draw each constant (state_surfaces, decision, system/maintenance page rules) stay green, counts unchanged; `check-frame-domain.py` read before and after (lib/ must not rise for a feature's word).

## Named states and the oracle

The named states that draw each moved name are re-taken by grep at the phase's opening (`window.__go` ids under
`harness/states/`); oracle expectation: the oracle holds the page at rest; a constant moved is a conversion — ZERO divergence, any divergence is STOP B.

## Gate

Per INDEX « Gates »: contracts + oracle + the named rules, logs postdating the commit; mutations by name where a rule
was written or re-aimed.
