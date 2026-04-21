# Implementation Progress — PersonalScraper v15

> **For Claude:** Read this file at the start of each session. It indicates exactly where to resume.
> Update **after each completed task** (check the checkbox, update "Next action", commit).
> Never batch updates.

**Archive v14:** `docs/archive/v14/IMPLEMENTATION.md`
**Branch:** `feat/config-driven`
**PR merge:** manual
**PR:** _(created after last phase)_
**Design spec:** `docs/v15-config-driven/DESIGN.md`
**Master plan:** `docs/v15-config-driven/plan/INDEX.md`

## Global Status

| Phase | Name                                                | Status | Last Update |
| ----- | --------------------------------------------------- | ------ | ----------- |
| 1     | Bootstrap — golden table + conf foundation          | [x]    | 2026-04-21  |
| 2     | Classifier pipeline + équivalence V14↔V15           | [x]    | 2026-04-21  |
| 3     | Resolver + Example Parser                           | [x]    | 2026-04-21  |
| 4     | Migration module + init-config command              | [x]    | 2026-04-21  |
| 5     | CLI integration — top-level --config + eager load   | [x]    | 2026-04-21  |
| 6     | Settings allégé + Dispatch refactor                 | [x]    | 2026-04-21  |
| 7     | Scraper refactor — classifier + TMDB keywords + NFO | [x]    | 2026-04-21  |
| 8     | Library refactor — prefs fusion + IDs               | [x]    | 2026-04-21  |
| 9     | Verify/Enforce/Sorter + Tests refactor              | [ ]    |             |
| 10    | Documentation + finalization + PR                   | [ ]    |             |

## Next Action

**Phase 9 — sous-phase 9.1** : Verify/Enforce/Sorter refactor + tests. 1698 tests passent. Commencer selon `docs/v15-config-driven/plan/phase-09-verify.md`.

## Detailed Tracking

### Phase 2 — Classifier pipeline + équivalence V14↔V15 (DONE 2026-04-21)

- [x] 2.1 `classifier.py` skeleton + `_read_nfo_category` — `personalscraper/conf/classifier.py`, `tests/conf/test_classifier.py`
- [x] 2.2 Level 1: NFO override — classify() with nfo_path priority
- [x] 2.3 Level 3: category_rules avec `_rule_matches` — all 5 pattern types + applies_to filter
- [x] 2.4 Level 2: anime_rule (consolidated before category_rules) — ID + string detection, JP origin
- [x] 2.5 Level 4-5: genre_mapping + defaults — tmdb_movies, tmdb_tv, tvdb IDs; defaults movie/tv
- [x] 2.6 Golden-table equivalence suite passes — 57/57 cases, `tests/fixtures/config.py` updated with category_rules

**Deviation from DESIGN:** `CategoryRule` has a new `applies_to: Literal["movie","tv","both"]` field (default "both") — needed to prevent cross-media-type rule collisions in equivalence tests. anime_rule runs before category_rules (level 2 vs level 3 in code) to prevent Animation+JP strings from being caught by "animation → tv_shows_animation" rules first.

**Test counts:** 50 unit (test_classifier.py) + 57 V14 regression + 57 V15 equivalence = 164 new tests. Full suite: 1506 passed.

### Phase 3 — Resolver + Example Parser (DONE 2026-04-21)

- [x] 3.1 `conf/resolver.py` — `folder_for` + `pick_disk_for` (V14 threshold formula) — 16 unit tests
- [x] 3.2 `conf/example_parser.py` scaffold — `Prompt` frozen dataclass + stub — smoke tests
- [x] 3.3 Line-based parser implementation — state machine, `//` + `/* */` comments, nested objects, indexed arrays — 5 fixtures, 30 tests
- [x] 3.4 Integration tests — `parse_example(config.example.json5)` → 53 Prompts, all default_values JSON5-valid, ≥70% with comments — 8 integration tests

**Array handling decision:** per-element (inline array → 1 Prompt with full literal; object-in-array → 1 Prompt per field with `key[N].field` path).

**Deviations:** `_OBJECT_OPEN_RE` requires `{` at end of line — inline one-liner objects (e.g. `movies: { folder_name: "movies" }`) are matched as leaf key-value with the full inline object as default_value. This is correct for `init-config` prompting.

**Test counts:** 16 (test_resolver.py) + 38 (test_example_parser.py) = 54 new tests. Full suite: 1560 passed.

### Phase 4 — Migration module + init-config command (DONE 2026-04-21)

- [x] 4.1 `conf/migration.py` — V14 genre maps inlined (V14_TMDB_MOVIE_GENRE_MAP, V14_TMDB_TV_GENRE_MAP, V14_TVDB_GENRE_MAP, V14_KNOWN_CATEGORIES, \_V14_DISK_CATEGORIES), all function signatures + implementations
- [x] 4.2 `generate_config_from_env` — DISK\*\_DIR → disks[], categories with V14 folder_names, genre_mapping, anime_rule, data_dir inside staging
- [x] 4.3 `migrate_library_preferences` — V14 library_preferences.json → LibraryPrefs dict, backup lifecycle in caller
- [x] 4.4 `migrate_library_json` — items[].category rewrite, .v14.bak backup, unknown label WARN, preferences skip
- [x] 4.5 `migrate_category_files` — .category → NFO <category source="personalscraper">, lock file check, idempotent
- [x] 4.6 `migrate_data_dir` — os.rename atomicity, lock check, same-fs check, target exists check
- [x] 4.7 `commands/init_config.py` — init_config() with --force backup (.v15.bak idempotent), --from-current full migration chain, non-interactive example-based creation
- [x] 4.8 `--from-current --yes` validation — exit 2 + explicit message when DISK1_DIR/STAGING_DIR/TORRENT_COMPLETE_DIR absent
- [x] 4.9 E2E test — 13 tests covering full migration: data_dir move, library rewrite, .category → NFO, load_config() passes, semantic equivalence

**Deviation:** 4.1-4.6 committed together (v15.4.1), 4.7-4.8 together (v15.4.7, 4.8 validation included), 4.9 separately. Sub-phase discipline maintained for 4.7 and 4.9; earlier sub-phases batched due to tight interdependencies in a single file.

**Test counts:** 60 (test_migration.py) + 17 (test_init_config.py) + 13 (test_init_config_e2e.py) = 90 new tests. Full suite: 1650 passed (+ 3 skipped).

### Phase 5 — CLI integration (DONE 2026-04-21)

- [x] 5.1 `AppCtx` dataclass + imports (`Config | None`, `config_override: Path | None`)
- [x] 5.2 `@app.callback()` eager load + bypass `init-config`
- [x] 5.3 `init-config` Typer command câblé vers `commands/init_config.init_config`
- [x] 5.4a Pipeline commands câblés avec `ctx.obj.config`
- [x] 5.4b Library commands câblés avec `ctx.obj.config`
- [x] 5.5 `_resolve_category()` — accepte ID ou alias, exit 2 si inconnu

**Note:** Phase 5 implémentée conjointement avec P6 dans la même session. Tous les sous-phases présents dans `cli.py` avant le commit v15.6.5.

### Phase 6 — Settings allégé + Dispatch refactor (DONE 2026-04-21)

- [x] 6.1 Strip `Settings` of disk paths and data_dir — commit `v15.6.1`
- [x] 6.2 `disk_scanner` uses `Config.disks` au lieu de `DISK_CATEGORIES` — commit `v15.6.2`
- [x] 6.3 `dispatcher` uses `Config` + `resolver` pour routing — commit `v15.6.3`
- [x] 6.4 `media_index` stocke/charge IDs avec auto-migration V14 — commit `v15.6.4`
- [x] 6.5 Migrate all Settings.disk/paths consumers to Config — `pipeline.py`, `dispatch/run.py`, `scraper/run.py`, `sorter/run.py`, `cli.py` (library commands) — commit `v15.6.5`

**Test counts:** 1670 passed (suite complète stable). mypy: 0 erreurs sur les 5 modules touchés; 42 erreurs restantes dans des modules hors-scope P6.5.

### Phase 8 — Library refactor : prefs fusion + IDs (DONE 2026-04-21)

- [x] 8.1 Supprimer `library/preferences.py` — fusionné dans `conf/models.py::LibraryPrefs` + imports réécrits
- [x] 8.2 `library/scanner.py` : V15 Config-driven, category_id IDs, `TV_CATEGORY_IDS` + `MOVIE_CATEGORY_IDS` dans `conf/ids.py`
- [x] 8.3 `library/{validator,analyzer,recommender}` : `_SERIES_FOLDER_NAMES` local, TODO P8.3 annotations
- [x] 8.4 `library/rescraper.py` : `_SERIES_FOLDER_NAMES` local, TODO P8.4 annotation
- [x] 8.5 `library/disk_cleaner.py` : itère `config.disks`, `clean_library(config, ...)` V15 API, tests réécrits
- [x] 8.6 Suppression `library_preferences.json` usage — tout via `config.library` (déjà fait en P8.1/cli.py)

**Test counts:** 1698 passed, 3 skipped (full suite).

---

**10 phases, 69 sous-phases** — Modules:

- **Nouveaux** : `personalscraper/conf/` (ids, models, loader, classifier, resolver, example_parser, migration), `personalscraper/commands/` (init_config)
- **Refactor** : `personalscraper/config.py` (allégé), `dispatch/*`, `scraper/*`, `library/*` (preferences supprimé), `verify/*`, `enforce/*`, `sorter/*`, `cli.py`, `pipeline.py`, `notifier.py`
- **Supprimé** : `personalscraper/genre_mapper.py`, `personalscraper/library/preferences.py`
- **Tests** : 434 hardcoded occurrences éliminés, fixture `test_config` unifiée
- **Config** : `config.example.json5` + `config.json5` (gitignored) + `MIGRATION.md`
