# Phase 1 — Telegram notifier

## Objectif

Compléter le stub TelegramNotifier créé en V0 avec l'implémentation réelle.

## Sous-phases

### 6.1.1 — Implémentation TelegramNotifier

- [x] Compléter `personalscraper/notifier.py` (remplacer le stub)
- [x] Implémenter `send(message, parse_mode="HTML")` : POST vers Telegram API
- [x] Timeout 10s, jamais de crash (try/except complet)
- [x] Implémenter `is_configured(settings)` : vérifie bot_token ET chat_id non vides
- [x] Implémenter `send_report(report)` : formate PipelineReport → HTML → send
- [x] Tests avec mock requests (pas d'appel API réel dans les tests)

**Commit** : `v6.1.1: Implement Telegram notifier`

### 6.1.2 — PipelineReport.to_html()

- [x] Implémenter `to_html()` dans `models.py` (PipelineReport)
- [x] Format HTML Telegram avec emojis (conforme au design V6)
- [x] Gérer les cas : rapport vide, seulement des erreurs, tout OK
- [x] Tests : vérifier le HTML généré pour différents scénarios

**Commit** : `v6.1.2: Implement PipelineReport HTML formatting`
