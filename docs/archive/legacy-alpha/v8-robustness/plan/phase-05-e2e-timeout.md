# Phase 5 — Timeout Dynamique E2E

## Objectif

Ajouter un timeout dynamique basé sur la taille des fichiers à `wait_for_completion()` dans les tests E2E, pour éviter qu'un test reste bloqué indéfiniment sur un torrent qui ne se télécharge pas.

## Sous-phases

### 8.5.1 — Implémenter le timeout dynamique

- [x] Modifier `wait_for_completion()` dans `tests/e2e/setup_torrents.py` :
  - Calculer la taille totale : `sum(t.total_size for t in torrents)` via l'API qBit
  - Convertir en GB : `total_bytes / (1024**3)`
  - Timeout : `max(ceil(total_gb) * 3, 10)` minutes (minimum 10 min)
  - Si `elapsed >= timeout_seconds` → `raise TimeoutError(msg)`
  - Message : `f"Torrent download timed out: {total_gb:.1f} GB, timeout={timeout_min} min, elapsed={elapsed_min} min"`
- [x] Ajouter log au démarrage du wait : `"Waiting for {n} torrents ({size:.1f} GB), timeout={timeout} min"`
- [x] Écrire tests dans `test_setup_torrents.py` :
  - Timeout calculé correctement : 12.6 GB → 39 min
  - Timeout minimum : 0.5 GB → 10 min (pas 3 min)
  - TimeoutError levée quand temps dépassé (mock time.sleep + client)
  - Completion avant timeout → pas d'erreur

**Commit** : `v8.5.1: Add dynamic timeout to wait_for_completion()`

### 8.5.2 — Validation finale et docs

- [x] Lancer tous les tests unitaires (710+) → vérifier que tout passe
- [x] Mettre à jour CLAUDE.md : ajouter note sur le timeout E2E
- [x] Mettre à jour `.env.example` si nécessaire (settings circuit breaker)
- [x] Mettre à jour IMPLEMENTATION.md : section V8 complète

**Commit** : `v8.5.2: Update docs and finalize V8 robustness`
