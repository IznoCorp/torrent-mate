# Phase 1 — Fix + Renforcement Tests Critiques

## Objectif

Corriger le test cassé, puis renforcer la couverture des 5 modules critiques identifiés par l'audit : dispatcher (48%), ingest (13%), verifier (63%), scraper orchestration (64%), confidence scoring.

## Prérequis

- Lire le rapport d'audit dans BRAINSTORMING.md section "Audit des tests unitaires"
- Couverture actuelle : `cd "A TRIER" && .venv/bin/python -m pytest tests/ --cov=personalscraper --cov-report=term-missing --ignore=tests/test_cli.py`

## Sous-phases

### 7x.1.1 — Fix test_sort_stub

- [ ] Lire `tests/test_cli.py::test_sort_stub` pour comprendre l'assertion qui échoue
- [ ] Lire `personalscraper/cli.py` — la commande `sort` pour comprendre le code retour
- [ ] Corriger le test (probablement un changement de signature ou de code retour)
- [ ] Vérifier que tous les autres tests de `test_cli.py` passent aussi
- [ ] Lancer `make test` → 0 failures

**Commit** : `v7x.1.1: Fix test_sort_stub assertion`

### 7x.1.2 — Tests dispatcher (replace/merge/rsync)

Objectif couverture : `dispatcher.py` de 48% → 70%+

- [ ] Lire `personalscraper/dispatch/dispatcher.py` lignes non couvertes (voir `--cov-report=term-missing`)
- [ ] Ajouter tests dans `tests/dispatch/test_dispatcher.py` :
  - `test_replace_rsync_failure_cleanup` — rsync retourne non-0 → tmp_new nettoyé
  - `test_replace_atomic_swap_failure_restore` — os.rename échoue → original restauré depuis tmp_old
  - `test_merge_rsync_failure` — rsync échoue → return False
  - `test_merge_verify_failure` — vérification taille échoue → return False
  - `test_move_new_success` — rsync + verify → dest existe, source supprimée
  - `test_move_new_rsync_failure` — rsync échoue → dest n'existe pas
  - `test_dispatch_movie_replace_existing` — film existe dans index → action "replaced"
  - `test_dispatch_movie_new_best_disk` — film absent → action "moved" sur meilleur disque
  - `test_dispatch_tvshow_merge_existing` — série existe → action "merged"
  - `test_dispatch_tvshow_new` — série absente → action "moved"
  - `test_dispatch_no_category_skip` — VerifyResult sans catégorie → skip
  - `test_dispatch_dry_run_no_transfer` — dry_run=True → pas d'appel rsync
- [ ] Mocker rsync via `subprocess.run` (pas d'appel réel)
- [ ] Utiliser `tmp_path` pour les chemins
- [ ] Relancer couverture → vérifier > 70%

**Commit** : `v7x.1.2: Add dispatcher tests for replace, merge, rsync errors`

### 7x.1.3 — Tests ingest orchestration

Objectif couverture : `ingest.py` de 13% → 60%+

- [ ] Lire `personalscraper/ingest/ingest.py` pour identifier les fonctions non couvertes
- [ ] Créer `tests/ingest/test_ingest.py` (nouveau fichier)
- [ ] Ajouter tests :
  - `test_run_ingest_no_completed` — QBitClient retourne 0 torrents → success_count=0
  - `test_run_ingest_already_ingested` — torrent déjà dans tracker → skip_count=1
  - `test_run_ingest_copy_seeding` — torrent en seeding → copié (pas déplacé)
  - `test_run_ingest_move_done` — torrent terminé → déplacé
  - `test_run_ingest_disk_space_fail` — pas assez d'espace → skip
  - `test_run_ingest_verify_fail` — taille ne correspond pas → error_count=1
  - `test_run_ingest_orphan_cleanup` — .ingest*tmp*\* nettoyé au démarrage
  - `test_run_ingest_dry_run` — dry_run=True → pas de copie/move
  - `test_run_ingest_step_report` — vérifier success/skip/error counts corrects
  - `test_run_ingest_multiple` — 3 torrents : 1 copy + 1 move + 1 skip
- [ ] Mocker QBitClient et shutil/os operations
- [ ] Relancer couverture → vérifier > 60%

**Commit** : `v7x.1.3: Add ingest orchestration tests`

### 7x.1.4 — Tests verifier cycle + scraper + confidence

Objectif couverture : `verifier.py` 63% → 80%, `scraper.py` 64% → 75%

- [ ] **Verifier** — Ajouter dans `tests/verify/test_verifier.py` :
  - `test_verify_check_fix_recheck_cycle` — item avec erreur fixable → fixed → re-check valid
  - `test_verify_multiple_issues_all_fixed` — 3 issues fixables → toutes corrigées
  - `test_verify_partial_fix_blocked` — 2 issues dont 1 non fixable → status "blocked"
  - `test_verify_category_correct` — genre "Action" → catégorie "films"
  - `test_verify_dispatchable_filter` — seuls les "valid"/"fixed" avec catégorie sont dispatchables
- [ ] **Scraper** — Ajouter dans `tests/scraper/test_scraper.py` :
  - `test_process_movie_api_failure` — TMDBError → action "error", pipeline continue
  - `test_process_movie_low_confidence` — score < seuil → action "skipped_low_confidence"
  - `test_process_tvshow_full_flow` — match TVDB + NFO + artwork + episodes
  - `test_scraper_already_scraped` — NFO existe → action "skipped_already_done"
- [ ] **Confidence** — Ajouter dans `tests/scraper/test_confidence.py` :
  - `test_malformed_tmdb_missing_title` — réponse sans "title" → pas de crash
  - `test_malformed_tvdb_missing_name` — réponse sans "name" → pas de crash
  - `test_tmdb_tvdb_conflict` — les deux matchent différemment → prendre le meilleur score
- [ ] Relancer couverture globale → cible ≥ 82%
- [ ] Relancer `make test` → 0 failures

**Commit** : `v7x.1.4: Add verifier cycle, scraper orchestration, and confidence tests`
