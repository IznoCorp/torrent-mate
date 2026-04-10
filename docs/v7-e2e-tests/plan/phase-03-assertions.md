# Phase 3 — Assertions pipeline

## Objectif

Implémenter les fonctions d'assertion pour vérifier chaque étape du pipeline E2E.

## Sous-phases

### 7.3.1 — Assertions ingest + sort

- [ ] Créer `tests/e2e/assertions.py`
- [ ] `assert_ingest_complete(staging_dir, expected)` :
  - Chaque torrent attendu a ses fichiers dans A TRIER/
  - Si torrent non-seeding : fichiers déplacés (absents de torrents/complete/)
  - Si torrent seeding : fichiers copiés (présents dans LES DEUX emplacements)
  - Le tracker de V1 a enregistré l'ingestion
- [ ] `assert_sort_complete(movies_dir, tvshows_dir, expected)` :
  - Chaque film attendu est dans 001-MOVIES/
  - Chaque série attendue est dans 002-TVSHOWS/
  - Les noms de fichiers sont nettoyés (pas de tags torrent)
- [ ] Tests unitaires avec structures simulées

**Commit** : `v7.3.1: Implement ingest and sort assertions`

### 7.3.2 — Assertions scrape + verify

- [ ] `assert_scrape_complete(movies_dir, tvshows_dir, expected)` :
  - Chaque film a un .nfo valide (XML parseable + tags title/year/uniqueid)
  - Chaque film a au minimum le poster (warning si landscape manquant)
  - Chaque série a tvshow.nfo + poster
  - Les épisodes sont renommés au format `S01E01 - Titre.ext`
  - Les épisodes ont un .nfo chacun
- [ ] `assert_verify_complete(results)` :
  - Tous les VerifyResult de test ont status "valid" ou "fixed"
  - Chaque dossier a une catégorie identifiée (pas None)
  - Les catégories matchent les `expected_category` du fichier de magnets

**Commit** : `v7.3.2: Implement scrape and verify assertions`

### 7.3.3 — Assertions dispatch + cleanup

- [ ] `assert_dispatch_complete(disk_paths, expected)` :
  - Chaque média est sur un disque dans la bonne catégorie
  - Le dossier dans A TRIER/ n'existe plus (déplacé)
  - Le .e2e-test-marker existe dans le dossier sur le disque destination
    (préservé par rsync — voir DESIGN.md "Cycle de vie du marker")
- [ ] `assert_pipeline_report(report)` :
  - Le PipelineReport contient un StepReport pour chaque étape (ingest→dispatch)
  - Le log file `logs/personalscraper.json` existe et contient les événements attendus
- [ ] `assert_cleanup_complete(registry)` :
  - Aucun chemin du registre n'existe encore sur le filesystem
  - Aucun marker orphelin trouvé par `find_orphan_markers()`
  - Les torrents "e2e-test" ne sont plus dans qBit

**Commit** : `v7.3.3: Implement dispatch and cleanup assertions`
