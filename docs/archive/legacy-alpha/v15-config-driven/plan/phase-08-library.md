# Phase 8 — Library refactor : prefs fusion + IDs

## Objectif

Supprimer `library/preferences.py` (fusionné dans `conf/models.py::LibraryPrefs`), refactorer tous les modules `library/*` pour utiliser les IDs V15 et `config.library`, migrer les JSON V14 existants à la lecture.

## Sous-phases

### 8.1 — Supprimer `library/preferences.py`

- [ ] **Vérifier** : `conf/models.py::LibraryPrefs` + sous-modèles (VideoPrefs, AudioPrefs, SubtitlePrefs, RuleCriteria, EncodingRule) sont complets et miroir V14 (P1.2)
- [ ] Supprimer `personalscraper/library/preferences.py`
- [ ] Grep imports : remplacer `from personalscraper.library.preferences import X` par `from personalscraper.conf.models import X` (renames : `LibraryPreferences` → `LibraryPrefs`, `VideoPreferences` → `VideoPrefs`, etc.)

**Commit** : `v15.8.1: Delete library/preferences.py (merged into conf/models.py::LibraryPrefs)`

### 8.2 — `library/scanner.py` + `library/models.py` : IDs dans library_index.json

- [ ] `library/scanner.py` : quand on scanne un dossier, déterminer le `category_id` via resolver (le dossier physique `disks[].path/{folder_name}` correspond à quel ID ?) :
  - Pour chaque disque de config, pour chaque category dans disk.categories : check si le path contient le dossier folder_name
  - Associer l'item au category_id correspondant
- [ ] `library/models.py::LibraryItem.category` = category_id (string, un des IDs valides)
- [ ] `library_index.json` schema V15 : items[].category = category_id
- [ ] `LibraryItem.from_v14_json(obj)` : helper de migration (rewrite label → ID via V14_LABEL_TO_ID à la lecture) — utilisé uniquement si format V14 détecté
- [ ] Tests : scan avec fixture config, index généré a les bons IDs

**Commit** : `v15.8.2: library/scanner and models use category IDs`

### 8.3 — `library/validator.py` + `library/analyzer.py` + `library/recommender.py`

- [ ] Grep `"films"`, `"series"`, etc. dans ces 3 modules → remplacer par IDs via `personalscraper.conf.ids`
- [ ] Les comparaisons de type deviennent `item.category == CID.MOVIES`, `item.category in (CID.TV_SHOWS, CID.TV_SHOWS_ANIMATION, ...)`, etc.
- [ ] `EncodingRule.criteria.genre` : reste un label TMDB (pas un category_id) — ok
- [ ] `LibraryPrefs.max_size_movie_gb` vs `max_size_episode_gb` : comparé contre `item.category` — utiliser set d'IDs film-type vs TV-type
  - `MOVIE_CATEGORY_IDS = {CID.MOVIES, CID.MOVIES_ANIMATION, CID.MOVIES_DOCUMENTARY}`
  - `TV_CATEGORY_IDS = {CID.TV_SHOWS, CID.TV_SHOWS_ANIMATION, CID.TV_SHOWS_DOCUMENTARY, CID.ANIME, CID.TV_PROGRAMS}`
  - Ajouter `MOVIE_CATEGORY_IDS`, `TV_CATEGORY_IDS` dans `conf/ids.py`
- [ ] Tests adaptés pour utiliser fixture + IDs

**Commit** : `v15.8.3: library/{validator,analyzer,recommender} use category IDs with MOVIE/TV sets`

### 8.4 — `library/reporter.py` + `library/rescraper.py` : affichage via labels

- [ ] `library/reporter.py` : pour affichage utilisateur (tables Rich), utiliser `config.category(item.category).folder_name` pour obtenir le label humain
- [ ] `library/rescraper.py` : même principe
- [ ] Logs structurés → IDs, affichage Rich → labels (cf D8)
- [ ] Tests : assertions sur IDs (structure) et sur labels (via config fixture)

**Commit** : `v15.8.4: library/{reporter,rescraper} use IDs in logs and labels in Rich display`

### 8.5 — `library/disk_cleaner.py` : iterate config.disks

- [ ] `library/disk_cleaner.py` : iterate `config.disks` au lieu de hardcoded list
- [ ] `--disk <id>` CLI flag accepte disk.id (validation via `config.disk_by_id(id)`)
- [ ] Tests : disk_cleaner avec config fixture (3 disques neutres)

**Commit** : `v15.8.5: library/disk_cleaner iterates config.disks`

### 8.6 — `library_preferences.json` : suppression + utilisation de `config.library`

- [ ] Pour chaque ancien usage de `LibraryPreferences.from_file(...)` ou `load_preferences()` : remplacer par `config.library`
- [ ] Migration : la suppression physique du fichier `library_preferences.json` est faite par `migrate_data_dir` + merge en step 7 de la migration (déjà en P4.4)
- [ ] Tests : plus aucun test ne charge `library_preferences.json` directement

**Commit** : `v15.8.6: Remove library_preferences.json usage — everything via config.library`

## Tests de cohérence P8→P9

- [ ] `tests/library/*` : tous passent avec fixture `test_config`
- [ ] `grep "films\|series" personalscraper/library/` → 0 (hors comments de migration)
- [ ] `grep "LibraryPreferences" personalscraper/` → 0 (ou seulement dans fichiers legacy explicites)
- [ ] `library/preferences.py` supprimé
- [ ] Tests équivalence comportementale V14 library : scan de même structure → index produit contient les même category_ids via `V14_LABEL_TO_ID`
- [ ] mypy strict : 0 erreur sur `library/*`
