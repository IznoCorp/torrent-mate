# Phase 2 — Dispatcher orchestrator

## Objectif

Implémenter l'orchestrateur de dispatch. La catégorisation est fournie par V4 (verify/genre_mapper.py).

## Sous-phases

### 5.2.1 — Dispatcher orchestrator

- [ ] Créer `personalscraper/dispatch/dispatcher.py`
- [ ] Implémenter `Dispatcher.__init__(settings, index, dry_run)`
- [ ] Implémenter `process(verified, staging_dir)` → list[DispatchResult]
  - Si `verified` fourni (mode pipeline) : dispatcher chaque VerifyResult.media_path avec sa category
  - Si `staging_dir` fourni (mode standalone) : scanner + categoriser via `from personalscraper.verify.genre_mapper import GenreMapper`
- [ ] Implémenter `dispatch_movie(dir, category)` : find → replace ou move to best disk
- [ ] Implémenter `dispatch_tvshow(dir, category)` : find → merge ou move to best disk
- [ ] Implémenter `_replace(source, dest)` : move source vers dest.tmp sur même disque,
      supprimer ancien dest, renommer dest.tmp → dest (plus sûr qu'un delete-then-move)
- [ ] Implémenter `_merge(source, dest)` : copie **récursive** (`shutil.copytree` avec
      `dirs_exist_ok=True`), préserve la structure Saison XX/, overwrite si même nom
- [ ] Implémenter `_verify_transfer(source, dest)` : vérifier tailles fichiers
- [ ] Mettre à jour l'index après chaque dispatch
- [ ] Seuil 100 Go, skip + warning si insuffisant
- [ ] Support dry-run
- [ ] Tests unitaires avec tmp_path

**Commit** : `v5.2.1: Implement Dispatcher with replace, merge, and verification`
