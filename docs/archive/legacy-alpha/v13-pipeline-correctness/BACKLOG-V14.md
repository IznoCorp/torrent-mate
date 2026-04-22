# V14+ Backlog

Items deferred from V13 PIPELINE CORRECTNESS.

## From V13 Design

| #   | Priority | Description                                                                 | Source                         |
| --- | -------- | --------------------------------------------------------------------------- | ------------------------------ |
| 1   | Medium   | Remove `verify --fix` completely (deprecated in V13, warned)                | V13 design §Phase 3            |
| 2   | Low      | Add `--rebuild-index` CLI option for dispatch                               | V5 plan phase-03, V13 audit    |
| 3   | Medium   | Call `MediaIndex.remove_stale()` after index load/rebuild                   | V13 audit (dead code)          |
| 4   | Medium   | NFO generator: write genre ID attributes `<genre id="10764">`               | V13 genre mapper investigation |
| 5   | Medium   | Genre mapper: extract genre IDs from NFO for reliable categorization        | V13 design §Phase 3            |
| 6   | Low      | Fallout (2024): re-download for quality upgrade (data lost in pipeline run) | Bug #15                        |

## From V0-V12 Audit

| #   | Priority | Description                                                               | Source                                   |
| --- | -------- | ------------------------------------------------------------------------- | ---------------------------------------- |
| 7   | Low      | Add `--rebuild-index` CLI option for dispatch (no manual rebuild trigger) | V5 plan phase-03, AUDIT §V14+ Backlog #3 |

> Note: The audit V14+ backlog item #3 (`--rebuild-index`) is identical to item #2 above (from V13 design). All other audit findings (1 BUG and 1 MISSING from V5) were fixed in V13 Phase 1 (`MediaIndex.rebuild()` always-on) and classified for V14 (`remove_stale()` call). V0–V4 and V6–V10 had 0 open issues.
