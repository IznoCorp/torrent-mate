# Phase 2 — Package core

## Objectif

Implémenter config.py (pydantic Settings), cli.py (Click groups), et models.py.

## Sous-phases

### 0.2.1 — Config (pydantic-settings)

- [ ] Créer `personalscraper/config.py` avec la classe `Settings`
- [ ] Toutes les variables .env mappées avec types et defaults
- [ ] Validation des paths (existence optionnelle au chargement)
- [ ] Fonction `get_settings()` avec cache singleton

**Commit** : `v0.2.1: Implement Settings with pydantic-settings`

### 0.2.2 — CLI (Click groups)

- [ ] Créer `personalscraper/cli.py` avec le groupe principal
- [ ] Sous-commandes stubs : ingest, sort, scrape, dispatch, run
- [ ] Options globales : --verbose, --quiet, --dry-run
- [ ] --version option
- [ ] Chaque sous-commande charge Settings et configure le logger

**Commit** : `v0.2.2: Implement CLI with Click command groups`

### 0.2.3 — Models partagés

- [ ] Créer `personalscraper/models.py`
- [ ] Dataclasses : SortResult, ScrapeResult, DispatchResult, StepReport, PipelineReport
- [ ] Toutes les interfaces définies dans les designs V2-V5

**Commit** : `v0.2.3: Add shared dataclass models`

### 0.2.4 — Notifier stub

- [ ] Créer `personalscraper/notifier.py` avec l'interface TelegramNotifier
- [ ] Implémentation stub : `send()` retourne False, `is_configured()` retourne False
- [ ] Sera complété en V5

**Commit** : `v0.2.4: Add TelegramNotifier stub`

### 0.2.5 — Tests de base

- [ ] Créer `tests/conftest.py` avec fixtures (tmp_path, mock settings)
- [ ] Créer `tests/test_config.py` : test chargement .env
- [ ] Créer `tests/test_cli.py` : test --help, --version via CliRunner
- [ ] Vérifier `make test` passe

**Commit** : `v0.2.5: Add base tests for config and CLI`
