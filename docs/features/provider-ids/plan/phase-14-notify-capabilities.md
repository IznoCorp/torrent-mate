# Phase 14 — Notify Capabilities Application + Telegram/Healthchecks Refactor

## Goal

**État codebase actuel** : `api/notify/_base.py` contient **déjà** 2 Protocols séparés et bien nommés — `Notifier` (`:17` ; méthodes `send(message, parse_mode)`, `send_report(report)`) et `HealthChecker` (`:35` ; méthodes `ping_start`, `ping_success`, `ping_fail`). Les classes concrètes existantes sont **`TelegramNotifier`** (`telegram.py:49`) et **`HealthcheckClient`** (`healthchecks.py:46`). Le wiring duck-type existant marche déjà.

Cette phase **rend la composition de Protocol explicite** (`class X(Notifier):` plutôt que duck-type), ajoute `@runtime_checkable` aux Protocols (via la migration phase 1.5 vers `_contracts.py`), et adapte les annotations des consommateurs. **Aucun Protocol monolithique à dropper** — déjà fait.

## Gate (prerequisites)

- Phase 1.5 mergée (`Notifier` et `HealthChecker` migrés de `_base.py` vers `_contracts.py` avec `@runtime_checkable` + re-export depuis `_base.py` pour compat).

## Sub-phases

### 14.1 — Vérifier l'état actuel + ajustements signatures (aucun drop)

Confirmer dans `api/notify/_base.py` que `Notifier(Protocol)` et `HealthChecker(Protocol)` existent. Vérifier que `TelegramNotifier.send` / `TelegramNotifier.send_report` matchent les signatures du Protocol. Si divergence → corriger la classe concrète, pas le Protocol.

Commit : aucun (vérification + ajustements éventuels intégrés dans 14.2/14.3).

### 14.2 — `TelegramNotifier` déclare explicitement `Notifier`

`personalscraper/api/notify/telegram.py:49` : ajouter `Notifier` dans la déclaration : `class TelegramNotifier(Notifier): ...`. Import `Notifier` depuis `personalscraper.api.notify._contracts` (post phase 1.5). Méthodes `send`, `send_report` déjà présentes — vérifier signatures.

Commit : `refactor(provider-ids): TelegramNotifier composes Notifier protocol explicitly`

### 14.3 — `HealthcheckClient` déclare explicitement `HealthChecker`

`personalscraper/api/notify/healthchecks.py:46` : ajouter `HealthChecker` dans la déclaration : `class HealthcheckClient(HealthChecker): ...`. Import depuis `_contracts.py`. Méthodes `ping_start`, `ping_success`, `ping_fail` déjà présentes.

Commit : `refactor(provider-ids): HealthcheckClient composes HealthChecker protocol explicitly`

### 14.4 — Update consommateurs (pipeline.py, cron handlers)

Consommateurs qui notifient → annotations passent à `Notifier` (depuis `_contracts.py`). Consommateurs qui pinguent healthchecks → annotations passent à `HealthChecker`. Si un module utilise les deux → 2 args séparés.

Commit : `refactor(provider-ids): notify consumers use Notifier and HealthChecker capability types`

## Tests to write

- `test_telegram_notifier_is_notifier_isinstance` (vérifie composition explicite + runtime_checkable)
- `test_telegram_notifier_not_health_checker_isinstance`
- `test_healthcheck_client_is_health_checker_isinstance`
- `test_healthcheck_client_not_notifier_isinstance`
- `test_notifier_protocol_methods_match_telegram_notifier_signatures`
- `test_health_checker_protocol_methods_match_healthcheck_client_signatures`
- `test_pipeline_notify_works_with_notifier_capability` (integration)
- `test_pipeline_health_beacon_works_with_health_checker_capability` (integration)

## Acceptance criteria

- `isinstance(TelegramNotifier(...), Notifier)` returns True.
- `isinstance(HealthcheckClient(...), HealthChecker)` returns True.
- `Notifier` et `HealthChecker` ne se chevauchent pas (un client n'implémente que ce qu'il fait).
- Les méthodes existantes (`send`/`send_report`, `ping_start`/`ping_success`/`ping_fail`) sont **préservées sans rename** — pas de breaking change consommateurs.
- Tests pass à 100%.
- Notifications + heartbeats du pipeline fonctionnent inchangés.

## Migration / config touch

Aucune (refactor type-only, signatures inchangées).

## DESIGN reference

§6.2 (api/notify refactor), §4 (Composition par client — adapter pour mentionner les noms réels `Notifier`/`HealthChecker` et classes `TelegramNotifier`/`HealthcheckClient`).
