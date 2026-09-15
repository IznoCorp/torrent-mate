# r·15 — `legacy.js`, `seams.ts` and every instrument that reads them die; the full gate

Q5 = B (ruling 99, 2026-09-15): this is a phase of L13r — The engine's residue; renamed from `phase-residue-N`.

2026-09-15 (ruling 101): renumbered — r·3 was cut into r·3 (the engine's product verbs) and r·4 (the engine's frame verbs), and every later phase moved up one.

2026-09-15 (ruling 105): r·6 « contract names » was cut into six numbered sub-phases, one family group each — r·6 queue cards, r·7 arrivals decisions and pipeline, r·8 follows and incompletes, r·9 suggestions, search and releases, r·10 library, settings, maintenance, account and SCHEDULERS, r·11 the sheet — and « the file dies » became r·12.

2026-09-15 (ruling 106, amended by order 38): the system families projected through `features/system/queries.ts`'s generic `family` parameter are a new phase r·11; the sheet became r·12 and « the file dies » r·13.

2026-09-15 (ruling 107): r·10 as ruling 105 cut it measured ≈ 18 and was cut — r·10 settings and secrets, r·11 library, maintenance actions and account, r·12 the system families with JOURNAL and SCHEDULERS (every family whose rows are `Fact`, one decision on `Fact`), r·13 the sheet, r·14 « the file dies ».

2026-09-15 (ruling 109): r·13 measured ≈ 18–19 and was cut — r·13 the sheet (conversion only), r·14 « the projection dies » (new), r·15 « the file dies ».

**Kind**: DELETION. **Cost**: Estimate ≤ 15 points (measure 11). The mean of L13b's measured phase costs is 11 (b·9 13, b·10 3, b·11 21, b·12 6.5); a phase above the mean says why.

## Measured

Figures measured on `1cb0a2dc1` (rebased on main `72712bb51`) by a throwaway measurement script (per-name block sizes and product-file readers; not committed) — block sizes are non-blank lines of `engine/legacy.js` per top-level name; « readers » counts product files (features/, app/, lib/, ui/, mocks/) naming it, an UPPER bound for generic words (`render`, `toast`, `view`, `select`, `follows`).

- The current `phase-b13-legacy-js-dies.md` text, unchanged in substance: `engine/legacy.js` (1 600 today, ~0 after
  r·1–r·4), `engine/seams.ts` 183, `app/engine-data.ts` 101, `app/engine-redraw.ts` 45, `lib/engine-drawing.ts` 73;
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
