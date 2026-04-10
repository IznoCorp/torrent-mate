# V6 — LOG + NOTIFY : Plan d'implémentation

> Notifications Telegram + commande pipeline `run` + cron

## Phases

| #   | Phase                                       | Fichier                                              | Status |
| --- | ------------------------------------------- | ---------------------------------------------------- | ------ |
| 1   | Telegram notifier (compléter le stub V0)    | [phase-01-telegram.md](phase-01-telegram.md)         | [ ]    |
| ·   | _Contrôle de cohérence P1→P2_               |                                                      | [ ]    |
| 2   | Pipeline `run` command + rapport            | [phase-02-pipeline-run.md](phase-02-pipeline-run.md) | [ ]    |
| ·   | _Contrôle de cohérence P2→P3_               |                                                      | [ ]    |
| 3   | Cron + alias + validation finale            | [phase-03-cron-final.md](phase-03-cron-final.md)     | [ ]    |
| ·   | _Contrôle de cohérence V6 → projet complet_ |                                                      | [ ]    |

## Dépendances entre phases

```
Phase 1 (telegram) ──▶ Phase 2 (pipeline run) ──▶ Phase 3 (cron + final)
```

Note : le module logger (structlog) est déjà implémenté en V0. V6 complète le notifier, assemble le pipeline, et utilise rich pour l'output console.

## Contrôles de cohérence

### Après Phase 1 (Telegram → Pipeline run)

- [ ] `TelegramNotifier.send()` envoie un message (test avec bot réel ou mock)
- [ ] `is_configured()` retourne True quand .env contient les tokens
- [ ] `is_configured()` retourne False quand .env est vide → pas d'erreur
- [ ] `send()` ne crash jamais (try/except, timeout 10s)

### Après Phase 2 (Pipeline run → Cron)

- [ ] `personalscraper run --dry-run` exécute V1→V5 en séquence
- [ ] Le PipelineReport est correctement alimenté par chaque étape
- [ ] `to_html()` produit le message Telegram attendu
- [ ] La notification est envoyée en fin de run (si configuré)
- [ ] Les logs JSON contiennent `run_id` dans chaque event (contextvars)
- [ ] Le résumé console utilise rich Panel/Table

### Après Phase 3 (Scheduling → Projet complet)

- [ ] Le LaunchAgent `com.personalscraper.pipeline` est chargé (`launchctl list`)
- [ ] `launchctl start com.personalscraper.pipeline` lance le pipeline correctement
- [ ] Les logs sont écrits dans `logs/` (structlog) et `~/.personalscraper/launchd-*.log` (stdout/stderr)
- [ ] Si healthcheck_url configuré : les pings start/success/fail sont envoyés
- [ ] L'alias `personalscraper` fonctionne dans le terminal
- [ ] Le pipeline complet fonctionne en dry-run sur les données réelles
- [ ] CLAUDE.md est à jour avec toutes les commandes
