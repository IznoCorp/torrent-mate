# Phase 5 — Tests E2E séries + test complet pipeline

## Objectif

Test E2E pour les séries (multi-saisons, renommage épisodes), puis test pipeline complet.

## Sous-phases

### 7.5.1 — Test E2E série unique

- [ ] Créer `tests/e2e/test_pipeline_tvshows.py`
- [ ] Test `test_tvshow_full_pipeline()` :
  1. Setup : magnet série → qBit → téléchargement
  2. V1 Ingest → A TRIER/
  3. V2 Sort → 002-TVSHOWS/
  4. V3 Scrape → tvshow.nfo, poster, épisodes renommés `S01E01 - Titre.ext`, NFO épisodes
  5. V4 Verify → vérifier structure saisons, catégorie identifiée
  6. V5 Dispatch → disque de destination (merge si série existante)
  7. Assertions complètes à chaque étape
  8. Cleanup with markers
- [ ] Vérifications spécifiques séries :
  - Dossiers `Saison XX/` créés correctement
  - Épisodes renommés avec les bons titres FR
  - Season posters téléchargés
  - tvshow.nfo contient les IDs TVDB + IMDB

**Commit** : `v7.5.1: Implement full E2E test for a TV show`

### 7.5.2 — Test E2E pipeline complet (films + séries ensemble)

- [ ] Test `test_full_pipeline_mixed()` :
  - Ajouter tous les magnets (films + séries) en une seule session
  - Exécuter le pipeline complet V1→V6 en une seule passe
  - Vérifier tous les résultats
  - Cleanup complet
- [ ] Ce test simule une exécution réelle du scheduling quotidien (tout le batch d'un coup)
- [ ] Vérifier que V6 (log+notify) produit un rapport cohérent : `assert_pipeline_report(report)`

**Commit** : `v7.5.2: Implement full mixed pipeline E2E test`

### 7.5.3 — Commande CLI test-e2e + documentation

- [ ] Ajouter `personalscraper test-e2e` dans cli.py (wrapper autour de pytest)
  - Options : `--dry-run` (vérifier setup sans exécuter), `--cleanup-only` (nettoyer une session précédente)
  - Affiche les prérequis : qBit, disques, magnets configurés
- [ ] Documenter dans le README :
  - Comment configurer `test_magnets.json`
  - Comment exécuter les tests E2E
  - Prérequis (qBit running, disques montés, internet)
- [ ] Vérifier que `pytest` standard (sans `-m e2e`) n'exécute PAS les tests E2E

**Commit** : `v7.5.3: Add test-e2e CLI command and documentation`
