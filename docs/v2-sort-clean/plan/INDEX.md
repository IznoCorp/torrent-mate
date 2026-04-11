# V2 — SORT + CLEAN : Plan d'implémentation

> Tri automatique des fichiers par type + nettoyage guessit des noms

## Phases

| #   | Phase                                          | Fichier                                                | Status |
| --- | ---------------------------------------------- | ------------------------------------------------------ | ------ |
| 1   | Intégration FileMate core (file_type, matcher) | [phase-01-filemate-core.md](phase-01-filemate-core.md) | [x]    |
| ·   | _Contrôle de cohérence P1→P2_                  |                                                        | [x]    |
| 2   | Nouveau cleaner guessit                        | [phase-02-cleaner.md](phase-02-cleaner.md)             | [x]    |
| ·   | _Contrôle de cohérence P2→P3_                  |                                                        | [x]    |
| 3   | Strategies + Sorter orchestrator               | [phase-03-sorter.md](phase-03-sorter.md)               | [x]    |
| ·   | _Contrôle de cohérence P3→P4_                  |                                                        | [x]    |
| 4   | CLI command + tests end-to-end                 | [phase-04-cli-tests.md](phase-04-cli-tests.md)         | [x]    |
| ·   | _Contrôle de cohérence V2→V3_                  |                                                        | [x]    |

## Dépendances entre phases

```
Phase 1 (file_type + matcher) ──▶ Phase 2 (cleaner) ──▶ Phase 3 (strategies + sorter) ──▶ Phase 4 (CLI + tests)
```

## Contrôles de cohérence

### Après Phase 1 (FileMate core → Cleaner)

- [x] `detect_file_type()` et `detect_dir_type()` fonctionnent sur des fichiers réels
- [x] `find_matching_directory()` retourne le bon match sur les dossiers existants
- [x] Les tests unitaires passent (86 tests)
- [x] Modules importables : `from personalscraper.sorter import FileType, find_matching_directory`

### Après Phase 2 (Cleaner → Strategies)

- [x] `NameCleaner.clean()` transforme correctement les noms de torrent
- [x] `extract_year()` et `extract_season_episode()` détectent tous les formats
- [x] Tests avec les noms réels de `torrents/complete/` passent (36 tests)
- [x] Pas de régression sur les patterns existants de FileMate (guessit + 140 services)

### Après Phase 3 (Strategies + Sorter → CLI)

- [x] `Sorter.process()` retourne bien une `list[SortResult]` (153 tests total)
- [x] Films triés dans `001-MOVIES/`, séries dans `002-TVSHOWS/`
- [x] Fuzzy matching empêche les doublons
- [x] `--dry-run` ne déplace rien

### Après Phase 4 (CLI → V3)

- [x] `personalscraper sort --dry-run` fonctionne end-to-end (164 tests total)
- [x] Les fichiers dans `001-MOVIES/` et `002-TVSHOWS/` ont des noms propres
- [x] Les `SortResult` contiennent title, year, season, episode corrects
- [x] V3 peut lire les dossiers triés et identifier les médias à scraper
- [x] **Handoff V2→V3** : V2 crée `Show Name/` (sans année). Merge via fuzzy matching ✓
- [x] **Handoff V2→V3** : V3 pourra renommer `Show Name/` → `Show Name (Year)/` sans conflit ✓
