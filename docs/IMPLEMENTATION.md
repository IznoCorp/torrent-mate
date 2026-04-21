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
| 3     | Resolver + Example Parser                           | [ ]    |             |
| 4     | Migration module + init-config command              | [ ]    |             |
| 5     | CLI integration — top-level --config + eager load   | [ ]    |             |
| 6     | Settings allégé + Dispatch refactor                 | [ ]    |             |
| 7     | Scraper refactor — classifier + TMDB keywords + NFO | [ ]    |             |
| 8     | Library refactor — prefs fusion + IDs               | [ ]    |             |
| 9     | Verify/Enforce/Sorter + Tests refactor              | [ ]    |             |
| 10    | Documentation + finalization + PR                   | [ ]    |             |

## Next Action

**Phase 3 — Resolver + Example Parser** : lire `docs/v15-config-driven/plan/phase-03-resolver-parser.md`, implémenter `conf/resolver.py` (`folder_for`, `pick_disk_for`) + `conf/example_parser.py` (extraction commentaires `//` → prompts).

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

---

**10 phases, 69 sous-phases** — Modules:

- **Nouveaux** : `personalscraper/conf/` (ids, models, loader, classifier, resolver, example_parser, migration), `personalscraper/commands/` (init_config)
- **Refactor** : `personalscraper/config.py` (allégé), `dispatch/*`, `scraper/*`, `library/*` (preferences supprimé), `verify/*`, `enforce/*`, `sorter/*`, `cli.py`, `pipeline.py`, `notifier.py`
- **Supprimé** : `personalscraper/genre_mapper.py`, `personalscraper/library/preferences.py`
- **Tests** : 434 hardcoded occurrences éliminés, fixture `test_config` unifiée
- **Config** : `config.example.json5` + `config.json5` (gitignored) + `MIGRATION.md`
