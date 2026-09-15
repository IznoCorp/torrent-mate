# r·10 — The library, settings, maintenance and account families take the contract's names

2026-09-15 (ruling 105): r·6 « contract names » was cut into six numbered sub-phases, one family group each — r·6 queue cards, r·7 arrivals decisions and pipeline, r·8 follows and incompletes, r·9 suggestions, search and releases, r·10 library, settings, maintenance, account and SCHEDULERS, r·11 the sheet — and « the file dies » became r·12.

**Kind**: CONVERSION. **Cost**: Estimate ≈ 14 points (measure 11, ≤ 15).

## Measured

On `533c160e5` (STOP D answered by ruling 105): LIBRARY (3 renames), CATS (3), SETTINGS (8), SECRETS (3), MAINT_ACTIONS (5), JOURNAL (4), ACCOUNT (1), SCHEDULERS (0, `features/system/fault.test.ts` only). `Setting` read by 13 files.

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
