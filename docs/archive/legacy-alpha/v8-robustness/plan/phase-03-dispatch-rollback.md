# Phase 3 — Rollback Dispatch

## Objectif

Appliquer le pattern staging→commit à `_move_new()` et améliorer `_merge()` pour éviter les états partiels sur les disques de stockage en cas de crash rsync.

Note : `_replace()` a déjà un pattern staging→commit (dest.new.tmp → atomic swap → cleanup). Pas besoin de le modifier.

## Sous-phases

### 8.3.1 — Rollback \_move_new()

- [x] Modifier `_move_new()` dans `dispatcher.py` :
  - Avant : `rsync source → dest` directement
  - Après : `rsync source → dest.parent / _tmp_dispatch_{dest.name}`
  - Success : `os.rename(tmp_dir, dest)`
  - Failure : `shutil.rmtree(tmp_dir)`, return False
- [x] Vérifier que `dest.parent.mkdir(parents=True, exist_ok=True)` est appelé avant rsync
- [x] Ajouter cleanup des `_tmp_dispatch_*` orphelins au démarrage du dispatcher (init ou process)
- [x] Écrire tests dans `test_dispatcher.py` :
  - \_move_new réussi → dest existe, tmp supprimé
  - \_move_new rsync fail → dest n'existe PAS, tmp supprimé
  - \_move_new avec tmp orphelin existant → nettoyé avant nouvelle tentative
- [x] Vérifier que les tests existants de \_move_new passent

**Commit** : `v8.3.1: Add staging→commit pattern to _move_new()`

### 8.3.2 — Rollback \_merge()

- [x] Modifier `_merge()` dans `dispatcher.py` :
  - Le merge est non-atomique par nature (ajout de fichiers à un dossier existant)
  - Stratégie : rsync avec `--backup --backup-dir=.merge_backup/`
  - Success : supprimer `.merge_backup/` si vide (pas de conflits)
  - Failure : restaurer depuis `.merge_backup/` (rsync inverse), log error
- [x] Écrire tests dans `test_dispatcher.py` :
  - \_merge réussi → fichiers ajoutés, backup nettoyé
  - \_merge rsync fail → backup restauré, état original préservé
  - \_merge avec fichiers existants → backup contient les anciens
- [x] Vérifier que les tests existants de \_merge passent

**Commit** : `v8.3.2: Add backup-based rollback to _merge()`

### 8.3.3 — Cleanup orphelins au démarrage

- [x] Ajouter méthode `_cleanup_orphan_temps()` dans `Dispatcher`
- [x] Scanner chaque disque pour `_tmp_dispatch_*` et `.merge_backup/` orphelins
- [x] Supprimer avec log warning
- [x] Appeler dans `process()` avant le traitement des items
- [x] Écrire tests : orphelins détectés et nettoyés

**Commit** : `v8.3.3: Clean up orphan temp directories on dispatcher startup`
