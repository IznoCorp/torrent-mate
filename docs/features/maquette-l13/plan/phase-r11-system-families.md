# r·11 — The system families take the contract's names

2026-09-15 (ruling 106, amended by order 38): the system families projected through `features/system/queries.ts`'s generic `family` parameter are a new phase r·11; the sheet became r·12 and « the file dies » r·13.

**Kind**: CONVERSION. **Cost**: Estimate ≈ 12 points (measure 11, ≤ 15; the mean of L13b's measured phases is 11).

## Measured

On `42e333d1b` (ruling 106): `features/system/queries.ts`'s `useSystemRead(address, family)` projects DISKS, INDEX,
DEPENDENCIES (the `$fact` shorthand: `l`→label, `ton`→tone, `v`→value, `s`→secondaryLine), ERRORS, EXECUTIONS
(`q`/`ok`/`d`/`r` renames) and SCHEDULERS (also `$fact`, and r·10's by ruling 105 — whichever phase comes first takes
it, said on its dated line); each read's key is its address. Readers: the system page, the maintenance page's
schedulers, `features/system/fault.ts` and its test, `lib/engine-drawing.ts`'s `Fact`.

## The proof first

no new rule; the surfaces' rules, the re-aimed cache readers and `check-mock-seeds.py --arm lossless` over the families
still projected.

## Named states and the oracle

The named states that draw each family are re-taken by grep at the phase's opening (`window.__go` ids under
`harness/states/`), and the `__queries` readers under `harness/` grepped for the families' engine field names.

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
