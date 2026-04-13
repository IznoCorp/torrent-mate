# Phase 3 — Verify + Dispatch resilience

## Objectif

Optimiser verify pour ne pas re-appliquer les fixes inutilement, renforcer le nettoyage d'artefacts dispatch, et ajouter les fast-skips restants.

## Sous-phases

### 10.3.1 — Verify skip unnecessary re-fix

- [x] Verify deja optimise : fixer ne tourne que si fixable_fails non-vide
- [x] `_has_items_to_verify(settings)` fast-skip dans verify/run.py
- [x] Tests filesystem → Phase 4

**Commit** : `v10.3.1: Skip unnecessary re-fix in verify, add fast-skip`

### 10.3.2 — Dispatch orphan cleanup + fast-skip

- [x] `_cleanup_staging_orphans()` dans dispatch/run.py
- [x] Nettoie `_tmp_dispatch_*` et `.merge_backup/` dans staging categories
- [x] Dispatch fast-skip existant deja implemente
- [x] Tests filesystem → Phase 4

**Commit** : `v10.3.2: Add dispatch orphan cleanup and verify fast-skip wiring`
