# V0 — PROJECT SETUP : Plan d'implémentation

> Mise en place du projet Python `personalscraper` + logger + archivage scripts legacy

## Phases

| #   | Phase                                                     | Fichier                                            | Status |
| --- | --------------------------------------------------------- | -------------------------------------------------- | ------ |
| 1   | Scaffolding projet (pyproject.toml, Makefile, .gitignore) | [phase-01-scaffolding.md](phase-01-scaffolding.md) | [x]    |
| ·   | _Contrôle de cohérence P1→P2_                             |                                                    | [x]    |
| 2   | Package core (config, CLI, models)                        | [phase-02-core.md](phase-02-core.md)               | [x]    |
| ·   | _Contrôle de cohérence P2→P3_                             |                                                    | [x]    |
| 3   | Module logger JSON structuré                              | [phase-03-logger.md](phase-03-logger.md)           | [x]    |
| ·   | _Contrôle de cohérence P3→P4_                             |                                                    | [x]    |
| 4   | Archivage scripts legacy + nettoyage                      | [phase-04-archive.md](phase-04-archive.md)         | [x]    |
| ·   | _Contrôle de cohérence V0→V1_                             |                                                    | [x]    |

## Dépendances entre phases

```
Phase 1 (scaffold) ──▶ Phase 2 (core) ──▶ Phase 3 (logger) ──▶ Phase 4 (archive)
```

Linéaire — chaque phase dépend de la précédente.

## Contrôles de cohérence

### Après Phase 1 (Scaffolding → Core)

- [x] `pip install -e ".[dev]"` fonctionne sans erreur
- [x] `make test` exécute pytest (même si 0 tests)
- [x] `make lint` et `make format` fonctionnent
- [x] `.env.example` contient toutes les sections du design

### Après Phase 2 (Core → Logger)

- [x] `personalscraper --version` affiche la version
- [x] `personalscraper --help` affiche les sous-commandes (Typer rich output)
- [x] `Settings` charge le `.env` correctement
- [x] Les sous-commandes stubs (ingest, sort, scrape, verify, dispatch, run) existent
- [x] `Console(quiet=True)` supprime l'output en mode `--quiet`
- [x] `rich.traceback.install()` rend les erreurs lisibles

### Après Phase 3 (Logger → Archive)

- [x] `configure_logging()` crée un fichier JSON dans `logs/`
- [x] Le format JSON Lines est valide et parseable (1 ligne = 1 event)
- [x] Chaque event contient `timestamp`, `level`, `event` au minimum
- [x] `--verbose` / `--quiet` changent le niveau de log
- [x] Console output est coloré en mode interactif, JSON en mode non-TTY
- [x] `cleanup_old_logs()` fonctionne
- [x] Les logs stdlib (requests, urllib3) passent aussi par structlog

### Après Phase 4 (Archive → V1)

- [x] `099-SCRIPTS/` n'est plus dans le repo
- [x] Les scripts sont archivés dans `~/dev/099-SCRIPTS-archive/`
- [x] `git status` est propre
- [x] Toutes les commandes CLI fonctionnent toujours
