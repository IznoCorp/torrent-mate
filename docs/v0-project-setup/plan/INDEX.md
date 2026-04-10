# V0 — PROJECT SETUP : Plan d'implémentation

> Mise en place du projet Python `personalscraper` + logger + archivage scripts legacy

## Phases

| #   | Phase                                                     | Fichier                                            | Status |
| --- | --------------------------------------------------------- | -------------------------------------------------- | ------ |
| 1   | Scaffolding projet (pyproject.toml, Makefile, .gitignore) | [phase-01-scaffolding.md](phase-01-scaffolding.md) | [ ]    |
| ·   | _Contrôle de cohérence P1→P2_                             |                                                    | [ ]    |
| 2   | Package core (config, CLI, models)                        | [phase-02-core.md](phase-02-core.md)               | [ ]    |
| ·   | _Contrôle de cohérence P2→P3_                             |                                                    | [ ]    |
| 3   | Module logger JSON structuré                              | [phase-03-logger.md](phase-03-logger.md)           | [ ]    |
| ·   | _Contrôle de cohérence P3→P4_                             |                                                    | [ ]    |
| 4   | Archivage scripts legacy + nettoyage                      | [phase-04-archive.md](phase-04-archive.md)         | [ ]    |
| ·   | _Contrôle de cohérence V0→V1_                             |                                                    | [ ]    |

## Dépendances entre phases

```
Phase 1 (scaffold) ──▶ Phase 2 (core) ──▶ Phase 3 (logger) ──▶ Phase 4 (archive)
```

Linéaire — chaque phase dépend de la précédente.

## Contrôles de cohérence

### Après Phase 1 (Scaffolding → Core)

- [ ] `pip install -e ".[dev]"` fonctionne sans erreur
- [ ] `make test` exécute pytest (même si 0 tests)
- [ ] `make lint` et `make format` fonctionnent
- [ ] `.env.example` contient toutes les sections du design

### Après Phase 2 (Core → Logger)

- [ ] `personalscraper --version` affiche la version
- [ ] `personalscraper --help` affiche les sous-commandes
- [ ] `Settings` charge le `.env` correctement
- [ ] Les sous-commandes stubs (ingest, sort, scrape, dispatch, run) existent

### Après Phase 3 (Logger → Archive)

- [ ] `get_logger("test")` crée un fichier dans `logs/`
- [ ] Le format JSON est valide et parseable
- [ ] `--verbose` / `--quiet` changent le niveau de log
- [ ] `cleanup_old_logs()` fonctionne

### Après Phase 4 (Archive → V1)

- [ ] `099-SCRIPTS/` n'est plus dans le repo
- [ ] Les scripts sont archivés dans `~/dev/099-SCRIPTS-archive/`
- [ ] `git status` est propre
- [ ] Toutes les commandes CLI fonctionnent toujours
