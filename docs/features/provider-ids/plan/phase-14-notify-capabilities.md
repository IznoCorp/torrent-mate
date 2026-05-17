# Phase 14 — Notify Capabilities + Telegram/Healthchecks Refactor

## Goal

Casser le `NotifierClient(Protocol)` monolithique existant (`api/notify/_base.py`) en capabilities : `Notifier`, `HealthBeacon`. Refactor `TelegramClient` (notifications) et `HealthcheckClient` (heartbeat) pour qu'ils déclarent ce qu'ils supportent.

## Gate (prerequisites)

- Phase 1 mergée (capabilities Protocols définis).

## Sub-phases

### 14.1 — Inspecter `_base.py` actuel + drop monolithique

Lire `personalscraper/api/notify/_base.py` pour confirmer le Protocol actuel (peut être déjà simple à ~1 méthode). Soit drop le Protocol monolithique soit le réorganiser en `Notifier` + `HealthBeacon` si déjà séparé.

Commit : `refactor(provider-ids): drop monolithic NotifierClient Protocol if present`

### 14.2 — `TelegramClient` compose `Notifier`

`personalscraper/api/notify/telegram.py` : déclare `class TelegramClient(Notifier): ...`. Méthode `notify(message, level="info")` existante.

Commit : `refactor(provider-ids): TelegramClient composes Notifier capability`

### 14.3 — `HealthcheckClient` compose `HealthBeacon`

`personalscraper/api/notify/healthchecks.py:46` : déclare `class HealthcheckClient(HealthBeacon): ...`. Méthodes `ping_success`, `ping_failure(message)`.

Commit : `refactor(provider-ids): HealthcheckClient composes HealthBeacon capability`

### 14.4 — Update consommateurs (pipeline.py, cron handlers)

Consommateurs qui notifient (errors, completion) : annotations passent à `Notifier`. Consommateurs qui pinguent healthchecks : annotations passent à `HealthBeacon`. Si un module utilise les deux, accepter les deux en arg séparés.

Commit : `refactor(provider-ids): notify consumers use Notifier and HealthBeacon types`

## Tests to write

- `test_telegram_client_is_notifier_isinstance`
- `test_telegram_client_not_health_beacon_isinstance`
- `test_healthcheck_client_is_health_beacon_isinstance`
- `test_healthcheck_client_not_notifier_isinstance`
- `test_no_more_monolithic_notifier_client_protocol_exists`
- `test_pipeline_notify_works_with_notifier_capability`
- `test_pipeline_health_beacon_works_with_health_beacon_capability`

## Acceptance criteria

- `isinstance(TelegramClient(...), Notifier)` returns True.
- `isinstance(HealthcheckClient(...), HealthBeacon)` returns True.
- Les capabilities `Notifier` et `HealthBeacon` ne se chevauchent pas (un client n'a pas besoin de tout implémenter).
- Tests pass à 100%.
- Notifications + heartbeats du pipeline fonctionnent inchangés.

## Migration / config touch

Aucune (refactor type-only).

## DESIGN reference

§6.2 (api/notify refactor), §4 (Composition par client).
