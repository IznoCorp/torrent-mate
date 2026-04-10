# Phase 3 — Module logger structuré (structlog)

## Objectif

Implémenter le logger structuré via structlog avec dual output (console colorée + fichier JSON), utilisable par toutes les versions.

> Ref : [docs/structlog-reference.md](../../structlog-reference.md)

## Sous-phases

### 0.3.1 — configure_logging et get_logger

- [ ] Créer `personalscraper/logger.py`
- [ ] Implémenter `configure_logging(verbose, quiet)` :
  - Processeurs partagés : `merge_contextvars`, `add_log_level`, `TimeStamper(fmt="iso")`, `StackInfoRenderer`, `format_exc_info`
  - Handler console : `ConsoleRenderer(colors=True)` via `ProcessorFormatter`
  - Handler fichier : `TimedRotatingFileHandler` → `logs/personalscraper.json` (rotation midnight, backupCount=30)
  - Formatter fichier : `JSONRenderer()` via `ProcessorFormatter`
  - verbose → DEBUG, quiet → WARNING, default → INFO
  - `foreign_pre_chain` pour les logs stdlib (requests, urllib3, qbittorrent-api)
- [ ] Implémenter `get_logger(name)` → `structlog.get_logger(name)`
- [ ] Création automatique du dossier `logs/`
- [ ] `cache_logger_on_first_use=True` pour la performance

**Commit** : `v0.3.1: Implement structured logger with structlog`

### 0.3.2 — Rotation et cleanup

- [ ] Implémenter `cleanup_old_logs(logs_dir, retention_days=30)`
- [ ] Complément au `backupCount` de `TimedRotatingFileHandler` (nettoyage orphelins)
- [ ] Tests unitaires : création de faux fichiers, vérification suppression

**Commit** : `v0.3.2: Add log cleanup with 30-day retention`

### 0.3.3 — Intégration CLI

- [ ] `configure_logging()` appelé dans le groupe CLI principal (déjà prévu en 0.2.2)
- [ ] Vérifier que `ctx.obj["console"]` (rich) et structlog cohabitent
  - rich pour l'output utilisateur (progress bars, tables, panels)
  - structlog pour le logging opérationnel (debug, diagnostics, traçabilité)
- [ ] Test : lancer une commande, vérifier que le fichier log JSON est créé et parseable

**Commit** : `v0.3.3: Wire structlog into CLI commands`
