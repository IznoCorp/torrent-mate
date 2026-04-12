# V7.x — TEST AUDIT : Plan d'implémentation

> Audit exhaustif des tests + golden files E2E pour valider l'exactitude du scrape et dispatch.

## Phases

| #   | Phase                              | Fichier                                                                | Status |
| --- | ---------------------------------- | ---------------------------------------------------------------------- | ------ |
| 1   | Fix + renforcement tests critiques | [phase-01-test-reinforcement.md](phase-01-test-reinforcement.md)       | [x]    |
| ·   | _Contrôle de cohérence P1→P2_      |                                                                        | [x]    |
| 2   | Infrastructure golden files        | [phase-02-golden-infrastructure.md](phase-02-golden-infrastructure.md) | [x]    |
| ·   | _Contrôle de cohérence P2→P3_      |                                                                        | [x]    |
| 3   | Génération golden files (MANUELLE) | [phase-03-golden-generation.md](phase-03-golden-generation.md)         | [ ]    |
| ·   | _Contrôle de cohérence P3→P4_      |                                                                        | [ ]    |
| 4   | Intégration E2E                    | [phase-04-e2e-integration.md](phase-04-e2e-integration.md)             | [ ]    |

## Dépendances entre phases

```
P1 (fix + renforcement) ──────────────────────> indépendant
P2 (golden infrastructure) ───────────────────> indépendant
P3 (golden generation) ───> dépend de P2 (format JSON défini en P2)
P4 (E2E integration) ────> dépend de P2 + P3 (infrastructure + données)

Ordre imposé : P1, P2, P3, P4
(P1 et P2 sont indépendants mais P1 d'abord pour stabiliser la suite de tests)
```

## Contrôles de cohérence

### Après Phase 1 (fix + renforcement → golden infrastructure)

- [x] Tous les tests existants passent (720 passants, 0 échec)
- [x] `test_sort_stub` corrigé et passant (→ `test_sort_command`)
- [x] Couverture `dispatcher.py` > 65% (48% → 85%)
- [x] Couverture `ingest.py` > 50% (13% → 87%)
- [x] Couverture `verifier.py` > 75% (63% → 82%)
- [x] Pas de régression sur les tests existants

### Après Phase 2 (golden infrastructure → golden generation)

- [x] `golden.py` importable et testé (load, match, discover) — 14 tests
- [x] Les 3 nouvelles assertions (`assert_scrape_golden`, `assert_dispatch_golden`, `assert_structure_golden`) ont leurs propres unit tests — 14 tests
- [x] Le format JSON est documenté et un schéma d'exemple existe (DESIGN.md)

### Après Phase 3 (golden generation → E2E integration)

- [ ] Golden files existent pour Jumanji et Malcolm
- [ ] Les golden files ont été validés humainement
- [ ] Les fichiers JSON sont valides et chargent sans erreur

### Après Phase 4 (E2E integration)

- [ ] Les 3 tests E2E pipeline utilisent les golden files
- [ ] Les anciennes assertions restent en place (rétrocompatibilité)
- [ ] Un test E2E sans golden file (nouveau torrent) continue de fonctionner avec les smoke tests seuls
