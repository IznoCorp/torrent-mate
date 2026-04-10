# Phase 3 — Strategies + Sorter orchestrator

## Objectif

Implémenter les strategies de tri et l'orchestrateur qui retourne list[SortResult].

## Sous-phases

### 2.3.1 — Sorting strategies

- [ ] Créer `personalscraper/sorter/strategies.py`
- [ ] Implémenter `SortingStrategy` (ABC), `MovieStrategy`, `TVShowStrategy`, `DefaultStrategy`
- [ ] MovieStrategy : destination `001-MOVIES/Title (Year)/`, fuzzy match existants
- [ ] TVShowStrategy : destination `002-TVSHOWS/Show Name/`, fuzzy match existants
- [ ] DefaultStrategy : dispatch vers le bon dossier type (003-EBOOKS, 004-AUDIO, etc.)
- [ ] Tests unitaires

**Commit** : `v2.3.1: Implement sorting strategies (Movie, TVShow, Default)`

### 2.3.2 — Sorter orchestrator

- [ ] Créer `personalscraper/sorter/sorter.py`
- [ ] Implémenter `Sorter.__init__(settings, cleaner, dry_run)`
- [ ] Implémenter `process(staging_dir)` → `list[SortResult]`
- [ ] Implémenter `sort_item(item)` → `SortResult`
- [ ] Gérer fichiers isolés ET dossiers
- [ ] Support `--dry-run` (log sans move)
- [ ] Gestion d'erreurs item par item (ne jamais crasher sur un item individuel)
- [ ] Tests unitaires avec tmp_path

**Commit** : `v2.3.2: Implement Sorter orchestrator with SortResult returns`
