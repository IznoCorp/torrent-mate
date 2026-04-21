# Phase 9 — Verify/Enforce/Sorter + Tests refactor

## Objectif

Dé-hardcoder les derniers modules (`verify/`, `enforce/`, `sorter/`) et refactorer l'intégralité de la suite de tests (434 occurrences de noms codés en dur) vers la fixture `test_config`.

## Sous-phases

### 9.1 — `verify/` : IDs partout

- [ ] `verify/checker.py`, `verify/verifier.py`, `verify/fixer.py`, `verify/genre_mapper.py` (si existe encore) :
  - Remplacer `"films"`, `"series"`, etc. par IDs `CID.*`
  - `verify/checker.py` consomme `config.library` au lieu de charger `library_preferences.json` directement
  - Affichage Rich utilise `config.category(id).folder_name` pour labels humains
- [ ] Tests `tests/verify/*` : adapter pour utiliser fixture `test_config` + IDs

**Commit** : `v15.9.1: verify/ uses category IDs and config.library`

### 9.2 — `enforce/` : IDs partout

- [ ] `enforce/run.py`, `enforce/coherence_checker.py`, `enforce/structure_validator.py`, `enforce/sanitizer.py` :
  - Remplacer labels par IDs
  - Rules de validation : utiliser IDs
- [ ] Tests `tests/enforce/*` : adapter

**Commit** : `v15.9.2: enforce/ uses category IDs`

### 9.3 — `sorter/` : IDs partout

- [ ] `sorter/matcher.py`, `sorter/sorter.py`, `sorter/cleaner.py`, `sorter/file_type.py` :
  - Remplacer labels par IDs
  - Pattern matching : regex sur filename (pas sur category name en dur)
- [ ] Tests `tests/sorter/*` : adapter

**Commit** : `v15.9.3: sorter/ uses category IDs`

### 9.4 — `pipeline.py` : signature + flow

- [ ] `personalscraper/pipeline.py::Pipeline` :
  - Constructor accepte `config: Config, settings: Settings` (au lieu de juste `settings`)
  - Propagate `config` vers tous les services instanciés (IngestRunner, Sorter, Scraper, Verifier, Dispatcher, etc.)
  - Utilise `config.paths.data_dir` pour lockfile, tracker, etc. (plus de `settings.data_dir`)
- [ ] Tests `tests/test_pipeline.py` : adapter signature

**Commit** : `v15.9.4: pipeline.py accepts Config and threads it through all services`

### 9.5 — `notifier.py` : Telegram templates utilisent IDs + labels

- [ ] `personalscraper/notifier.py` :
  - Templates de messages : utiliser IDs dans les tags structurés ; utiliser labels humains (via `config.category(id).folder_name`) dans le texte user-visible
- [ ] Tests notifier : avec fixture config

**Commit** : `v15.9.5: notifier uses IDs in structured tags and labels in human text`

### 9.6 — `tests/conftest.py` : vérifier `test_config` est exposée partout

- [ ] `tests/fixtures/__init__.py` et `tests/fixtures/config.py` ont été créés en **P1.4b** (fixture shared dispo depuis le début)
- [ ] Vérifier que `tests/conftest.py` l'expose bien (via import ou `pytest_plugins`) — ajouter si nécessaire
- [ ] **NB** : la fixture `mock_settings` existante reste en place ici — elle sera retirée en P9.13 (après refactor de tous les tests consommateurs)

**Commit** : `v15.9.6: Ensure test_config fixture is auto-exposed in conftest`

### 9.7 — `tests/dispatch/*` : refactor hardcoding

- [ ] Grep `/Volumes/|"Disk[1-4]"|"films"|"series"` dans `tests/dispatch/*`
- [ ] Remplacer par utilisations de `test_config` fixture + IDs via `CID.*`
- [ ] Ajuster les mocks `get_disk_status` pour utiliser `DiskConfig` provenant de fixture
- [ ] Tests dispatch passent

**Commit** : `v15.9.7: Remove hardcoded paths/names from tests/dispatch/*`

### 9.8 — `tests/library/*` : refactor hardcoding

- [ ] Même traitement pour `tests/library/*` (10+ fichiers)
- [ ] Tests library passent

**Commit** : `v15.9.8: Remove hardcoded paths/names from tests/library/*`

### 9.9 — `tests/scraper/*` : refactor hardcoding

- [ ] Même traitement pour `tests/scraper/*`
- [ ] Fixtures de genres TMDB/TVDB : utiliser des IDs et labels neutres
- [ ] Tests scraper passent

**Commit** : `v15.9.9: Remove hardcoded paths/names from tests/scraper/*`

### 9.10 — `tests/verify/*`, `tests/enforce/*`, `tests/sorter/*`, `tests/test_cli.py`

- [ ] Refactor mécanique de tous les tests restants
- [ ] Remplacer labels par IDs
- [ ] Remplacer paths `/Volumes/...` par `tmp_path`-based
- [ ] `tests/test_cli.py` : mettre à jour les CliRunner invocations

**Commit** : `v15.9.10: Remove hardcoded paths/names from remaining test files`

### 9.11 — `tests/resilience/*`, `tests/integration/*`, `tests/e2e/*`

- [ ] Tests E2E utilisent `test_config` fixture (pas de vraie config utilisateur)
- [ ] Tests roundtrip : utiliser configs synthétiques

**Commit** : `v15.9.11: Remove hardcoded paths/names from resilience/integration/e2e tests`

### 9.12 — Audit final : grep zero-result sur tout le codebase

- [ ] Commande exacte à copy-paste :

  ```bash
  grep -rnE '"films"|"series"|"films animations"|"series animations"|"series documentaires"|"series animes"|"emissions"|"livres audios"|"spectacles"|"theatres"|"Disk[1-4]"|/Volumes/' personalscraper/ tests/ --include="*.py" \
    | grep -vE 'conf/migration\.py|tests/migration/fixtures/'
  ```

- [ ] Seules exceptions acceptées :
  - `personalscraper/conf/migration.py::V14_LABEL_TO_ID` + genre maps inlinés (par design, one-shot migration)
  - `tests/migration/fixtures/*` (fixtures V14 pour tester la migration)
- [ ] Résultat attendu : 0 ligne après le second grep -v
- [ ] Si autre résultat → corriger

**Commit** : `v15.9.12: Audit final — zero hardcoded user-specific values outside migration code`

### 9.13 — Retirer `mock_settings` fixture obsolète

- [ ] **Pré-requis** : tous les tests refactorés (P9.7-P9.11) et utilisent `test_config` au lieu de `mock_settings`
- [ ] Vérifier avec : `grep -rn "mock_settings" tests/ --include="*.py"` → seules références = la définition dans `tests/conftest.py`
- [ ] Supprimer la fixture `mock_settings` de `tests/conftest.py` (plus besoin après P6 qui a allégé `Settings`)
- [ ] Relancer la suite complète pour confirmer zéro régression

**Commit** : `v15.9.13: Remove obsolete mock_settings fixture after tests migration`

## Tests de cohérence P9→P10

- [ ] `python -m pytest tests/ -q` → 1270+ tests passent (aucune régression)
- [ ] `grep -rE '"films"|"series"|"Disk[1-4]"|/Volumes/' personalscraper/ tests/ --include="*.py"` → seulement migration-related
- [ ] Golden-table equivalence test passe toujours
- [ ] Test E2E migration (P4.8) passe
- [ ] mypy strict sur tout `personalscraper/` : 0 erreur
- [ ] ruff check + ruff format : clean
