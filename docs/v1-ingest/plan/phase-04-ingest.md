# Phase 4 — Orchestrateur ingest

## Objectif

Implémenter `ingest.py` : l'orchestrateur appelé par la commande CLI Typer.

## Sous-phases

### 4.1 — Fonction run_ingest et wiring CLI

- [ ] Implémenter `run_ingest(settings, dry_run)` → StepReport
  - ⚠️ Pas de paramètre `verbose` — le niveau de log est configuré globalement par le callback Typer
- [ ] Connecter au stub Typer `ingest` dans `cli.py` :
      appeler `run_ingest(get_settings(), dry_run)`
- [ ] Appeler `acquire_lock()` en début de `run_ingest`, `release_lock()` en `try/finally`
  - Si lock pris → log WARNING "Another instance is running (PID {pid})", retourner StepReport vide
- [ ] Valider que les settings requises sont présentes (qbit\_\*, staging_dir, torrent_complete_dir)

**Commit** : `v1.4.1: Implement run_ingest with lock file and wire to CLI`

### 4.2 — Logique de transfert atomique (copy/move)

- [ ] Implémenter la vérification d'espace disque (`shutil.disk_usage`, seuil `min_free_space_staging_gb`)
- [ ] Implémenter la détection de doublons (fichier/dossier déjà existant dans staging_dir)
- [ ] Implémenter `transfer_torrent(source, dest, copy)` avec copie atomique :
  - **Si copy=True** (torrent en seed) :
    1. Copier vers `dest.parent / '.ingest_tmp_{hash}/'` (dossier temporaire)
    2. Vérifier taille par fichier : `tmp.stat().st_size == source.stat().st_size`
    3. `os.rename(tmp, dest)` — atomique sur même filesystem (SSD)
  - **Si copy=False** (torrent terminé) :
    1. `shutil.move(source, dest)` — sur même filesystem = rename atomique
    2. Vérifier que dest existe et a la bonne taille
  - **Vérification post-transfert** : si mismatch taille → supprimer dest, log ERROR, continuer
- [ ] Au début de chaque run : nettoyer les `.ingest_tmp_*` orphelins dans staging_dir
- [ ] Supporter `--dry-run` (log ce qui serait fait sans le faire)

**Commit** : `v1.4.2: Implement atomic transfer logic (copy/move with verification)`

### 4.3 — Flux principal (main)

- [ ] Assembler le flux complet :
  1. Nettoyer les `.ingest_tmp_*` orphelins (runs précédents interrompus)
  2. Login qBit (via QBitClient context manager)
  3. Récupérer les torrents complétés
  4. Cleanup tracker
  5. Filtrer les non-ingérés
  6. Pour chaque : vérifier espace → transférer (atomique) → vérifier taille → marquer
  7. Alimenter le StepReport (success/skip/error counts)
- [ ] Gestion d'erreurs globale (ne pas crasher sur un torrent individuel)
- [ ] Retourner le StepReport

**Commit** : `v1.4.3: Implement main orchestration flow`

### 4.4 — Test end-to-end en dry-run

- [ ] Lancer `personalscraper ingest --dry-run --verbose` sur les torrents actuels
- [ ] Vérifier que le résumé est correct
- [ ] Vérifier que rien n'est copié/déplacé
- [ ] Fixer les bugs trouvés

**Commit** : `v1.4.4: Fix issues found during dry-run testing`
