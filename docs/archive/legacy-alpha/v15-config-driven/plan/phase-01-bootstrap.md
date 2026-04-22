️# Phase 1 — Bootstrap : golden table + `conf/` foundation

## Objectif

Poser le socle du package `personalscraper/conf/` (IDs, modèles Pydantic, loader JSON5) et capturer le comportement V14 dans une golden table qui servira de contrat pour la Phase 2.

## Pré-requis (P1.0)

- [ ] Créer branche `feat/v15-config-driven` depuis `main`
- [ ] Configurer PR merge strategy via `/implement-version` (recommandé : `manual` — PR reviewable en une fois)

## Sous-phases

### 1.1 — Ajouter dépendance `json5` + scaffolding package

- [ ] Ajouter `json5>=0.9.14` à `pyproject.toml [project]` dependencies
- [ ] Créer `personalscraper/conf/__init__.py` (vide)
- [ ] Créer `personalscraper/conf/ids.py` avec :
  - Les 11 constantes `MOVIES`, `MOVIES_ANIMATION`, `MOVIES_DOCUMENTARY`, `TV_SHOWS`, `TV_SHOWS_ANIMATION`, `TV_SHOWS_DOCUMENTARY`, `ANIME`, `AUDIOBOOKS`, `STANDUP`, `THEATER`, `TV_PROGRAMS`
  - `BUILTIN_CATEGORY_IDS: frozenset[str]`
  - `default_label(category_id: str) -> str`

**Commit** : `v15.1.1: Add json5 dependency and conf/ids.py with 11 builtin category IDs`

### 1.2 — `conf/models.py` : Pydantic models

- [ ] Créer `personalscraper/conf/models.py` avec :
  - `_StrictModel` base (extra="forbid")
  - `CategoryConfig`, `DiskConfig`, `CategoryRule`, `GenreMapping`, `AnimeRule`, `PathConfig`
  - `VideoPrefs`, `AudioPrefs`, `SubtitlePrefs`, `RuleCriteria`, `EncodingRule`, `LibraryPrefs` (miroir V14 library/preferences.py avec validators)
  - `Config` top-level avec validators `_validate_custom_ids`, `_validate_cross_references`
  - Methods : `category()`, `disk_by_id()`, `disks_accepting()`, `resolve_category_alias()`, `all_category_ids` property
- [ ] Unit tests `tests/conf/test_models.py` : valid config, invalid IDs, duplicate disk IDs, cross-refs broken, `extra="forbid"` rejette clés inconnues

**Commit** : `v15.1.2: Add conf/models.py with Pydantic schema and full V14 library prefs`

### 1.3 — `conf/loader.py` : JSON5 loader + warnings

- [ ] Créer `personalscraper/conf/loader.py` avec :
  - `DEFAULT_CONFIG_PATH`, `ENV_CONFIG_PATH`
  - `ConfigNotFoundError`, `ConfigValidationError` exceptions
  - `resolve_config_path(cli_override)` (CLI > env > default)
  - `load_config(path)` : read + json5.load + Pydantic validation + exception wrapping + **émission des warnings non-blocking** via `collect_warnings(config)`
  - `collect_warnings(config: Config) -> list[str]` (implémente acceptance #12) :
    - Pour chaque `custom_categories[id]` sans disque l'acceptant → `"dead custom_category '{id}': no disk accepts it"`
    - Pour chaque ID utilisé (via disks/rules/mapping) mais absent de `config.categories` → `"using default label for '{id}'"`
    - Pour chaque `disk.path` qui n'existe pas sur le filesystem → `"disk '{id}' path '{path}' not mounted/present"`
  - Les warnings sont émis via `logger.warning()` (ne bloquent pas le load)
- [ ] Unit tests `tests/conf/test_loader.py` : resolution order, missing file, invalid JSON5, validation error (Pydantic), expanduser/resolve
- [ ] Unit tests `tests/conf/test_warnings.py` : chaque type de warning émis dans le bon cas

**Commit** : `v15.1.3: Add conf/loader.py with JSON5 parsing, resolution, and validation warnings`

### 1.4 — `config.example.json5` template

- [ ] Créer `config.example.json5` à la racine du repo avec :
  - `config_version: 1`
  - Tous les champs documentés par des commentaires `//` (qui serviront de prompts pour init-config)
  - Valeurs placeholders (`/path/to/drive_a`, etc.)
  - Exemples commentés dans `category_rules` et `custom_categories`
  - `genre_mapping` pré-rempli avec IDs TMDB/TVDB + noms en commentaire
- [ ] Validation : `python -c "import json5; json5.load(open('config.example.json5'))"`
- [ ] Test `tests/conf/test_example_config.py` : `load_config('config.example.json5')` passe la validation Pydantic

**Commit** : `v15.1.4: Add config.example.json5 template with fully commented schema`

### 1.4b — `tests/fixtures/config.py` : fixture `test_config` partagée

- [ ] Créer `tests/fixtures/__init__.py` (vide)
- [ ] Créer `tests/fixtures/config.py` avec fixture `test_config` (cf DESIGN §1138-1162) : 3 disques neutres `drive_a/b/c`, labels `cat_{id}`, tmp_path-based
- [ ] Dans `tests/conftest.py`, importer ou exposer via `pytest_plugins = ["tests.fixtures.config"]` (au choix)
- [ ] **NB** : cette fixture est nécessaire dès la Phase 6 pour les tests refactorés — sa création tôt évite les dépendances inter-phases implicites
- [ ] Tests smoke : `test_fixture_loads` → assert `test_config.disks[0].id == "drive_a"`, valide Pydantic

**Commit** : `v15.1.4b: Add tests/fixtures/config.py with test_config shared fixture`

### 1.5 — `conf/migration.py` scaffold minimal (V14_LABEL_TO_ID uniquement)

- [ ] Créer `personalscraper/conf/migration.py` avec SEULEMENT le dict `V14_LABEL_TO_ID` (11 mappings, dont "spectacles" → "standup")
- [ ] Le reste du module (fonctions migration) sera rempli en Phase 4 — ici juste la constante pour débloquer P2.6 (golden equivalence)
- [ ] **NB** : ce scaffold brise le back-edge P2 → P4 identifié par la review (P2.6 a besoin de V14_LABEL_TO_ID)

**Commit** : `v15.1.5: Add conf/migration.py scaffold with V14_LABEL_TO_ID constant`

### 1.6 — Golden table : capturer le comportement V14

- [ ] Créer `scripts/generate_classifier_golden.py` qui :
  - Importe `personalscraper.genre_mapper.GenreMapper`
  - Définit une matrice d'inputs couvrant les 11 catégories × min 4 scénarios
  - Pour chaque input : invoque `categorize_movie` ou `categorize_tvshow`, enregistre `(inputs, expected_v14_label)`
  - Dump vers `tests/equivalence/golden/classifier_cases.json`
- [ ] Lancer le script → générer 50+ cas
- [ ] Vérifier manuellement que les cas couvrent toutes les branches de `genre_mapper.py` (grep `return "..."` → assertion matching dans la golden)

**Commit** : `v15.1.6: Add script to generate classifier equivalence golden from V14`

### 1.7 — Test d'équivalence (rouge pour le moment)

- [ ] Créer `tests/equivalence/__init__.py` et `tests/equivalence/test_classifier_v14_vs_v15.py` avec :
  - Charge `classifier_cases.json`
  - Pour chaque case : invoke `classifier.classify()` V15 (n'existe pas encore → ImportError ou skip)
  - Assert `result_id == V14_LABEL_TO_ID[case.expected_v14_label]`
- [ ] Marque le test `@pytest.mark.skip(reason="Phase 2 will implement classifier")` pour l'instant

**Commit** : `v15.1.7: Add skipped equivalence test scaffold for Phase 2 gate`

## Tests de cohérence P1→P2

- [ ] `python -m pytest tests/conf/` → tous passent
- [ ] `python -c "from personalscraper.conf import ids; from personalscraper.conf.models import Config; from personalscraper.conf.loader import load_config"` → 0 erreur
- [ ] `python -m json5 < config.example.json5` → parse OK
- [ ] `ls tests/equivalence/golden/classifier_cases.json` → existe, ≥ 50 cas
- [ ] mypy strict : 0 erreur sur `personalscraper/conf/*`
