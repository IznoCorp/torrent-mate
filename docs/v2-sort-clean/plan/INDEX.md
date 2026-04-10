# V2 — SORT + CLEAN : Plan d'implémentation

> Tri automatique des fichiers par type + nettoyage guessit des noms

## Phases

| #   | Phase                                          | Fichier                                                | Status |
| --- | ---------------------------------------------- | ------------------------------------------------------ | ------ |
| 1   | Intégration FileMate core (file_type, matcher) | [phase-01-filemate-core.md](phase-01-filemate-core.md) | [ ]    |
| ·   | _Contrôle de cohérence P1→P2_                  |                                                        | [ ]    |
| 2   | Nouveau cleaner guessit                        | [phase-02-cleaner.md](phase-02-cleaner.md)             | [ ]    |
| ·   | _Contrôle de cohérence P2→P3_                  |                                                        | [ ]    |
| 3   | Strategies + Sorter orchestrator               | [phase-03-sorter.md](phase-03-sorter.md)               | [ ]    |
| ·   | _Contrôle de cohérence P3→P4_                  |                                                        | [ ]    |
| 4   | CLI command + tests end-to-end                 | [phase-04-cli-tests.md](phase-04-cli-tests.md)         | [ ]    |
| ·   | _Contrôle de cohérence V2→V3_                  |                                                        | [ ]    |

## Dépendances entre phases

```
Phase 1 (file_type + matcher) ──▶ Phase 2 (cleaner) ──▶ Phase 3 (strategies + sorter) ──▶ Phase 4 (CLI + tests)
```

## Contrôles de cohérence

### Après Phase 1 (FileMate core → Cleaner)

- [ ] `detect_file_type()` et `detect_dir_type()` fonctionnent sur des fichiers réels
- [ ] `find_matching_directory()` retourne le bon match sur les dossiers existants
- [ ] Les tests unitaires passent
- [ ] Modules importables : `from personalscraper.sorter import FileType, find_matching_directory`

### Après Phase 2 (Cleaner → Strategies)

- [ ] `NameCleaner.clean()` transforme correctement les noms de torrent
- [ ] `extract_year()` et `extract_season_episode()` détectent tous les formats
- [ ] Tests avec les noms réels de `torrents/complete/` passent
- [ ] Pas de régression sur les patterns existants de FileMate

### Après Phase 3 (Strategies + Sorter → CLI)

- [ ] `Sorter.process()` retourne bien une `list[SortResult]`
- [ ] Films triés dans `001-MOVIES/`, séries dans `002-TVSHOWS/`
- [ ] Fuzzy matching empêche les doublons
- [ ] `--dry-run` ne déplace rien

### Après Phase 4 (CLI → V3)

- [ ] `personalscraper sort --dry-run` fonctionne end-to-end
- [ ] Les fichiers dans `001-MOVIES/` et `002-TVSHOWS/` ont des noms propres
- [ ] Les `SortResult` contiennent title, year, season, episode corrects
- [ ] V3 peut lire les dossiers triés et identifier les médias à scraper
- [ ] **Handoff V2→V3** : V2 crée `Show Name/` (sans année). Un nouvel épisode est ajouté
      au dossier existant via fuzzy matching (pas de création de doublon).
      V3 renommera en `Show Name (Year)/` après matching.
- [ ] **Handoff V2→V3** : V3 pourra renommer `Show Name/` → `Show Name (Year)/` sans conflit
