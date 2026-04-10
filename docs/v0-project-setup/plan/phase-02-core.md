# Phase 2 — Package core

## Objectif

Implémenter config.py (pydantic Settings), cli.py (Typer app), et models.py.

## Sous-phases

### 0.2.1 — Config (pydantic-settings)

- [ ] Créer `personalscraper/config.py` avec la classe `Settings`
- [ ] Toutes les variables .env mappées avec types et defaults
- [ ] Validation des paths (existence optionnelle au chargement)
- [ ] Fonction `get_settings()` avec cache singleton

**Commit** : `v0.2.1: Implement Settings with pydantic-settings`

### 0.2.2 — CLI (Typer app)

- [ ] Créer `personalscraper/cli.py` avec `app = typer.Typer()`
- [ ] `@app.callback()` pour les options globales : --verbose, --quiet, --version
- [ ] Sous-commandes stubs via `@app.command()` : ingest, sort, scrape, verify, dispatch, run
- [ ] Options par commande : --dry-run (type hint `bool = typer.Option(False, "--dry-run")`)
- [ ] Module-level `state` dict pour partager Console et flags entre commandes
- [ ] Créer `Console(quiet=quiet)` dans le callback principal
- [ ] Appeler `configure_logging(verbose, quiet)` dans le callback principal
- [ ] Installer `rich.traceback.install()` pour des tracebacks lisibles
- [ ] Entry point : `personalscraper = "personalscraper.cli:app"`

**Commit** : `v0.2.2: Implement CLI with Typer`

### 0.2.3 — Models partagés

- [ ] Créer `personalscraper/models.py`
- [ ] Dataclasses partagées uniquement : SortResult, StepReport, PipelineReport
  - ScrapeResult → défini en V3 dans `scraper.py` (référence MatchResult local)
  - VerifyResult → défini en V4 dans `verifier.py`
  - DispatchResult → défini en V5 dans `dispatcher.py`
- [ ] Interfaces alignées sur les designs V0+V6 (StepReport et PipelineReport)

**Commit** : `v0.2.3: Add shared dataclass models`

### 0.2.4 — Notifier stub

- [ ] Créer `personalscraper/notifier.py` avec l'interface TelegramNotifier
- [ ] Implémentation stub : `send()` retourne False, `is_configured()` retourne False
- [ ] Sera complété en V6

**Commit** : `v0.2.4: Add TelegramNotifier stub`

### 0.2.5 — Tests de base

- [ ] Créer `tests/conftest.py` avec fixtures (tmp_path, mock settings)
- [ ] Créer `tests/test_config.py` : test chargement .env
- [ ] Créer `tests/test_cli.py` : test --help, --version via CliRunner
- [ ] Vérifier `make test` passe

**Commit** : `v0.2.5: Add base tests for config and CLI`
