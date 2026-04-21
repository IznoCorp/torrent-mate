# V15 — CONFIG-DRIVEN ARCHITECTURE : Plan d'implémentation

> Refactoring intégral : sortir toutes les valeurs hardcodées (paths, disques, catégories) du code et les déplacer dans `config.json5`. Code manipule uniquement des IDs abstraits.

## Phases

| #   | Phase                                                                       | Fichier                                                              | Status |
| --- | --------------------------------------------------------------------------- | -------------------------------------------------------------------- | ------ |
| 1   | Bootstrap — golden table + conf foundation                                  | [phase-01-bootstrap.md](phase-01-bootstrap.md)                       | [ ]    |
| ·   | _Cohérence P1→P2 : equivalence golden dumped depuis V14_                    |                                                                      | [ ]    |
| 2   | Classifier pipeline + équivalence                                           | [phase-02-classifier.md](phase-02-classifier.md)                     | [ ]    |
| ·   | _Cohérence P2→P3 : 6 niveaux testés, golden passe_                          |                                                                      | [ ]    |
| 3   | Resolver + example parser                                                   | [phase-03-resolver-parser.md](phase-03-resolver-parser.md)           | [ ]    |
| ·   | _Cohérence P3→P4 : pick_disk_for + prompts opérationnels_                   |                                                                      | [ ]    |
| 4   | Migration module + `init-config` command                                    | [phase-04-migration-initconfig.md](phase-04-migration-initconfig.md) | [ ]    |
| ·   | _Cohérence P4→P5 : migration reversible, tests E2E passent_                 |                                                                      | [ ]    |
| 5   | CLI integration — top-level `--config` + eager load                         | [phase-05-cli.md](phase-05-cli.md)                                   | [ ]    |
| ·   | _Cohérence P5→P6 : toute commande charge Config via callback_               |                                                                      | [ ]    |
| 6   | Settings allégé + Dispatch refactor                                         | [phase-06-settings-dispatch.md](phase-06-settings-dispatch.md)       | [ ]    |
| ·   | _Cohérence P6→P7 : dispatcher utilise Config.disks, tests dispatch passent_ |                                                                      | [ ]    |
| 7   | Scraper refactor — classifier integration + TMDB keywords + NFO             | [phase-07-scraper.md](phase-07-scraper.md)                           | [ ]    |
| ·   | _Cohérence P7→P8 : `genre_mapper.py` supprimé, scraper tests passent_       |                                                                      | [ ]    |
| 8   | Library refactor — prefs fusion + IDs                                       | [phase-08-library.md](phase-08-library.md)                           | [ ]    |
| ·   | _Cohérence P8→P9 : library_\*.json utilise IDs, preferences.py supprimé\_   |                                                                      | [ ]    |
| 9   | Verify/Enforce/Sorter + Tests refactor                                      | [phase-09-verify-enforce-tests.md](phase-09-verify-enforce-tests.md) | [ ]    |
| ·   | _Cohérence P9→P10 : 0 label FR dans les tests, fixture partout_             |                                                                      | [ ]    |
| 10  | Documentation + finalization + PR                                           | [phase-10-docs-pr.md](phase-10-docs-pr.md)                           | [ ]    |

## Dépendances entre phases

```
P1 (bootstrap)
 └──► P2 (classifier) ──► P3 (resolver/parser) ──┐
                                                  ├──► P4 (migration + init-config) ──► P5 (CLI)
                                                  │                                        │
                                                  └────────────────────────────────────────┘
                                                                                           ▼
              ┌───────────────────────────────────────────────────────────────► P6 (settings + dispatch)
              │                                                                            │
              ▼                                                                            ▼
        P7 (scraper) ◄─────────────────────────────────────────────── P8 (library)
              │                                                                            │
              └───────────────────────────────┬──────────────────────────────────────────┘
                                              ▼
                                      P9 (verify/enforce + tests)
                                              │
                                              ▼
                                      P10 (docs + PR)
```

## Contrôles de cohérence

### Après Phase 1 (bootstrap → classifier)

- [ ] `conf/ids.py` définit les 11 IDs builtin (y compris STANDUP, pas CONCERTS)
- [ ] `conf/models.py` contient Config, DiskConfig, CategoryConfig, CategoryRule, GenreMapping, AnimeRule, PathConfig, LibraryPrefs (+ sous-modèles V14)
- [ ] `conf/loader.py` expose `load_config`, `resolve_config_path`, `ConfigNotFoundError`, `ConfigValidationError`
- [ ] `config.example.json5` créé et lisible par `json5.load`
- [ ] `json5>=0.9.14` ajouté à `pyproject.toml [project.dependencies]`
- [ ] Golden table `tests/equivalence/golden/classifier_cases.json` générée depuis V14 (50+ cas)
- [ ] Test `tests/equivalence/test_classifier_v14_vs_v15.py` écrit (rouge pour le moment — V15 n'existe pas encore)

### Après Phase 2 (classifier → resolver/parser)

- [ ] `conf/classifier.py` expose `classify()` avec priority chain 6 niveaux
- [ ] NFO element lit `source="personalscraper"` en priorité (fallback legacy sans attribut)
- [ ] Unit tests : 1 test par niveau + tests de transition (NFO invalide → rules → ...)
- [ ] Golden-table equivalence test **passe** (V15 produit les IDs équivalents à V14)
- [ ] `logger` correctement déclaré et utilisé pour warnings (NFO invalide, labels obsolètes)

### Après Phase 3 (resolver/parser → migration)

- [ ] `conf/resolver.py` : `folder_for()`, `pick_disk_for()` avec threshold V14 (`max(min_free, item*1.5)`)
- [ ] `conf/example_parser.py` : extraction commentaires `//` en prompts, gère commentaires multiligne `/* */`, nested objects, arrays
- [ ] Tests example_parser sur fixture snippets avec toutes formes syntactiques

### Après Phase 4 (migration + init-config)

- [ ] `conf/migration.py` expose `generate_config_from_env`, `migrate_library_json`, `migrate_category_files`, `migrate_data_dir`
- [ ] `V14_LABEL_TO_ID` contient 11 mappings (dont "spectacles" → "standup")
- [ ] `commands/init_config.py` : flow interactif, `--force`, `--from-current`, `--yes`
- [ ] `--force` + existing config = backup `.v15.bak` puis overwrite
- [ ] `--from-current --yes` sans `.env` = error explicit (exit 2)
- [ ] Test E2E : `--from-current` sur `.env` V14 fixture → assert config valide + equivalente
- [ ] Migration `.personalscraper/` → `.data/` atomique (abort si cross-mount)

### Après Phase 5 (CLI)

- [ ] `@app.callback()` charge Config eagerly (sauf si subcommand = `init-config`)
- [ ] Erreur de config = `typer.Exit(2)` immédiat avec message clair
- [ ] `AppCtx` contient `config: Config | None` (plain attribute)
- [ ] `--config` top-level option documentée avec position BEFORE subcommand
- [ ] Toutes les subcommands accèdent `ctx.obj.config`

### Après Phase 6 (settings + dispatch)

- [ ] `config.py` ne contient plus `disk1_dir..disk4_dir` ni `data_dir` (allégé, secrets + seuils numériques)
- [ ] `dispatch/disk_scanner.py` : `DISK_CATEGORIES` supprimé, `get_disk_configs()` lit depuis `Config.disks`
- [ ] `dispatch/dispatcher.py` utilise `resolver.folder_for()`, `resolver.pick_disk_for()`, IDs partout
- [ ] `dispatch/media_index.py` : index par (category_id, disk_id), script migration JSON existant

### Après Phase 7 (scraper)

- [ ] `scraper/scraper.py` appelle `classifier.classify()` avant `nfo_generator.write()`
- [ ] `scraper/nfo_generator.py` écrit `<category source="personalscraper">{ID}</category>`
- [ ] TMDB keywords fetcher : endpoint + cache 30j dans `data_dir/tmdb_keywords_cache.json`
- [ ] Fail-soft : API 404/down → empty keywords, rules ne match pas (niveau suivant)
- [ ] `genre_mapper.py` supprimé
- [ ] Tests scraper passent (mocks TMDB/TVDB)

### Après Phase 8 (library)

- [ ] `library/preferences.py` supprimé (contenu → `conf/models.py::LibraryPrefs`)
- [ ] `library/*.py` utilisent IDs partout (scanner, validator, analyzer, recommender, reporter, disk_cleaner, rescraper)
- [ ] `library_*.json` (tous les 5) utilisent IDs à la lecture et à l'écriture
- [ ] Migration in-place des JSON V14 existants → rewrite labels → IDs + backup `.v14.bak`

### Après Phase 9 (verify/enforce + tests)

- [ ] `verify/*.py`, `enforce/*.py`, `sorter/*.py` : IDs partout, résolution labels via `config.category(id).folder_name` pour affichage Rich
- [ ] 0 occurrence `/Volumes/`, `"Disk1"`, `"films"`, `"series"`, `"series animations"`, `"emissions"`, `"livres audios"`, `"spectacles"`, `"theatres"` dans `tests/` (hors migration fixtures)
- [ ] Fixture `test_config` utilisée partout (ou importée pour dérivation)
- [ ] Tous les 1270+ tests passent

### Après Phase 10 (docs + PR)

- [ ] `CLAUDE.md` mis à jour (V15 current, V14 archive)
- [ ] `INSTALLATION.md`, `CONFIGURATION.md`, `MANUAL.md` mis à jour
- [ ] `README.md` mentionne config.json5 + init-config
- [ ] `MIGRATION.md` créé avec procédure V14 → V15
- [ ] `docs/reference/*.md` mis à jour (architecture, commands, naming, storage, scraping)
- [ ] `config.example.json5` finalisé, testé, commit
- [ ] `.gitignore` ajoute `config.json5`, `config.json5.v15.bak`, `tmdb_keywords_cache.json`
- [ ] CI green sur Python 3.10, 3.11, 3.12, 3.13
- [ ] Tous les critères d'acceptation DESIGN #1-#12 validés
- [ ] PR créée avec récap scope, migration notes, breaking changes

## Commit convention

Sub-phase commit: `v15.{phase}.{sub}: {description}`

Exemples : `v15.1.1: Add conf/ids.py with 11 builtin category IDs`, `v15.7.3: Delete genre_mapper.py after equivalence suite passes`, `v15.9.12: Remove hardcoded disk names from tests/dispatch/*`.
