# Phase 4 — Tests resilience filesystem

## Objectif

Ecrire les 10 tests de resilience sur vrai filesystem. Chaque test cree un etat corrompu reel puis verifie le recovery. API mockee pour le scrape, filesystem reel pour tout le reste.

## Sous-phases

### 10.4.1 — Tests recovery scrape (NFO + artwork)

- [ ] Creer `tests/resilience/` avec `__init__.py` et `conftest.py`
- [ ] Fixture `media_dirs` : cree 001-MOVIES/ et 002-TVSHOWS/ dans tmp_path avec settings
- [ ] Test 1 : NFO tronque → ecrire XML invalide, lancer scrape (API mockee), verifier NFO re-cree valide
- [ ] Test 2 : NFO sans uniqueid → ecrire XML parsable sans `<uniqueid>`, lancer scrape, verifier NFO re-cree
- [ ] Test 3 : Artwork partiel → NFO valide + poster, pas de landscape, lancer scrape, verifier landscape re-download
- [ ] Test 8 : Kill mid-scrape simule → NFO partiel + artwork partiel, lancer pipeline, verifier recovery complet

**Commit** : `v10.4.1: Add filesystem resilience tests — scrape recovery`

### 10.4.2 — Tests idempotence (double-run + orphelins)

- [ ] Test 5 : Orphelin `_tmp_dispatch_*` → creer dans 001-MOVIES/, lancer dispatch (dry-run), verifier nettoyage
- [ ] Test 6 : Sort double-run → creer item dans 097-TEMP, sort, re-sort, verifier 2e run skip
- [ ] Test 7 : Pipeline double-run → run complet (API mockee), relancer, verifier 2e run fast-skip tout
- [ ] Test 4 : Merge partiel → creer source + target qui coexistent, lancer clean, verifier re-merge

**Commit** : `v10.4.2: Add filesystem resilience tests — idempotence and orphan cleanup`

### 10.4.3 — Tests double-run verify + clean

- [ ] Test 9 : Verify double-run → creer item valide, verify, re-verify, verifier pas de re-fix
- [ ] Test 10 : Clean double-run → creer dossier pollue, clean, re-clean, verifier 2e run skip
- [ ] Verifier que tous les tests utilisent des vrais fichiers filesystem (pas de mocks filesystem)
- [ ] Verifier que dispatch est en dry-run dans tous les tests

**Commit** : `v10.4.3: Add filesystem resilience tests — verify and clean double-run`
