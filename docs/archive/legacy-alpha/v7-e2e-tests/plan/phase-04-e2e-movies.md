# Phase 4 — Tests E2E films

## Objectif

Premier test E2E complet : un film passe le pipeline entier du magnet au disque de destination.

## Sous-phases

### 7.4.1 — Test E2E film unique

- [ ] Créer `tests/e2e/test_pipeline_movies.py`
- [ ] Décorateur `@pytest.mark.e2e` sur tous les tests
- [ ] Test `test_movie_full_pipeline()` :
  1. **Setup** : ajouter le magnet film à qBit, attendre téléchargement
  2. **Marker** : placer `.e2e-test-marker` sur le dossier téléchargé (seul placement)
  3. **V1 Ingest** : exécuter ingest → fichier arrive dans A TRIER/
     - Vérifier que le marker a survécu (copytree/move)
     - `assert_ingest_complete()`
  4. **V2 Sort** : exécuter sort+clean → fichier dans 001-MOVIES/
     - Vérifier que le marker a survécu (move = rename même FS)
     - `assert_sort_complete()`
  5. **V3 Scrape** : exécuter scrape → NFO + artwork
     - `assert_scrape_complete()`
  6. **V4 Verify** : exécuter verify → VerifyResult
     - `assert_verify_complete()`
     - Vérifier la catégorie (doit matcher `expected_category`)
  7. **V5 Dispatch** : exécuter dispatch → fichier sur disque
     - Vérifier que le marker a survécu (rsync copie tout)
     - `assert_dispatch_complete()`
       Note : le marker n'est PAS re-créé — il se propage naturellement
       (voir DESIGN.md "Cycle de vie du marker")
  8. **Cleanup** : supprimer fichiers de test
     - `cleanup.cleanup_all(force=True)`
     - `assert_cleanup_complete()`
- [ ] Le test est dans un `try/finally` pour garantir le cleanup même en cas d'échec

**Commit** : `v7.4.1: Implement full E2E test for a single movie`

### 7.4.2 — Tests edge cases films

- [ ] Test `test_movie_scrape_no_match()` :
  - Magnet d'un film obscur/ancien → V3 ne trouve pas de match
  - V4 verify → status "blocked" (pas de NFO)
  - Le film reste dans A TRIER/, n'est PAS dispatché
  - Cleanup nettoie quand même
- [ ] Test `test_movie_already_exists_on_disk()` :
  - Si un film de même nom existe déjà sur un disque (cas replace)
  - Vérifier que le dispatch remplace correctement
  - Le marker est sur le NOUVEAU dossier, pas l'ancien
- [ ] Cleanup systématique

**Commit** : `v7.4.2: Add movie edge case E2E tests`
