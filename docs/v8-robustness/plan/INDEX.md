# V8 — ROBUSTNESS : Plan d'implémentation

> Durcissement du pipeline : circuit breaker, anti-faux-positifs, rollback dispatch, fallback disque, timeout E2E.

## Phases

| #   | Phase                         | Fichier                                                        | Status |
| --- | ----------------------------- | -------------------------------------------------------------- | ------ |
| 1   | Circuit breaker API           | [phase-01-circuit-breaker.md](phase-01-circuit-breaker.md)     | [x]    |
| ·   | _Contrôle de cohérence P1→P2_ |                                                                | [x]    |
| 2   | Anti-faux-positifs fuzzy      | [phase-02-fuzzy-guards.md](phase-02-fuzzy-guards.md)           | [x]    |
| ·   | _Contrôle de cohérence P2→P3_ |                                                                | [x]    |
| 3   | Rollback dispatch             | [phase-03-dispatch-rollback.md](phase-03-dispatch-rollback.md) | [x]    |
| ·   | _Contrôle de cohérence P3→P4_ |                                                                | [x]    |
| 4   | Fallback disque + auto-create | [phase-04-disk-fallback.md](phase-04-disk-fallback.md)         | [x]    |
| ·   | _Contrôle de cohérence P4→P5_ |                                                                | [x]    |
| 5   | Timeout dynamique E2E         | [phase-05-e2e-timeout.md](phase-05-e2e-timeout.md)             | [x]    |

## Dépendances entre phases

```
P1 (circuit breaker) ─────────────────────────────> indépendant
P2 (fuzzy guards) ────────────────────────────────> indépendant
P3 (dispatch rollback) ───> dépend de P2 (fuzzy guards affecte media_index.find)
P4 (disk fallback) ───────> dépend de P3 (choose_disk modifié en P4, dispatcher en P3)
P5 (E2E timeout) ─────────────────────────────────> indépendant

Ordre imposé : P1, P2, P3, P4, P5
(P1 et P2 sont indépendants mais séquencés pour simplicité)
```

## Contrôles de cohérence

### Après Phase 1 (circuit breaker → fuzzy guards)

- [x] CircuitBreaker n'impacte pas les tests existants du scraper (53 TMDB + 40 TVDB)
- [x] Les mocks existants dans test_tmdb_client.py ne cassent pas avec le nouveau self.\_circuit
- [x] `_is_retryable()` ne compte toujours PAS les 429 (tenacity seul les gère)

### Après Phase 2 (fuzzy guards → dispatch rollback)

- [x] `fuzzy_match_score()` dans text_utils.py est importable par media_index.py ET matcher.py
- [x] Les tests existants de test_matcher.py (14 passent, 3 adaptés V8) et test_media_index.py (10 passent)
- [x] Le seuil adaptatif ne casse pas les vrais matchs (Jumanji, Avengers testés)

### Après Phase 3 (dispatch rollback → disk fallback)

- [x] `_move_new()` modifié passe les tests existants de test_dispatcher.py (35 tests passent)
- [x] Le pattern `_tmp_dispatch_` ne rentre pas en conflit avec `.new.tmp`/`.old.tmp` de `_replace()`
- [x] Les tests de `_replace()` existants ne sont pas affectés

### Après Phase 4 (disk fallback → E2E timeout)

- [x] `choose_disk()` avec `allow_create_category=False` (défaut) a le même comportement qu'avant
- [x] Les tests existants de test_disk_scanner.py (7 tests) passent sans modification
- [x] Le dispatcher crée le dossier catégorie uniquement pour les nouveaux médias (`allow_create_category=True` pour new, pas pour replace/merge)
