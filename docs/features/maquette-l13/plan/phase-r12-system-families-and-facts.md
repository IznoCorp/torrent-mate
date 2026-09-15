# r·12 — The system families, JOURNAL and SCHEDULERS take the contract's names

2026-09-15 (ruling 106, amended by order 38): the system families projected through `features/system/queries.ts`'s generic `family` parameter are a new phase r·11; the sheet became r·12 and « the file dies » r·13.

2026-09-15 (ruling 107): r·10 as ruling 105 cut it measured ≈ 18 and was cut — r·10 settings and secrets, r·11 library, maintenance actions and account, r·12 the system families with JOURNAL and SCHEDULERS (every family whose rows are `Fact`, one decision on `Fact`), r·13 the sheet, r·14 « the file dies ».

**Kind**: CONVERSION. **Cost**: Estimate ≈ 12 points (measure 11, ≤ 15; the mean of L13b's measured phases is 11).

## Measured

On `42e333d1b` (ruling 106) and `ee8455d98` (ruling 107): `features/system/queries.ts`'s `useSystemRead(address, family)`
projects DISKS, INDEX, DEPENDENCIES and SCHEDULERS (the `$fact` shorthand: `l`→label, `ton`→tone, `v`→value,
`s`→secondaryLine), ERRORS and EXECUTIONS (`q`/`ok`/`d`/`r` renames); `features/maintenance/queries.ts` projects JOURNAL
(`lignes`→rows, `l`/`v`/`s`). Every one of these rows is `lib/engine-drawing.ts`'s `Fact`, the input of
`ui/fact-rows.tsx`. THE DECISION ON `Fact` (ruling 107): its keys become full words — label, value, secondaryLine,
tone — under the code-naming rule, and no hand-written projection survives; only if this phase's measure at opening
exceeds 15 with that rename does the conversion live in `lib/` while `ui/` keeps its vocabulary, said with the count.
Each read's key is its address.

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
