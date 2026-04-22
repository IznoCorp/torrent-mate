# V6 — LOG + NOTIFY : Plan d'implémentation

> Notifications Telegram + commande pipeline `run` + scheduling

## Phases

| #   | Phase                                            | Fichier                                              | Status |
| --- | ------------------------------------------------ | ---------------------------------------------------- | ------ |
| 1   | Telegram notifier (compléter le stub V0)         | [phase-01-telegram.md](phase-01-telegram.md)         | [x]    |
| ·   | _Contrôle de cohérence P1→P2_                    |                                                      | [x]    |
| 2   | Pipeline `run` command + rapport                 | [phase-02-pipeline-run.md](phase-02-pipeline-run.md) | [x]    |
| ·   | _Contrôle de cohérence P2→P3_                    |                                                      | [x]    |
| 3   | Scheduling (launchd) + alias + validation finale | [phase-03-cron-final.md](phase-03-cron-final.md)     | [x]    |
| ·   | _Contrôle de cohérence V6 → projet complet_      |                                                      | [x]    |

## Dépendances entre phases

```
Phase 1 (telegram) ──▶ Phase 2 (pipeline run) ──▶ Phase 3 (scheduling + final)
```

Note : le module logger (structlog) est déjà implémenté en V0. V6 complète le notifier, assemble le pipeline, et utilise rich pour l'output console.

## Contrôles de cohérence

### Après Phase 1 (Telegram → Pipeline run)

- [x] `TelegramNotifier.send()` envoie un message (test avec bot réel ou mock)
- [x] `is_configured()` retourne True quand .env contient les tokens
- [x] `is_configured()` retourne False quand .env est vide → pas d'erreur
- [x] `send()` ne crash jamais (try/except, timeout 10s)

### Après Phase 2 (Pipeline run → Cron)

- [x] `personalscraper run --dry-run` exécute V1→V5 en séquence
- [x] Le PipelineReport est correctement alimenté par chaque étape
- [x] `to_html()` produit le message Telegram attendu
- [x] La notification est envoyée en fin de run (si configuré)
- [x] Les logs JSON contiennent `run_id` dans chaque event (contextvars)
- [x] Le résumé console utilise rich Panel/Table

### Après Phase 3 (Scheduling → Projet complet)

- [x] Le LaunchAgent `com.personalscraper.pipeline` est chargé (`launchctl list`)
- [x] `launchctl start com.personalscraper.pipeline` lance le pipeline correctement
- [x] Les logs sont écrits dans `logs/` (structlog) et `~/.personalscraper/launchd-*.log` (stdout/stderr)
- [x] Si healthcheck_url configuré : les pings start/success/fail sont envoyés
- [x] L'alias `personalscraper` fonctionne dans le terminal
- [x] Le pipeline complet fonctionne en dry-run sur les données réelles
- [x] CLAUDE.md est à jour avec toutes les commandes
