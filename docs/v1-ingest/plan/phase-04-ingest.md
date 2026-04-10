# Phase 4 — Orchestrateur ingest

## Objectif

Implémenter `ingest.py` : le script principal qui orchestre le flux complet.

## Sous-phases

### 4.1 — CLI et chargement config

- [ ] Implémenter `argparse` : `--dry-run`, `--verbose`
- [ ] Charger le `.env` via `python-dotenv`
- [ ] Configurer le logging (stdout + format horodaté)
- [ ] Valider que toutes les variables requises sont présentes

**Commit** : `v1.4.1: Implement CLI args and config loading`

### 4.2 — Logique de transfert (copy/move)

- [ ] Implémenter la vérification d'espace disque (`shutil.disk_usage`)
- [ ] Implémenter la détection de doublons (fichier/dossier déjà existant dans A TRIER/)
- [ ] Implémenter `transfer_torrent()` : copie si seeding, move sinon
  - `shutil.copytree` pour les dossiers en seed
  - `shutil.copy2` pour les fichiers isolés en seed
  - `shutil.move` pour les terminés
- [ ] Supporter `--dry-run` (log ce qui serait fait sans le faire)

**Commit** : `v1.4.2: Implement transfer logic (copy/move with dry-run)`

### 4.3 — Flux principal (main)

- [ ] Assembler le flux complet :
  1. Login qBit
  2. Récupérer les torrents complétés
  3. Cleanup tracker
  4. Filtrer les non-ingérés
  5. Pour chaque : vérifier espace → transférer → marquer
  6. Afficher résumé
- [ ] Gestion d'erreurs globale (ne pas crasher sur un torrent individuel)
- [ ] Exit codes : 0 = succès, 1 = erreur fatale (API), 2 = erreurs partielles

**Commit** : `v1.4.3: Implement main orchestration flow`

### 4.4 — Test end-to-end en dry-run

- [ ] Lancer `ingest.py --dry-run --verbose` sur les 6 torrents actuels
- [ ] Vérifier que le résumé est correct
- [ ] Vérifier que rien n'est copié/déplacé
- [ ] Fixer les bugs trouvés

**Commit** : `v1.4.4: Fix issues found during dry-run testing`
