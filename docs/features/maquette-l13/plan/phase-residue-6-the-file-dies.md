# Residue 6 — `legacy.js`, `seams.ts` and every instrument that reads them die; the full gate

Pending Q5 (ruling 98): renamed b·13… inside L13b or the new sub-lot's letter when the operator decides.

**Kind**: DELETION. **Cost**: Estimate ≤ 15 points (measure 11). The mean of L13b's measured phase costs is 11 (b·9 13, b·10 3, b·11 21, b·12 6.5); a phase above the mean says why.

## Measured

Figures measured on `1cb0a2dc1` (rebased on main `72712bb51`) by a throwaway measurement script (per-name block sizes and product-file readers; not committed) — block sizes are non-blank lines of `engine/legacy.js` per top-level name; « readers » counts product files (features/, app/, lib/, ui/, mocks/) naming it, an UPPER bound for generic words (`render`, `toast`, `view`, `select`, `follows`).

- The current `phase-b13-legacy-js-dies.md` text, unchanged in substance: `engine/legacy.js` (1 600 today, ~0 after
  residue 1–3), `engine/seams.ts` 183, `app/engine-data.ts` 101, `app/engine-redraw.ts` 45, `lib/engine-drawing.ts` 73;
  the parser arms (`classification`, `lossless`, `correspondence`), `ENGINE_SOURCES`, the French debt section and its
  arms, the size-ledger entry, `resync.py`, `FAN_IN_EXEMPT`'s engine entries, the harness reads (`mocks.py`,
  `said_and_done.py`, `page_host.py`, `navigation.py`).
- Then the lot's full gate: full suite, `--a11y`, `harness-hold-counts.py --compare`, `make lint`, rebase, PR READY
  (constitution §§ cited: behaviour phases exist in the lot).

## The proof first

`grep -rn "engine/legacy\|legacy\.js" frontend/maquette/design/src` lists nothing; `check-frontend-boundaries.py --arm size` lists no GRANDFATHERED file.

## Named states and the oracle

The named states that draw each moved name are re-taken by grep at the phase's opening (`window.__go` ids under
`harness/states/`); oracle expectation: zero divergence.

## Gate

Per INDEX « Gates »: contracts + oracle + the named rules, logs postdating the commit; mutations by name where a rule
was written or re-aimed.
