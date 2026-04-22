# Phase 2 — Infrastructure Golden Files

## Objectif

Créer le système de chargement et d'assertion des golden files. À la fin de cette phase, le code est prêt à consommer des golden files — il ne manque que les données (phase 3).

## Sous-phases

### 7x.2.1 — GoldenFileLoader

- [ ] Créer `tests/e2e/golden.py`
- [ ] Implémenter `GoldenFile` dataclass (name, nfo, artwork, structure, dispatch)
- [ ] Implémenter `load_golden_file(slug)` :
  - Chemin : `assets/torrents/expected/{slug}/`
  - Charger chaque JSON : `expected_nfo.json`, `expected_artwork.json`, `expected_structure.json`, `expected_dispatch.json`
  - Chaque fichier est optionnel (dict vide si absent) — permet une adoption progressive
- [ ] Implémenter `match_torrent_to_golden(torrent_name)` :
  - Normaliser le nom torrent (lowercase, supprimer tags `[LaCale]-`, codecs, résolution)
  - Matcher contre les noms de dossiers dans `expected/` (fuzzy, seuil 80%)
  - Ex: `"[LaCale]-Jumanji.1995.MULTi..."` → `"jumanji_1995"`
- [ ] Implémenter `discover_golden_files()` :
  - Lister les sous-dossiers de `assets/torrents/expected/`
  - Charger chacun via `load_golden_file()`
- [ ] Écrire tests dans `tests/e2e/test_golden.py` :
  - `test_load_golden_file_complete` — tous les 4 JSON présents
  - `test_load_golden_file_partial` — seulement expected_nfo.json → les autres sont dict vide
  - `test_load_golden_file_not_found` — FileNotFoundError
  - `test_match_torrent_jumanji` — nom torrent complet → "jumanji_1995"
  - `test_match_torrent_malcolm` — nom torrent complet → "malcolm_in_the_middle_s01"
  - `test_match_torrent_unknown` — nom inconnu → None
  - `test_discover_empty` — dossier expected/ vide → liste vide
  - (Pour les tests, créer des golden files factices dans tmp_path)

**Commit** : `v7x.2.1: Add GoldenFileLoader with load, match, and discover`

### 7x.2.2 — Assertions golden file

- [ ] Ajouter dans `tests/e2e/assertions.py` :

**`assert_scrape_golden(media_dir, golden)`** :

1. Vérifier que le dossier correspond à `golden.nfo["folder_name_pattern"]`
2. Trouver le fichier NFO (`.nfo` dans le dossier racine)
3. Parser le XML (ET.parse)
4. Pour chaque tag dans `golden.nfo["required_nfo_tags"]` : vérifier `root.find(tag)` is not None
5. Pour chaque (key, value) dans `golden.nfo["nfo_invariants"]` : vérifier `root.find(key).text == value`
6. Pour chaque fichier dans `golden.artwork["required"]` : vérifier existence
7. Vérifier taille poster >= `golden.artwork["min_poster_size_bytes"]`
8. Si `golden.nfo["seasons"]` existe (TV show) :
   - Pour chaque saison : vérifier que le dossier `season_dir` existe
   - Vérifier `episode_count` (nombre de `.mkv` dans le dossier saison)
   - Vérifier `sample_episodes` (fichiers spécifiques existent, prefix match)

**`assert_dispatch_golden(result, golden)`** :

1. `assert result.action == golden.dispatch["action"]`
2. `assert result.disk in golden.dispatch["eligible_disks"]`
3. `assert golden.dispatch["destination_contains"] in str(result.destination)`
4. `assert result.action not in ("error", "skipped")`

**`assert_structure_golden(media_dir, golden)`** :

1. Pour chaque pattern dans `golden.structure["required_files"]` : `assert list(media_dir.glob(pattern))`
2. Pour chaque dir dans `golden.structure["required_dirs"]` : `assert (media_dir / dir).is_dir()`
3. Pour chaque pattern dans `golden.structure["forbidden_patterns"]` : `assert not list(media_dir.glob(pattern))`
4. Si `golden.structure["season_files"]` existe :
   - Pour chaque saison : vérifier `min_episode_count`

- [ ] Écrire tests unitaires pour chaque assertion (avec golden files factices + filesystem tmp_path) :
  - `test_assert_scrape_golden_valid` — tous les champs corrects → pass
  - `test_assert_scrape_golden_missing_nfo_tag` → AssertionError
  - `test_assert_scrape_golden_wrong_invariant` → AssertionError
  - `test_assert_scrape_golden_missing_artwork` → AssertionError
  - `test_assert_dispatch_golden_correct` → pass
  - `test_assert_dispatch_golden_wrong_action` → AssertionError
  - `test_assert_dispatch_golden_wrong_disk` → AssertionError
  - `test_assert_structure_golden_forbidden_file` → AssertionError

**Commit** : `v7x.2.2: Add golden file assertion functions with tests`

### 7x.2.3 — Helper pour trouver le media_dir et le DispatchResult

- [ ] Ajouter dans `assertions.py` :

**`find_media_dir(parent_dir, folder_pattern)`** :

- Chercher un dossier dans `parent_dir` dont le nom contient `folder_pattern`
- Retourner le `Path` ou raise AssertionError si pas trouvé

**`find_dispatch_result(results, torrent_name)`** :

- Chercher dans la liste de DispatchResult celui dont `source.name` matche `torrent_name` (partiel)
- Retourner le DispatchResult ou None

- [ ] Tests unitaires pour les deux helpers

**Commit** : `v7x.2.3: Add find_media_dir and find_dispatch_result helpers`
