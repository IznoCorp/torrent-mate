# Phase 3 — Module logger JSON structuré

## Objectif

Implémenter le logger JSON avec rotation quotidienne, utilisable par toutes les versions.

## Sous-phases

### 0.3.1 — JsonFormatter et get_logger

- [ ] Créer `personalscraper/logger.py`
- [ ] Implémenter `JsonFormatter` : format JSON Lines (timestamp, level, module, message, extra)
- [ ] Implémenter `get_logger(name, verbose, quiet)` :
  - File handler → `logs/personalscraper-YYYY-MM-DD.json`
  - Console handler → format humain lisible
  - verbose → DEBUG, quiet → WARNING, default → INFO
- [ ] Création automatique du dossier `logs/`

**Commit** : `v0.3.1: Implement JSON structured logger`

### 0.3.2 — Rotation et cleanup

- [ ] Implémenter `cleanup_old_logs(logs_dir, retention_days=30)`
- [ ] Appelé au démarrage du logger (supprime les fichiers > 30 jours)
- [ ] Tests unitaires : création de faux fichiers, vérification suppression

**Commit** : `v0.3.2: Add log rotation with 30-day retention`

### 0.3.3 — Intégration CLI

- [ ] Connecter get_logger() au CLI (verbose/quiet flags passés au logger)
- [ ] Chaque sous-commande utilise le logger
- [ ] Test : lancer une commande, vérifier que le fichier log est créé

**Commit** : `v0.3.3: Wire logger into CLI commands`
