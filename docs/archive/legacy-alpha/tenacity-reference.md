# tenacity — Reference Documentation

> Date : 2026-04-10 | Contexte : V3 SCRAPE — retry avec backoff pour les appels API TMDB/TVDB

## Qu'est-ce que tenacity ?

[tenacity](https://github.com/jd/tenacity) (v9.1+) est une librairie de retry pour Python. Elle
permet de ré-essayer des appels de fonctions avec des stratégies de wait, stop, et conditions
de retry composables via des décorateurs.

**Utilisé pour** : Gérer les erreurs transitoires des APIs TMDB et TVDB (timeouts, rate limits 429,
erreurs serveur 5xx) dans les modules `tmdb_client.py` et `tvdb_client.py` (V3).

**Version** : >= 9.1.3 (ajout de `wait_exception` pour lire `Retry-After`)
**Licence** : Apache 2.0
**Python** : >= 3.10
**Dépendances** : Aucune

## Installation

```bash
pip install tenacity
```

## API principale — `@retry`

### Signature complète

```python
from tenacity import retry

@retry(
    wait=wait_none(),                    # Délai entre les tentatives
    stop=stop_never,                     # Quand arrêter
    retry=retry_if_exception_type(),     # Quand retenter (défaut: toute Exception)
    before=before_nothing,               # Callback avant chaque tentative
    after=after_nothing,                 # Callback après chaque échec
    before_sleep=None,                   # Callback avant le sleep (logging)
    reraise=False,                       # True = re-raise exception originale
)
def my_function():
    ...
```

**ATTENTION** : `@retry` sans arguments retente **à l'infini** sans **aucun délai**.
Toujours spécifier `stop` et `wait`.

### Paramètre `reraise`

- `reraise=False` (défaut) : encapsule dans `RetryError` → les `except` doivent catcher `RetryError`
- `reraise=True` (recommandé) : re-raise l'exception originale → stack traces propres

## Stratégies de wait

### `wait_fixed(seconds)`

Délai constant entre chaque tentative.

```python
from tenacity import wait_fixed
@retry(wait=wait_fixed(2))  # 2s entre chaque retry
```

### `wait_exponential(multiplier=1, min=0, max=MAX_WAIT, exp_base=2)`

Backoff exponentiel : `clamp(min, multiplier * exp_base^(attempt-1), max)`

```python
from tenacity import wait_exponential
@retry(wait=wait_exponential(multiplier=1, min=1, max=60))
# Attempt 1: 1s, Attempt 2: 2s, Attempt 3: 4s, ..., plafonné à 60s
```

### `wait_exponential_jitter(multiplier=1, max=MAX_WAIT, jitter=1)`

Exponentiel + jitter aléatoire additif. Pattern recommandé par AWS.

```python
from tenacity import wait_exponential_jitter
@retry(wait=wait_exponential_jitter(multiplier=1, max=60, jitter=2))
# Exponentiel + random(0, 2) secondes de jitter
```

### `wait_random_exponential(multiplier=1, min=0, max=MAX_WAIT)`

"Full jitter" : `uniform(min, exponential_result)`. Plus agressif que `wait_exponential_jitter`.

### `wait_exception(predicate)` — NOUVEAU v9.1.3

Extrait le délai depuis l'exception. **Parfait pour lire le header `Retry-After`.**

```python
from tenacity import wait_exception

def get_retry_after(exc):
    """Lire Retry-After depuis une HTTPError."""
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after:
            return float(retry_after)
    return 1.0  # fallback 1 seconde

@retry(wait=wait_exception(get_retry_after))
```

### Combiner des waits avec `+`

```python
# Exponentiel + jitter random
@retry(wait=wait_exponential(multiplier=1, max=30) + wait_random(0, 2))
```

### `wait_chain(*strategies)`

Stratégies séquentielles. La dernière se répète.

```python
from tenacity import wait_chain
@retry(wait=wait_chain(*[wait_fixed(1)]*3, *[wait_fixed(5)]*2, wait_fixed(10)))
# 1s, 1s, 1s, 5s, 5s, 10s, 10s, 10s, ...
```

## Stratégies de stop

### `stop_after_attempt(n)`

Arrêter après N tentatives au total.

```python
from tenacity import stop_after_attempt
@retry(stop=stop_after_attempt(4))  # 1 essai initial + 3 retries max
```

### `stop_after_delay(seconds)`

Arrêter après un temps total écoulé.

```python
from tenacity import stop_after_delay
@retry(stop=stop_after_delay(30))  # Arrêter après 30s au total
```

**Attention** : Le sleep final peut dépasser `max_delay`. Utiliser `stop_before_delay` pour un timeout strict.

### Combiner avec `|` (OR) et `&` (AND)

```python
# Arrêter après 5 tentatives OU 30 secondes (ce qui arrive en premier)
@retry(stop=stop_after_attempt(5) | stop_after_delay(30))
```

## Conditions de retry

### `retry_if_exception_type(types)`

Retenter sur un type d'exception spécifique.

```python
from tenacity import retry_if_exception_type
@retry(retry=retry_if_exception_type(ConnectionError))
```

### `retry_if_exception(predicate)`

Retenter selon un prédicat custom.

```python
from tenacity import retry_if_exception

def is_retryable(exc):
    if isinstance(exc, requests.exceptions.HTTPError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    return False

@retry(retry=retry_if_exception(is_retryable))
```

### `retry_if_result(predicate)`

Retenter selon la valeur de retour.

```python
from tenacity import retry_if_result
@retry(retry=retry_if_result(lambda x: x is None))  # Retenter si None
```

### Combiner avec `|` (OR)

```python
@retry(
    retry=(
        retry_if_exception_type((ConnectionError, Timeout))
        | retry_if_exception(lambda e: isinstance(e, HTTPError) and e.response.status_code >= 500)
    )
)
```

## Callbacks de logging

### `before_sleep_log` — RECOMMANDÉ

Log avant chaque sleep (pas appelé avant la première tentative).

```python
import logging
from tenacity import before_sleep_log

logger = logging.getLogger(__name__)

@retry(
    before_sleep=before_sleep_log(logger, logging.WARNING),
    # Log: "Retrying my_function in 2.0 seconds as it raised ConnectionError."
)
```

Avec traceback complet : `before_sleep_log(logger, logging.WARNING, exc_info=True)`

### `after_log`

Log après chaque tentative échouée.

```python
from tenacity import after_log
@retry(after=after_log(logger, logging.WARNING))
# Log: "Finished call to 'my_func' after 4.123s, this was the 3rd time calling it."
```

## Patterns pour le pipeline

### Client TMDB (40 req/s, 429 avec Retry-After)

```python
import requests
import logging
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception, before_sleep_log,
)

logger = logging.getLogger("personalscraper.scraper.tmdb_client")

def _is_retryable(exc: BaseException) -> bool:
    """Retry sur 429/5xx et erreurs réseau. PAS sur 400/401/403/404."""
    if isinstance(exc, requests.exceptions.HTTPError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))

@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential_jitter(multiplier=0.5, max=10, jitter=0.5),
    stop=stop_after_attempt(4),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _tmdb_get(session: requests.Session, endpoint: str, params: dict) -> dict:
    """GET TMDB API avec retry automatique."""
    resp = session.get(
        f"https://api.themoviedb.org/3{endpoint}",
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
```

### Client TVDB (token JWT, limites moins documentées)

```python
@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _tvdb_get(session: requests.Session, endpoint: str, headers: dict) -> dict:
    """GET TVDB API avec retry automatique."""
    resp = session.get(
        f"https://api4.thetvdb.com/v4{endpoint}",
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
```

### Approche double couche (transport + application)

Pour une fiabilité maximale, combiner `urllib3.Retry` (transport) avec tenacity (application) :

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry as Urllib3Retry

# Couche 1 : transport (DNS, TCP, TLS)
transport_retry = Urllib3Retry(total=2, backoff_factor=0.5, status_forcelist=[502, 503, 504])
adapter = HTTPAdapter(max_retries=transport_retry)
session = requests.Session()
session.mount("https://", adapter)

# Couche 2 : application (429, logique métier) — tenacity sur les fonctions
@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential_jitter(multiplier=0.5, max=10, jitter=0.5),
    stop=stop_after_attempt(4),
    reraise=True,
)
def api_call(url):
    resp = session.get(url, timeout=10)  # urllib3 gère les erreurs transport
    resp.raise_for_status()               # tenacity gère les 429/5xx
    return resp.json()
```

### Retry-After avec fallback exponentiel (pré-9.1.3)

Si on n'a pas accès à `wait_exception` (version < 9.1.3) :

```python
class WaitRetryAfterOrExponential(wait_exponential):
    """Lire Retry-After si disponible, sinon backoff exponentiel."""
    def __call__(self, retry_state):
        exc = retry_state.outcome.exception()
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            retry_after = exc.response.headers.get("Retry-After")
            if retry_after:
                return float(retry_after)
        return super().__call__(retry_state)
```

## Context manager (alternative au décorateur)

```python
from tenacity import Retrying, stop_after_attempt, wait_fixed

for attempt in Retrying(stop=stop_after_attempt(3), wait=wait_fixed(1)):
    with attempt:
        result = requests.get(url, timeout=10)
        result.raise_for_status()
```

Utile quand le décorateur n'est pas pratique (lambdas, méthodes dynamiques).

## Statistiques

```python
@retry(stop=stop_after_attempt(5), wait=wait_fixed(1), reraise=True)
def my_func():
    ...

my_func()
stats = my_func.statistics
# {
#   'start_time': 2282811.23,              # horloge monotone
#   'attempt_number': 3,                    # nombre de tentatives
#   'idle_for': 2.0,                        # secondes passées à dormir
#   'delay_since_first_attempt': 2.001      # temps total depuis la 1ère tentative
# }
```

Les stats sont **thread-local** — chaque thread a ses propres stats.

## Rate limits des APIs

| API         | Limite                    | Mécanisme | Header                   |
| ----------- | ------------------------- | --------- | ------------------------ |
| TMDB        | ~40 req/s (par IP)        | HTTP 429  | `Retry-After` (secondes) |
| TMDB images | 20 connexions simultanées | -         | -                        |
| TVDB        | Non documenté précisément | HTTP 429  | Probable `Retry-After`   |

## Gotchas

### 1. Thread safety

L'objet `Retrying` sous-jacent n'est **PAS thread-safe**. Si plusieurs threads appellent la même
fonction décorée, il peut y avoir des conflits d'état.

**Solution** : Pour du multi-threading, définir la fonction décorée dans chaque thread ou utiliser
`my_func.retry_with(stop=..., wait=...)()` pour créer des copies.

### 2. Le défaut retente à l'infini

`@retry` sans arguments = retry infini sans délai. **Toujours spécifier `stop` et `wait`.**

### 3. `retry_if_exception_type()` attrape TOUT

Le défaut est `Exception` — ça inclut `TypeError`, `ValueError`, `KeyError` qui sont des bugs,
pas des erreurs transitoires. **Toujours restreindre les types.**

### 4. `stop_after_delay` peut dépasser

Le check se fait avant le sleep, mais l'exécution + sleep peut dépasser `max_delay`.
Utiliser `stop_before_delay` pour un deadline strict.

### 5. Générateurs non supportés

tenacity ne supporte PAS les générateurs ni les générateurs async. Le décorateur wrappe
l'appel de la fonction, pas l'itération.

### 6. `reraise=False` encapsule les exceptions

Sans `reraise=True`, les clauses `except` doivent catcher `RetryError`, pas l'exception originale.
L'exception originale est accessible via `retry_error.last_attempt.exception()`.

## Comparaison avec les alternatives

| Aspect           | tenacity                                | backoff                | urllib3.Retry         |
| ---------------- | --------------------------------------- | ---------------------- | --------------------- |
| Version          | 9.1.4 (2026)                            | 2.2.1 (2022, **mort**) | Intégré urllib3       |
| Scope            | Toute fonction                          | Toute fonction         | HTTP uniquement       |
| Wait strategies  | 8+ composables                          | 3 (exp, fib, constant) | `backoff_factor` seul |
| Conditions retry | Exception, result, message, composables | Exception ou prédicat  | Status codes          |
| `Retry-After`    | `wait_exception` (natif)                | Non                    | Non                   |
| Stats            | Thread-local dict                       | Non                    | Non                   |
| Async            | asyncio, Trio, Tornado                  | asyncio uniquement     | Non                   |

**Verdict** : `backoff` est mort depuis 2022. `urllib3.Retry` est limité au transport HTTP.
tenacity est le standard communautaire, activement maintenu, avec les features les plus riches.
