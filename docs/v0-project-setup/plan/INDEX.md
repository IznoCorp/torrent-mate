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
- [ ] `personalscraper --help` affiche les sous-commandes (Typer rich output)
- [ ] `Settings` charge le `.env` correctement
- [ ] Les sous-commandes stubs (ingest, sort, scrape, verify, dispatch, run) existent
- [ ] `Console(quiet=True)` supprime l'output en mode `--quiet`
- [ ] `rich.traceback.install()` rend les erreurs lisibles

### Après Phase 3 (Logger → Archive)

- [ ] `configure_logging()` crée un fichier JSON dans `logs/`
- [ ] Le format JSON Lines est valide et parseable (1 ligne = 1 event)
- [ ] Chaque event contient `timestamp`, `level`, `event` au minimum
- [ ] `--verbose` / `--quiet` changent le niveau de log
- [ ] Console output est coloré en mode interactif, JSON en mode non-TTY
- [ ] `cleanup_old_logs()` fonctionne
- [ ] Les logs stdlib (requests, urllib3) passent aussi par structlog

### Après Phase 4 (Archive → V1)

- [ ] `099-SCRIPTS/` n'est plus dans le repo
- [ ] Les scripts sont archivés dans `~/dev/099-SCRIPTS-archive/`
- [ ] `git status` est propre
- [ ] Toutes les commandes CLI fonctionnent toujours
