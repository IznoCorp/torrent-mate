# Phase 4 — Orchestrateur ingest

## Objectif

Implémenter `ingest.py` : l'orchestrateur appelé par la commande CLI Click.

## Sous-phases

### 4.1 — Fonction run_ingest et wiring CLI

- [ ] Implémenter `run_ingest(settings, dry_run, verbose)` → StepReport
- [ ] Connecter au stub Click `ingest` dans `cli.py` :
      appeler `run_ingest(get_settings(), dry_run, verbose)`
- [ ] Configurer le logger via `get_logger("ingest", verbose, quiet)`
- [ ] Valider que les settings requises sont présentes (qbit\_\*, staging_dir, torrent_complete_dir)

**Commit** : `v1.4.1: Implement run_ingest and wire to CLI command`

### 4.2 — Logique de transfert (copy/move)

- [ ] Implémenter la vérification d'espace disque (`shutil.disk_usage`, seuil `min_free_space_staging_gb`)
- [ ] Implémenter la détection de doublons (fichier/dossier déjà existant dans staging_dir)
- [ ] Implémenter `transfer_torrent()` : copie si seeding, move sinon
  - `shutil.copytree` pour les dossiers en seed
  - `shutil.copy2` pour les fichiers isolés en seed
  - `shutil.move` pour les terminés
- [ ] Supporter `--dry-run` (log ce qui serait fait sans le faire)

**Commit** : `v1.4.2: Implement transfer logic (copy/move with dry-run)`

### 4.3 — Flux principal (main)

- [ ] Assembler le flux complet :
  1. Login qBit (via QBitClient context manager)
  2. Récupérer les torrents complétés
  3. Cleanup tracker
  4. Filtrer les non-ingérés
  5. Pour chaque : vérifier espace → transférer → marquer
  6. Alimenter le StepReport (success/skip/error counts)
- [ ] Gestion d'erreurs globale (ne pas crasher sur un torrent individuel)
- [ ] Retourner le StepReport

**Commit** : `v1.4.3: Implement main orchestration flow`

### 4.4 — Test end-to-end en dry-run

- [ ] Lancer `personalscraper ingest --dry-run --verbose` sur les torrents actuels
- [ ] Vérifier que le résumé est correct
- [ ] Vérifier que rien n'est copié/déplacé
- [ ] Fixer les bugs trouvés

**Commit** : `v1.4.4: Fix issues found during dry-run testing`
