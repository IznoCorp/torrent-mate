# Phase 2 — Dispatcher orchestrator

## Objectif

Implémenter l'orchestrateur de dispatch. La catégorisation est fournie par V4 (`personalscraper/genre_mapper.py`).

## Sous-phases

### 5.2.1 — Dispatcher orchestrator avec rsync

- [ ] Créer `personalscraper/dispatch/dispatcher.py`
- [ ] Implémenter `Dispatcher.__init__(settings, index, dry_run)`
- [ ] Implémenter `_rsync(source, dest, delete)` : wrapper subprocess rsync
  - Vérifier que rsync est disponible au `__init__` (`shutil.which("rsync")`)
  - Flags : `-a --partial --checksum` (archive, reprise, vérification)
  - Parser le returncode (0=OK, 23=partial transfer, 24=vanished files)
  - Log stderr si erreur
- [ ] Implémenter `_cleanup_stale_temps(disk_path)` : nettoyer .new.tmp, .old.tmp, .merge-backup-\*
- [ ] Implémenter `process(verified, staging_dir)` → list[DispatchResult]
  - Au début : `_cleanup_stale_temps()` sur chaque disque monté
  - Si `verified` fourni (mode pipeline) : dispatcher chaque VerifyResult.media_path avec sa category
  - Si `staging_dir` fourni (mode standalone) : scanner + categoriser via GenreMapper
- [ ] Implémenter `dispatch_movie(dir, category)` : find → replace ou move to best disk
  - ⚠️ Calculer la taille source AVANT `choose_disk()` et la passer en paramètre
- [ ] Implémenter `dispatch_tvshow(dir, category)` : find → merge ou move to best disk
- [ ] Implémenter `_replace(source, dest)` — crash-safe cross-filesystem :
  1. rsync source → dest.new.tmp/ (même FS que dest)
  2. os.rename(dest, dest.old.tmp) — atomique (même FS)
  3. os.rename(dest.new.tmp, dest) — atomique (même FS)
  4. shutil.rmtree(dest.old.tmp)
  5. Supprimer source dans A TRIER/
  - Recovery : détecter dest.new.tmp/dest.old.tmp orphelins au démarrage
- [ ] Implémenter `_merge(source, dest)` — avec backup/rollback :
  1. Lister fichiers source existant déjà dans dest
  2. Backup fichiers écrasés dans dest/.merge-backup-{timestamp}/
  3. rsync source → dest
  4. Vérifier intégrité (tailles)
  5. Si OK → supprimer backup + source
  6. Si ERREUR → restaurer depuis backup, log ERROR
- [ ] Implémenter `_verify_transfer(source, dest)` : vérifier tailles fichiers récursivement
- [ ] Mettre à jour l'index après chaque dispatch
- [ ] Seuil : `max(min_free_space_disk_gb, item_size_gb * 1.5)`, skip + warning si insuffisant
- [ ] Support dry-run (log rsync commands sans les exécuter)
- [ ] Tests unitaires avec tmp_path (mock rsync subprocess pour les tests)

**Commit** : `v5.2.1: Implement Dispatcher with rsync, backup/rollback, and verification`
