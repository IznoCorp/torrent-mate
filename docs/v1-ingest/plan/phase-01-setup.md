# Phase 1 — Setup sous-package ingest

## Objectif

Créer le sous-package `personalscraper/ingest/` avec les fichiers vides.

> Note : V0 a déjà créé le package `personalscraper/`, pyproject.toml, .env.example,
> .gitignore, Settings, CLI stubs, et le logger. Cette phase crée uniquement le
> sous-package ingest/ avec ses modules vides.

## Sous-phases

### 1.1 — Créer le sous-package ingest

- [ ] Créer `personalscraper/ingest/__init__.py`
- [ ] Créer `personalscraper/ingest/qbit_client.py` (vide, avec docstring)
- [ ] Créer `personalscraper/ingest/tracker.py` (vide, avec docstring)
- [ ] Créer `personalscraper/ingest/ingest.py` (vide, avec docstring)
- [ ] Créer `tests/ingest/` (vide, avec `__init__.py`)
- [ ] Vérifier : `from personalscraper.ingest import qbit_client` fonctionne
- [ ] Créer `~/.personalscraper/` si inexistant (pour `ingested_torrents.json`)

**Commit** : `v1.1.1: Scaffold ingest sub-package`
