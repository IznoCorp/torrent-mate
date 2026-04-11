# Phase 2 — Pipeline `run` command + rapport

## Objectif

Implémenter la commande `run` qui enchaîne V1→V5 et envoie le rapport.

## Sous-phases

### 6.2.1 — Commande `run` avec pipeline orchestration

- [x] Implémenter `personalscraper run` dans `cli.py` (remplacer le stub)
- [x] Utiliser le lock module de V1 : `from personalscraper.lock import acquire_lock, release_lock`
  - Le module existe déjà — pas besoin de le ré-implémenter
  - `acquire_lock()` en début, `release_lock()` en try/finally
- [x] Si `settings.healthcheck_url` configuré : ping `{url}/start` au début du run
- [x] Au début du run : `cleanup_old_logs(logs_dir)` pour nettoyer les logs > 30 jours
- [x] Au début du run : `structlog.contextvars.clear_contextvars()` + `bind_contextvars(run_id=...)`
- [x] Créer un `PipelineReport` au début
- [x] Séquence : ingest → sort → scrape → verify → dispatch
  - Chaque `run_*()` retourne un `StepReport` (conversion interne dans chaque version)
  - **Responsabilité** : chaque orchestrateur de version (run_ingest, run_sort, etc.) convertit ses résultats internes en StepReport. V6 ne fait qu'agréger et envoyer.
  - `report.add_step("ingest", run_ingest(settings, dry_run))`
  - `report.add_step("sort", run_sort(settings, dry_run))`
  - `report.add_step("scrape", run_scrape(settings, dry_run))`
  - `step_report, verified = run_verify(settings, dry_run)` puis `report.add_step("verify", step_report)`
  - `report.add_step("dispatch", run_dispatch(settings, dry_run, verified=verified))`
  - Chaque étape utilise `log.bind(step=...)` pour le contexte structlog
- [x] Si une étape échoue fatalement → log ERROR, continuer les suivantes
- [x] À la fin : envoyer le rapport via Telegram (si configuré)
- [x] Si `settings.healthcheck_url` configuré : ping `{url}` (success) ou `{url}/fail` (erreur)
- [x] Afficher le résumé en console via `rich.panel.Panel` et `rich.table.Table`
- [x] Support --dry-run (passé à chaque étape)

**Commit** : `v6.2.1: Implement pipeline run command with healthcheck pings`

### 6.2.2 — Tests du pipeline complet

- [x] Test dry-run via CliRunner
- [x] Vérifier que chaque étape est appelée dans l'ordre
- [x] Vérifier que le rapport contient les StepReport de chaque étape
- [x] Vérifier que la notification est envoyée (mock)
- [x] Test avec Telegram non configuré (pas d'erreur)

**Commit** : `v6.2.2: Add pipeline run integration tests`
