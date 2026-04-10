# Phase 1 — Infrastructure test (registry, markers)

## Objectif

Implémenter les mécanismes de tracking et sécurité pour les tests E2E.

## Sous-phases

### 7.1.1 — TestRegistry

- [ ] Créer `tests/e2e/registry.py`
- [ ] Implémenter `TestRegistry` dataclass avec `session_id` (UUID), `created_paths`, `torrent_hashes`
- [ ] `register(path)` : ajoute un chemin + persiste immédiatement en JSON
- [ ] `register_torrent(hash)` : ajoute un hash torrent
- [ ] `save()` / `load()` : sérialisation JSON dans `~/.personalscraper/e2e-test-registry-{uuid}.json`
- [ ] `get_cleanup_order()` : retourne les chemins en ordre inverse (enfants d'abord, parents ensuite)
- [ ] Tests unitaires

**Commit** : `v7.1.1: Implement TestRegistry for E2E file tracking`

### 7.1.2 — Markers de test

- [ ] Créer `tests/e2e/markers.py`
- [ ] `place_marker(directory, session_id)` : crée `.e2e-test-marker` contenant le UUID
- [ ] `verify_marker(directory, session_id)` : triple check (fichier existe + UUID match + dans registre)
- [ ] `find_orphan_markers(base_paths)` : scan récursif pour trouver des markers de sessions précédentes
- [ ] Tests unitaires avec tmp_path

**Commit** : `v7.1.2: Implement E2E test markers with triple verification`

### 7.1.3 — Conftest pytest (fixtures)

- [ ] Créer `tests/e2e/conftest.py`
- [ ] Fixture `e2e_session_id` (scope=session) : génère un UUID unique
- [ ] Fixture `e2e_registry` (scope=session) : TestRegistry initialisé
- [ ] Fixture `e2e_qbit_client` (scope=session) : connexion qBit, skip si indisponible
- [ ] Fixture `e2e_magnets` (scope=session) : charge `test_magnets.json`, skip si absent
- [ ] Marqueur `pytest.mark.e2e` configuré dans `pyproject.toml` (exclu du `pytest` standard)
- [ ] `test_magnets.example.json` commité (template), `test_magnets.json` dans `.gitignore`

**Commit** : `v7.1.3: Add pytest fixtures and E2E test configuration`
