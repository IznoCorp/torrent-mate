# Phase 2 — Genre mapper + dispatcher

## Objectif

Implémenter le mapping genre → catégorie et l'orchestrateur de dispatch.

## Sous-phases

### 4.2.1 — Genre mapper

- [ ] Créer `personalscraper/dispatch/genre_mapper.py`
- [ ] Implémenter `GENRE_TO_SUBTYPE` dict (configurable)
- [ ] Implémenter `determine_category(media_type, nfo_path)` : lire le genre du .nfo XML
- [ ] Gérer : Animation → films animations / series animations
- [ ] Gérer : Animation + Japon → series animes
- [ ] Gérer : Documentaire → films documentaires / series documentaires
- [ ] Fallback : films / series si genre non mappé
- [ ] Tests unitaires avec des .nfo réels

**Commit** : `v4.2.1: Implement genre-to-category mapper from NFO`

### 4.2.2 — Dispatcher orchestrator

- [ ] Créer `personalscraper/dispatch/dispatcher.py`
- [ ] Implémenter `Dispatcher.__init__(settings, index, dry_run)`
- [ ] Implémenter `process(staging_dir)` → list[DispatchResult]
- [ ] Implémenter `dispatch_movie(dir)` : genre → find → replace ou move to best disk
- [ ] Implémenter `dispatch_tvshow(dir)` : genre → find → merge ou move to best disk
- [ ] Implémenter `_replace(source, dest)` : move source vers dest.tmp sur même disque,
      supprimer ancien dest, renommer dest.tmp → dest (plus sûr qu'un delete-then-move)
- [ ] Implémenter `_merge(source, dest)` : copie **récursive** (`shutil.copytree` avec
      `dirs_exist_ok=True`), préserve la structure Saison XX/, overwrite si même nom
- [ ] Implémenter `_verify_transfer(source, dest)` : vérifier tailles fichiers
- [ ] Mettre à jour l'index après chaque dispatch
- [ ] Seuil 100 Go, skip + warning si insuffisant
- [ ] Support dry-run
- [ ] Tests unitaires avec tmp_path

**Commit** : `v4.2.2: Implement Dispatcher with replace, merge, and verification`
