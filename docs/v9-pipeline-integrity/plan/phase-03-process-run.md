# Phase 3 — Process: cleanup + run_process

## Objectif

Ajouter le nettoyage des dossiers vides et assembler `run_process()` qui coordonne reclean → dedup → scrape → cleanup. Retourne 3 StepReports.

## Sous-phases

### 9.3.1 — cleanup_empty_dirs

- [x] Creer `personalscraper/process/cleanup.py`
- [x] `cleanup_empty_dirs(category_dir, dry_run) -> StepReport`
- [x] Parcours bottom-up : supprime les feuilles vides d'abord, remonte
- [x] Ignore les fichiers `.DS_Store` (considere le dossier comme vide s'il ne contient que ca)
- [x] Ne supprime PAS la racine du category_dir elle-meme
- [x] Dry-run : log sans supprimer
- [x] StepReport : success_count = dirs supprimés, details = liste des chemins
- [x] Tests : arbre avec dossiers vides imbriques → tous supprimes
- [x] Tests : dossier avec fichiers → pas supprime
- [x] Tests : dossier avec seulement .DS_Store → supprime
- [x] Tests : ne supprime pas la racine

**Commit** : `v9.3.1: Add cleanup_empty_dirs() recursive empty dir removal`

### 9.3.2 — run_process assembler

- [x] Creer `personalscraper/process/run.py`
- [x] `run_process(settings, dry_run, interactive) -> tuple[StepReport, StepReport, StepReport]`
- [x] Ordre : reclean(movies) + dedup(movies) → reclean(tvshows) + dedup(tvshows) → combine en clean_report
- [x] Puis : run_scrape(settings, dry_run, interactive) → scrape_report
- [x] Puis : cleanup(movies) + cleanup(tvshows) → combine en cleanup_report
- [x] Retourne (clean_report, scrape_report, cleanup_report)
- [x] Tests : run_process avec mocks → verifie l'ordre d'appel
- [x] Tests : run_process retourne bien 3 StepReports avec les bons noms

**Commit** : `v9.3.2: Add run_process() assembler returning 3 StepReports`
