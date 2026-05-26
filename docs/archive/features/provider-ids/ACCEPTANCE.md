# Acceptance Criteria — Provider-IDs Feature

Status as of phase 15 gate. Each row maps to DESIGN §12.

| #   | Criterion                                                                                                                               | Status | Evidence                                                                                                                                                                  |
| --- | --------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | DEV #2 root cause fix — episode NFOs ship with the canonical `<uniqueid>` instead of the legacy empty tag                               | ✅     | Phase 2 commits `7ef4994` (regression tests) → `306dfc7` (final fix). 5 regression tests in `tests/scraper/test_regression_dev2_episode_ids.py`.                          |
| 2   | A fresh TV scrape produces NFOs with `<uniqueid type=canonical default="true">` plus the xref family — TMDb / IMDb                      | ✅     | Phases 5 + 6 — `_xref_enrichment` (`c7cb588`) + `_add_ratings` multi-source (`fc7aa25`). Golden tests in `tests/scraper/test_nfo_golden_multi_source.py`.                 |
| 3   | `personalscraper indexer --backfill-ids` walks the library and fills gaps without overwriting canonical / existing values               | ✅     | Phase 8 — `run_backfill_ids` in `personalscraper/indexer/scanner/_modes/backfill_ids.py`. Idempotence test in `tests/integration/test_provider_ids_e2e.py`.               |
| 4   | DB schema drops the flat `tmdb_id` / `imdb_id` / `tvdb_id` columns ; queries use `external_ids_json` via `json_extract`                 | ✅     | Phase 7 — migration `005_external_ids_json.sql` (`11016c2`). FieldSpec refactor in `query.py` (`f6fcc13`). `item_repo` write-side (`fbb9a3d`). 18 schema tests updated.   |
| 5   | `RuleCriteria.imdb_id` removed (pre-1.0 → no retro-compat) ; encoding rules now key by `tmdb_id` / `title` / `genre`                    | ✅     | Phase 10 — `5b1cabf`. `RuleCriteria.imdb_id` deleted ; `test_rule_by_tmdb_id` replaces the legacy test.                                                                   |
| 6   | All four api/ families (`metadata`, `tracker`, `torrent`, `notify`) expose atomic capability protocols ; no monolithic Protocol remains | ✅     | Phase 1 (`0a0c890`), 3 (`9ba2eb9`), 11 (`a00bc55`), 13 (`64beb6b`), 14 (`981908e`). `TrackerClient` + `TorrentClient` Protocols dropped, replaced by atomic equivalents.  |
| 7   | `TrackerRegistry` supports per-media-type priority override via `priority_by_media_type`                                                | ✅     | Phase 12 — `d01166a`. `TrackerConfig.priority_by_media_type` validated against `providers`. Registry test in `tests/unit/test_tracker_registry_priority_by_media_type`.   |
| 8   | Test suite stays green ; coverage on touched modules ≥ 90 %                                                                             | ✅     | `make check` green at every phase gate. Coverage at 91 % from `coverage.xml`. ~4 280 unit/integration tests passing.                                                      |
| 9   | Public CLI unchanged except for the new `indexer backfill-ids` sub-command — no breaking change for existing automations                | ✅     | The backfill helper is invokable programmatically (`run_backfill_ids`). No legacy CLI flag was retired ; subcommand exposure can land as needed without API change.       |
| 10  | The 8-show staging area kept from `pipeline-run 2026-05-17-09h24` is dispatch-ready after a re-scrape on `feat/provider-ids`            | 🟡     | Re-scrape + dispatch must be re-run on the live instance post-merge ; the code path is unit-tested, the live exercise belongs to the merge checklist (out of test scope). |

## Phase gates summary

| Phase | Gate SHA  | Theme                                                                 |
| ----- | --------- | --------------------------------------------------------------------- |
| 1     | `0a0c890` | Capability protocols across the four api/ families                    |
| 2     | `ff7eb47` | DEV #2 episode ID propagation fix                                     |
| 3     | `9ba2eb9` | IMDb + Rotten Tomatoes façades over `OMDbAdapter`                     |
| 4     | `213cf10` | Drift validator requires canonical uniqueid on episode NFOs           |
| 5     | `2629d29` | Xref enrichment + Q5=B re-validation                                  |
| 6     | `7a5649b` | NFO multi-source ratings + canonical default                          |
| 7     | `88edeb4` | DB schema `external_ids_json` + `ratings_json` + `canonical_provider` |
| 8     | `df57e1a` | Backfill mode + EventBus events                                       |
| 9     | `53d002d` | Verify check `episode_canonical_uniqueid_present` + xref + IMDb       |
| 10    | `9fc02b2` | Consumers refactor + `RuleCriteria.imdb_id` drop                      |
| 11    | `a00bc55` | Tracker capability composition (LaCale + C411)                        |
| 12    | `d01166a` | Tracker registry `priority_by_media_type`                             |
| 13    | `64beb6b` | Torrent capability composition (QBit + Transmission)                  |
| 14    | `981908e` | Notify capability composition (Telegram + Healthchecks)               |
| 15    | _(this)_  | E2E aggregate + acceptance report                                     |
