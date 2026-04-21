# Implementation Progress — PersonalScraper v15

> **For Claude:** Read this file at the start of each session. It indicates exactly where to resume.
> Update **after each completed task** (check the checkbox, update "Next action", commit).
> Never batch updates.

**Archive v14:** `docs/archive/v14/IMPLEMENTATION.md`
**Branch:** _(to be defined by /implement-version)_
**PR merge:** auto-merge | auto-squash | manual _(filled by /implement-version)_
**PR:** _(created after last phase)_
**Design spec:** `docs/v15-config-driven/DESIGN.md`
**Master plan:** `docs/v15-config-driven/plan/INDEX.md`

## Global Status

| Phase | Name                                                | Status | Last Update |
| ----- | --------------------------------------------------- | ------ | ----------- |
| 1     | Bootstrap — golden table + conf foundation          | [ ]    |             |
| 2     | Classifier pipeline + équivalence V14↔V15           | [ ]    |             |
| 3     | Resolver + Example Parser                           | [ ]    |             |
| 4     | Migration module + init-config command              | [ ]    |             |
| 5     | CLI integration — top-level --config + eager load   | [ ]    |             |
| 6     | Settings allégé + Dispatch refactor                 | [ ]    |             |
| 7     | Scraper refactor — classifier + TMDB keywords + NFO | [ ]    |             |
| 8     | Library refactor — prefs fusion + IDs               | [ ]    |             |
| 9     | Verify/Enforce/Sorter + Tests refactor              | [ ]    |             |
| 10    | Documentation + finalization + PR                   | [ ]    |             |

## Next Action

**Phase 1 — Bootstrap** : lire `docs/v15-config-driven/plan/phase-01-bootstrap.md`, lancer `/implement-version` pour créer la branch et démarrer l'implémentation.

## Detailed Tracking

_(Filled phase by phase as the plan progresses)_

---

**10 phases, 70 sous-phases** — Modules:

- **Nouveaux** : `personalscraper/conf/` (ids, models, loader, classifier, resolver, example_parser, migration), `personalscraper/commands/` (init_config)
- **Refactor** : `personalscraper/config.py` (allégé), `dispatch/*`, `scraper/*`, `library/*` (preferences supprimé), `verify/*`, `enforce/*`, `sorter/*`, `cli.py`, `pipeline.py`, `notifier.py`
- **Supprimé** : `personalscraper/genre_mapper.py`, `personalscraper/library/preferences.py`
- **Tests** : 434 hardcoded occurrences éliminés, fixture `test_config` unifiée
- **Config** : `config.example.json5` + `config.json5` (gitignored) + `MIGRATION.md`
