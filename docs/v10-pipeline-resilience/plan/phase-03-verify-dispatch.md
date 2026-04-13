# Phase 3 — Verify + Dispatch resilience

## Objectif

Optimiser verify pour ne pas re-appliquer les fixes inutilement, renforcer le nettoyage d'artefacts dispatch, et ajouter les fast-skips restants.

## Sous-phases

### 10.3.1 — Verify skip unnecessary re-fix

- [ ] Dans `verify_movie()` : si le premier check n'a aucun fail ERROR ni fixable → skip fix + re-check
- [ ] Dans `verify_tvshow()` : meme optimisation
- [ ] L'item passe directement a `_classify()` avec les resultats du premier check
- [ ] Status "valid" directement si aucun probleme
- [ ] Ajouter `_has_items_to_verify(settings) -> bool` dans `verify/run.py`
- [ ] Fast-skip : si aucun dossier media present dans 001-MOVIES/ et 002-TVSHOWS/ → retour immediat
- [ ] Tests filesystem : item deja valide (NFO + poster + episodes renommes) → verify skip fix, status "valid"
- [ ] Tests filesystem : item avec probleme fixable → verify applique le fix normalement
- [ ] Tests filesystem : verify double-run → meme resultat, pas de re-fix

**Commit** : `v10.3.1: Skip unnecessary re-fix in verify, add fast-skip`

### 10.3.2 — Dispatch orphan cleanup + fast-skip

- [ ] En debut de `run_dispatch()` : scanner 001-MOVIES/ et 002-TVSHOWS/ pour `_tmp_dispatch_*`
- [ ] Supprimer les dossiers orphelins `_tmp_dispatch_*` avec log WARNING
- [ ] Scanner et supprimer les `.merge_backup/` orphelins dans les sous-dossiers medias
- [ ] Verifier que le fast-skip dispatch existant fonctionne (aucun item dispatchable → skip)
- [ ] Tests filesystem : creer un `_tmp_dispatch_Movie` → dispatch le nettoie avant de commencer
- [ ] Tests filesystem : creer un `.merge_backup/` dans un dossier media → dispatch le nettoie

**Commit** : `v10.3.2: Add dispatch orphan cleanup and verify fast-skip wiring`
