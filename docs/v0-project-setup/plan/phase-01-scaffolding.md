# Phase 1 — Scaffolding projet

## Objectif

Créer la structure de base du projet Python avec pyproject.toml, Makefile, et .gitignore.

## Sous-phases

### 0.1.1 — pyproject.toml

- [ ] Créer `pyproject.toml` basé sur TorrentMaker
- [ ] Configurer : name=personalscraper, version dynamique, Python>=3.10
- [ ] Ajouter dependencies (typer, pydantic-settings, python-dotenv, requests, qbittorrent-api, guessit, rapidfuzz, tenacity, rich, structlog)
- [ ] Ajouter optional-dependencies dev (pytest, pytest-cov, ruff)
- [ ] Configurer `[project.scripts]` : personalscraper = personalscraper.cli:app
- [ ] Configurer `[tool.ruff]` : target-version py310, line-length 120, rules E/F/I/W
- [ ] Configurer `[tool.pytest.ini_options]` : testpaths, pythonpath

**Commit** : `v0.1.1: Add pyproject.toml with project config and tooling`

### 0.1.2 — Makefile

- [ ] Créer `Makefile` avec targets : help, clean, test, lint, format, install-dev, version
- [ ] Basé sur le Makefile de TorrentMaker

**Commit** : `v0.1.2: Add Makefile with standard targets`

### 0.1.3 — .env.example et .gitignore

- [ ] Créer `.env.example` avec toutes les sections (qBit, Paths, TMDB, TVDB, Telegram, Thresholds)
- [ ] Mettre à jour `.gitignore` : ajouter `.env`, `logs/`, `*.egg-info/`, `dist/`, `build/`
- [ ] Créer `personalscraper/__init__.py` avec `__version__ = "0.1.0"`

**Commit** : `v0.1.3: Add .env.example, update .gitignore, init package`
