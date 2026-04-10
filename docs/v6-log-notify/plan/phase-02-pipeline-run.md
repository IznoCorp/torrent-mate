# Phase 2 — Pipeline `run` command + rapport

## Objectif

Implémenter la commande `run` qui enchaîne V1→V5 et envoie le rapport.

## Sous-phases

### 6.2.1 — Commande `run` avec pipeline orchestration

- [ ] Implémenter `personalscraper run` dans `cli.py` (remplacer le stub)
- [ ] Utiliser le lock module de V1 : `from personalscraper.lock import acquire_lock, release_lock`
  - Le module existe déjà — pas besoin de le ré-implémenter
  - `acquire_lock()` en début, `release_lock()` en try/finally
- [ ] Si `settings.healthcheck_url` configuré : ping `{url}/start` au début du run
- [ ] Au début du run : `structlog.contextvars.clear_contextvars()` + `bind_contextvars(run_id=...)`
- [ ] Créer un `PipelineReport` au début
- [ ] Séquence : ingest → sort → scrape → verify → dispatch
  - Chaque `run_*()` retourne un `StepReport` (conversion interne dans chaque version)
  - **Responsabilité** : chaque orchestrateur de version (run_ingest, run_sort, etc.) convertit ses résultats internes en StepReport. V6 ne fait qu'agréger et envoyer.
  - `report.add_step("ingest", run_ingest(settings, dry_run))` etc.
  - Chaque étape utilise `log.bind(step=...)` pour le contexte structlog
- [ ] Si une étape échoue fatalement → log ERROR, continuer les suivantes
- [ ] À la fin : envoyer le rapport via Telegram (si configuré)
- [ ] Si `settings.healthcheck_url` configuré : ping `{url}` (success) ou `{url}/fail` (erreur)
- [ ] Afficher le résumé en console via `rich.panel.Panel` et `rich.table.Table`
- [ ] Support --dry-run (passé à chaque étape)

**Commit** : `v6.2.1: Implement pipeline run command with healthcheck pings`

### 6.2.2 — Tests du pipeline complet

- [ ] Test dry-run via CliRunner
- [ ] Vérifier que chaque étape est appelée dans l'ordre
- [ ] Vérifier que le rapport contient les StepReport de chaque étape
- [ ] Vérifier que la notification est envoyée (mock)
- [ ] Test avec Telegram non configuré (pas d'erreur)

**Commit** : `v6.2.2: Add pipeline run integration tests`
