# Phase 1 — Setup sous-package ingest

## Objectif

Créer le sous-package `personalscraper/ingest/` avec les fichiers vides.

> Note : V0 a déjà créé le package `personalscraper/`, pyproject.toml, .env.example,
> .gitignore, Settings, CLI stubs, et le logger. Cette phase crée uniquement le
> sous-package ingest/ avec ses modules vides.

## Sous-phases

### 1.1 — Créer le sous-package ingest + lock module

- [ ] Créer `personalscraper/ingest/__init__.py`
- [ ] Créer `personalscraper/ingest/qbit_client.py` (vide, avec docstring)
- [ ] Créer `personalscraper/ingest/tracker.py` (vide, avec docstring)
- [ ] Créer `personalscraper/ingest/ingest.py` (vide, avec docstring)
- [ ] Créer `personalscraper/lock.py` avec `acquire_lock()` et `release_lock()`
  - Lock file : `~/.personalscraper/pipeline.lock` (PID du processus)
  - Détection stale lock : `os.kill(pid, 0)` pour vérifier si le processus est vivant
  - Si lock pris par processus vivant → retourner False
  - Si stale → supprimer, prendre le nouveau
- [ ] Créer `tests/ingest/` (vide, avec `__init__.py`)
- [ ] Créer `tests/test_lock.py` avec tests pour :
  - [ ] `acquire_lock()` crée le fichier lock avec le PID
  - [ ] `release_lock()` supprime le fichier lock
  - [ ] Détection de stale lock (processus mort)
  - [ ] Refus de prendre le lock si processus vivant
- [ ] Vérifier : `from personalscraper.ingest import qbit_client` fonctionne
- [ ] Vérifier : `from personalscraper.lock import acquire_lock, release_lock` fonctionne
- [ ] Créer `~/.personalscraper/` si inexistant (pour `ingested_torrents.json` et `pipeline.lock`)

**Commit** : `v1.1.1: Scaffold ingest sub-package and lock module`
