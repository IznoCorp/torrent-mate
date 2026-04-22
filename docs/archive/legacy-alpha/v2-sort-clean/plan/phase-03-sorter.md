# Phase 3 — Strategies + Sorter orchestrator

## Objectif

Implémenter les strategies de tri et l'orchestrateur qui retourne list[SortResult].

## Sous-phases

### 2.3.1 — Sorting strategies

- [x] Créer `personalscraper/sorter/strategies.py`
- [x] Implémenter `SortingStrategy` (ABC), `MovieStrategy`, `TVShowStrategy`, `DefaultStrategy`
- [x] MovieStrategy : destination `001-MOVIES/Title (Year)/`, fuzzy match existants
- [x] TVShowStrategy : destination `002-TVSHOWS/Show Name/`, fuzzy match existants
- [x] DefaultStrategy : dispatch vers le bon dossier type (003-EBOOKS, 004-AUDIO, etc.)
- [x] Tests unitaires (13 tests)

**Commit** : `v2.3.1: Implement sorting strategies (Movie, TVShow, Default)` ✅

### 2.3.2 — Sorter orchestrator

- [x] Créer `personalscraper/sorter/sorter.py`
- [x] SortResult importé depuis `personalscraper/models.py`
- [x] Implémenter `Sorter.__init__(cleaner, dry_run)`
- [x] Implémenter `process(staging_dir)` → `list[SortResult]`
- [x] Implémenter `sort_item(item, staging_dir)` → `SortResult`
- [x] Gérer fichiers isolés ET dossiers
- [x] Support `--dry-run` (log sans move)
- [x] Gestion d'erreurs item par item (18 tests, error handling vérifié)

**Commit** : `v2.3.2: Implement Sorter orchestrator with SortResult returns` ✅
