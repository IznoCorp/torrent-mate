# Phase 4 — Intégration E2E

## Objectif

Brancher les golden files dans les 3 tests E2E pipeline existants. Les anciennes assertions restent en place (backward compat). Les golden files ajoutent une couche de vérification supplémentaire.

## Sous-phases

### 7x.4.1 — Intégrer dans test_pipeline_movies.py

- [ ] Importer `match_torrent_to_golden` et les 3 assertions golden de `assertions.py`
- [ ] Après `assert_scrape_complete()` (existant, conservé) :
  ```python
  golden = match_torrent_to_golden(torrent_name)
  if golden:
      media_dir = find_media_dir(movies_dir, golden.nfo["folder_name_pattern"])
      assert_scrape_golden(media_dir, golden)
      assert_structure_golden(media_dir, golden)
  ```
- [ ] Après `run_dispatch(dry_run=True)` :
  ```python
  if golden:
      matching_result = find_dispatch_result(dispatch_results, torrent_name)
      assert_dispatch_golden(matching_result, golden)
  ```
- [ ] Le test doit toujours passer si aucun golden file n'existe (graceful skip avec log)
- [ ] Tester en local : lancer le test E2E movie complet avec golden files

**Commit** : `v7x.4.1: Integrate golden file assertions into movie pipeline E2E`

### 7x.4.2 — Intégrer dans test_pipeline_tvshows.py

- [ ] Même pattern que movies pour `TestTVShowFullPipeline.test_tvshow_full_pipeline()`
- [ ] Points spécifiques TV :
  - `assert_scrape_golden()` vérifie aussi les saisons et épisodes
  - Golden file inclut `seasons.1.episode_count` et `sample_episodes`
- [ ] Pour `TestFullPipelineMixed.test_full_pipeline_via_run_command()` :
  - Ce test utilise le CLI runner → on ne peut pas facilement capturer les DispatchResult
  - Ajouter seulement les assertions de structure post-pipeline (si les dossiers sont accessibles)
  - Ou bien skip golden assertions pour ce test (le CLI test est un smoke test par nature)
- [ ] Tester en local : lancer le test E2E tvshow complet avec golden files

**Commit** : `v7x.4.2: Integrate golden file assertions into tvshow pipeline E2E`

### 7x.4.3 — Validation finale

- [ ] Lancer tous les tests unitaires : `.venv/bin/python -m pytest tests/ -q` → 0 failures
- [ ] Lancer couverture : `--cov=personalscraper --cov-report=term-missing` → cible ≥ 82%
- [ ] Vérifier que les tests E2E sans golden file fonctionnent toujours (assertions smoke seules)
- [ ] Mettre à jour CLAUDE.md :
  - Section Testing : mentionner les golden files
  - Ajouter le chemin `assets/torrents/expected/` dans la structure
- [ ] Mettre à jour IMPLEMENTATION.md : V7.x statut `[x]`

**Commit** : `v7x.4.3: Finalize V7.x — update docs and mark complete`
