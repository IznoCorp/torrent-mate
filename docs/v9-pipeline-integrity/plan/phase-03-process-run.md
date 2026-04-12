# Phase 3 — Process: cleanup + run_process

## Objectif

Ajouter le nettoyage des dossiers vides et assembler `run_process()` qui coordonne reclean → dedup → scrape → cleanup. Retourne 3 StepReports.

## Sous-phases

### 9.3.1 — cleanup_empty_dirs

- [ ] Creer `personalscraper/process/cleanup.py`
- [ ] `cleanup_empty_dirs(category_dir, dry_run) -> StepReport`
- [ ] Parcours bottom-up : supprime les feuilles vides d'abord, remonte
- [ ] Ignore les fichiers `.DS_Store` (considere le dossier comme vide s'il ne contient que ca)
- [ ] Ne supprime PAS la racine du category_dir elle-meme
- [ ] Dry-run : log sans supprimer
- [ ] StepReport : success_count = dirs supprimés, details = liste des chemins
- [ ] Tests : arbre avec dossiers vides imbriques → tous supprimes
- [ ] Tests : dossier avec fichiers → pas supprime
- [ ] Tests : dossier avec seulement .DS_Store → supprime
- [ ] Tests : ne supprime pas la racine

**Commit** : `v9.3.1: Add cleanup_empty_dirs() recursive empty dir removal`

### 9.3.2 — run_process assembler

- [ ] Creer `personalscraper/process/run.py`
- [ ] `run_process(settings, dry_run, interactive) -> tuple[StepReport, StepReport, StepReport]`
- [ ] Ordre : reclean(movies) + dedup(movies) → reclean(tvshows) + dedup(tvshows) → combine en clean_report
- [ ] Puis : run_scrape(settings, dry_run, interactive) → scrape_report
- [ ] Puis : cleanup(movies) + cleanup(tvshows) → combine en cleanup_report
- [ ] Retourne (clean_report, scrape_report, cleanup_report)
- [ ] Tests : run_process avec mocks → verifie l'ordre d'appel
- [ ] Tests : run_process retourne bien 3 StepReports avec les bons noms

**Commit** : `v9.3.2: Add run_process() assembler returning 3 StepReports`
