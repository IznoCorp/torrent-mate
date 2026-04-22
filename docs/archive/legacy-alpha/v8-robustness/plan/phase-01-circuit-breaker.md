# Phase 1 — Circuit Breaker API

## Objectif

Protéger le pipeline contre les pannes durables des APIs TMDB/TVDB. Le circuit breaker se place au-dessus de tenacity (qui gère les erreurs transitoires) pour détecter quand un provider est durablement down et éviter de le spammer.

## Sous-phases

### 8.1.1 — CircuitBreaker classe générique

- [x] Créer `personalscraper/scraper/circuit_breaker.py`
- [x] Implémenter `CircuitState` enum (CLOSED, OPEN, HALF_OPEN)
- [x] Implémenter `CircuitBreaker` avec :
  - `__init__(name, failure_threshold=5, cooldown_seconds=300)`
  - `record_success()` → reset error count, state → CLOSED
  - `record_failure(exc)` → increment si 5xx/Timeout/ConnectionError, ignorer 429/4xx
  - `can_proceed()` → True si CLOSED ou HALF_OPEN (cooldown écoulé)
  - `reset()` → retour à CLOSED
  - `_is_circuit_error(exc)` → True pour 5xx, Timeout, ConnectionError
- [x] Implémenter `CircuitOpenError(provider, remaining_seconds)`
- [x] Écrire `tests/scraper/test_circuit_breaker.py` avec tests :
  - État initial CLOSED
  - 4 failures → reste CLOSED
  - 5 failures → passe OPEN
  - OPEN → can_proceed() returns False
  - OPEN → attendre cooldown → passe HALF_OPEN
  - HALF_OPEN → success → passe CLOSED
  - HALF_OPEN → failure → retourne OPEN
  - 429 non compté (reste CLOSED)
  - 4xx non compté (reste CLOSED)
  - reset() → retour CLOSED depuis n'importe quel état

**Commit** : `v8.1.1: Add CircuitBreaker class with state machine and tests`

### 8.1.2 — Intégrer dans TMDBClient

- [x] Ajouter `self._circuit = CircuitBreaker(name="TMDB")` dans `__init__`
- [x] Modifier `_get()` : vérifier `can_proceed()` avant l'appel, appeler `record_success()`/`record_failure()` selon le résultat
- [x] Exposer `circuit` property pour le scraper
- [x] Ajouter settings : `circuit_breaker_threshold` et `circuit_breaker_cooldown` dans `config.py`
- [x] Mettre à jour tests existants : les mocks de `_get()` doivent toujours fonctionner
- [x] Ajouter tests spécifiques : `_get()` avec circuit OPEN → CircuitOpenError

**Commit** : `v8.1.2: Integrate CircuitBreaker into TMDBClient`

### 8.1.3 — Intégrer dans TVDBClient

- [x] Même pattern que TMDB : `self._circuit = CircuitBreaker(name="TVDB")`
- [x] Modifier `_get()` avec circuit breaker
- [x] Exposer `circuit` property
- [x] Vérifier que le re-login sur 401 n'est PAS bloqué par le circuit breaker (401 = pas une circuit error)
- [x] Mettre à jour tests existants

**Commit** : `v8.1.3: Integrate CircuitBreaker into TVDBClient`

### 8.1.4 — Fallback inter-provider dans Scraper

- [x] Modifier `scraper.py:process_movies()` : catch `CircuitOpenError` sur TMDB → tenter TVDB
- [x] Modifier `scraper.py:process_tvshows()` : catch `CircuitOpenError` sur TVDB → tenter TMDB
- [x] Si les deux circuits sont OPEN → skip item avec log warning
- [x] Ajouter tests dans `test_scraper.py` : fallback provider quand primaire est down
- [x] Vérifier que les 459 tests passent (modules avec deps installées)

**Commit** : `v8.1.4: Add inter-provider fallback on CircuitOpenError`
