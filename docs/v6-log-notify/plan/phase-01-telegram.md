# Phase 1 — Telegram notifier

## Objectif

Compléter le stub TelegramNotifier créé en V0 avec l'implémentation réelle.

## Sous-phases

### 5.1.1 — Implémentation TelegramNotifier

- [ ] Compléter `personalscraper/notifier.py` (remplacer le stub)
- [ ] Implémenter `send(message, parse_mode="HTML")` : POST vers Telegram API
- [ ] Timeout 10s, jamais de crash (try/except complet)
- [ ] Implémenter `is_configured(settings)` : vérifie bot_token ET chat_id non vides
- [ ] Implémenter `send_report(report)` : formate PipelineReport → HTML → send
- [ ] Tests avec mock requests (pas d'appel API réel dans les tests)

**Commit** : `v5.1.1: Implement Telegram notifier`

### 5.1.2 — PipelineReport.to_html()

- [ ] Implémenter `to_html()` dans `models.py` (PipelineReport)
- [ ] Format HTML Telegram avec emojis (conforme au design V5)
- [ ] Gérer les cas : rapport vide, seulement des erreurs, tout OK
- [ ] Tests : vérifier le HTML généré pour différents scénarios

**Commit** : `v5.1.2: Implement PipelineReport HTML formatting`
