# Phase 2 — Pipeline `run` command + rapport

## Objectif

Implémenter la commande `run` qui enchaîne V1→V4 et envoie le rapport.

## Sous-phases

### 5.2.1 — Commande `run`

- [ ] Implémenter `personalscraper run` dans `cli.py` (remplacer le stub)
- [ ] Séquence : ingest → sort → scrape → dispatch
- [ ] Créer un `PipelineReport` au début, passer à chaque étape
- [ ] Chaque étape alimente son `StepReport`
- [ ] Si une étape échoue fatalement → log ERROR, continuer les suivantes
- [ ] À la fin : envoyer le rapport via Telegram (si configuré)
- [ ] Afficher le résumé en console
- [ ] Support --dry-run (passé à chaque étape)

**Commit** : `v5.2.1: Implement pipeline run command`

### 5.2.2 — Tests du pipeline complet

- [ ] Test dry-run via CliRunner
- [ ] Vérifier que chaque étape est appelée dans l'ordre
- [ ] Vérifier que le rapport contient les StepReport de chaque étape
- [ ] Vérifier que la notification est envoyée (mock)
- [ ] Test avec Telegram non configuré (pas d'erreur)

**Commit** : `v5.2.2: Add pipeline run integration tests`
