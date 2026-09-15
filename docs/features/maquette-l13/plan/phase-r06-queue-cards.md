# r·6 — The queue cards take the contract's names

2026-09-15 (ruling 105): r·6 « contract names » was cut into six numbered sub-phases, one family group each — r·6 queue cards, r·7 arrivals decisions and pipeline, r·8 follows and incompletes, r·9 suggestions, search and releases, r·10 library, settings, maintenance, account and SCHEDULERS, r·11 the sheet — and « the file dies » became r·12.

2026-09-15 (r·6 done; steward, cost 0, for r·7–r·12): before each family's gate the harness `.py` files' multi-line JS blocks are swept for the family's one-letter keys and what the sweep finds is listed on the phase's dated line, even when zero — r·6's line grep missed `page_host.py`'s `first.t`, which the first gate caught as a crash. r·6's sweep: ten readers (two_picks, resolution_card, busy, take, resolution_window, seeds_at_rest, acted_surface_redraws, journey_verbs, url_state, page_host); remaining one-letter reads in those files belong to follows (r·8) and settings (r·10).

**Kind**: CONVERSION. **Cost**: Estimate ≈ 11 points (measure 11, ≤ 15).

## Measured

On `533c160e5` (STOP D answered by ruling 105): the eight queue-card families through the `$card` shorthand (`t`→title, `s`→secondaryLine, `r`→reason, `noposter`→withoutPoster, tuple `chip`→tone/text): BLOCKED, DONE_TODAY, INFLIGHT, MOVING, NOTFOUND_REAL, SETTLED_REAL, STUCK_REAL, TAKEABLE. Callers `app/engine-data.ts`, `lib/queue.ts`, `features/arrivals/queries.ts`; `QueueCard` read by 9 files.

## Measured before the cut (r·6 « contract names »)

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

no new rule; the surfaces' rules, the re-aimed cache readers and `check-mock-seeds.py --arm lossless` (the projection's
own proof, over the families still projected).

## Named states and the oracle

The named states that draw each family are re-taken by grep at the phase's opening (`window.__go` ids under
`harness/states/`), and the `__queries` readers under `harness/` grepped for the family's engine field names.

## Method (ruling 105)

Per family the query drops its projection (`toEngineShape`) and its type becomes the contract's schema
(`contract/types.d.ts`). `tsc`'s diagnostics are the exhaustive list of typed readers; each site is corrected by a
scripted replacement at the reported line:column (ruling 65), the diff re-read. Untyped readers — `QueueCard` and
`MediaSheet`'s `Record`, the markup `.ts` templates, the rules reading `__queries` — receive the contract type FIRST in
the same sub-phase so `tsc` sees them; the rest is grepped by family name and field. The rename tool is NOT used on
one-letter keys (tree-wide, it would move every `.t`). Oracle expectation: ZERO divergence; STOP B otherwise.
Re-aimed rules: said in docstring and body, one mutation by name per rule; above five in a sub-phase, one mutation of
the query per family that fells all its named rules, each FAIL line read.

## Gate

Per INDEX « Gates »: contracts + oracle + the named rules (the surfaces' rules and every re-aimed cache reader), logs
postdating the commit; `check-mock-seeds.py --arm lossless` green over the families still projected.
