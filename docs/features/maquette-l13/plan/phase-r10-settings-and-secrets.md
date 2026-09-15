# r·10 — The settings and the secrets take the contract's names

2026-09-15 (ruling 105): r·6 « contract names » was cut into six numbered sub-phases, one family group each — r·6 queue cards, r·7 arrivals decisions and pipeline, r·8 follows and incompletes, r·9 suggestions, search and releases, r·10 library, settings, maintenance, account and SCHEDULERS, r·11 the sheet — and « the file dies » became r·12.

2026-09-15 (ruling 107): r·10 as ruling 105 cut it measured ≈ 18 and was cut — r·10 settings and secrets, r·11 library, maintenance actions and account, r·12 the system families with JOURNAL and SCHEDULERS (every family whose rows are `Fact`, one decision on `Fact`), r·13 the sheet, r·14 « the file dies ».

2026-09-15 (r·10 done): harness sweep — reads: 35 lines in 7 rules (settings, settings_editing, page_host, producers, secret_acts, seeds_at_rest, redraw_entry); object LITERALS handed to the product with engine keys: `settings.py:478` (`__settingLabels.label({f, c, n})`, missed by the read sweep, caught by the first gate, now `{file, key, name}`) and no other; `settings.py:95` reads a topic's `r.f`, a key neither the engine nor the contract gives a topic, left. Calls with a string or generic family on these keys: none. `Setting.topic` is optional — only a flattened setting carries its rubric.

**Kind**: CONVERSION. **Cost**: Estimate ≈ 10 points (measure 11, ≤ 15).

## Measured

On `ee8455d98` (ruling 107): SETTINGS (`t`→title, `s`→secondaryLine, `r`→settings; per setting `f`→file, `c`→key,
`brut`→raw, `n`→name, `v`→displayedValue, `brut` and `v` opaque) and SECRETS (`k`→key, `l`→label, `def`→defined).
`Setting` read by 14 files, `SettingsTopic` by 6, `Secret` by 4; a setting's identifier `file:key` keys
`SETTINGS_STATE.modifs` and the rules. Estimate ≈ 10 points (measure 11, below the mean).

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
