# V8 — ROBUSTNESS : Design

> Durcissement du pipeline : circuit breaker API, anti-faux-positifs fuzzy, rollback dispatch, fallback disque, timeout E2E.

## Architecture

### Fichiers modifiés

```
personalscraper/
├── scraper/
│   ├── circuit_breaker.py     # NOUVEAU — CircuitBreaker classe générique
│   ├── tmdb_client.py         # MODIFIÉ — intégrer CircuitBreaker
│   └── tvdb_client.py         # MODIFIÉ — intégrer CircuitBreaker
├── dispatch/
│   ├── dispatcher.py          # MODIFIÉ — rollback transactionnel + fallback disk full (existants)
│   ├── disk_scanner.py        # MODIFIÉ — fallback catégorie + auto-create
│   └── media_index.py         # MODIFIÉ — anti-faux-positifs fuzzy matching
├── sorter/
│   └── matcher.py             # MODIFIÉ — anti-faux-positifs (cohérence avec media_index)
├── config.py                  # MODIFIÉ — nouveaux settings (circuit breaker, timeout)
tests/
├── e2e/
│   └── setup_torrents.py      # MODIFIÉ — timeout dynamique
├── scraper/
│   └── test_circuit_breaker.py # NOUVEAU — tests CircuitBreaker
├── dispatch/
│   ├── test_dispatcher.py     # MODIFIÉ — tests rollback + fallback
│   ├── test_disk_scanner.py   # MODIFIÉ — tests auto-create catégorie
│   └── test_media_index.py    # MODIFIÉ — tests anti-faux-positifs
├── sorter/
│   └── test_matcher.py        # MODIFIÉ — tests anti-faux-positifs
└── e2e/
    └── test_setup_torrents.py # MODIFIÉ — tests timeout
```

### Dépendances

Aucune nouvelle dépendance externe. Le circuit breaker est implémenté en interne (pas pybreaker).

## Interfaces

### 1. CircuitBreaker (`scraper/circuit_breaker.py`)

```python
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Cooldown period
    HALF_OPEN = "half_open"    # Testing after cooldown


class CircuitBreaker:
    """Generic circuit breaker for API providers.

    States:
    - CLOSED: Normal operation, counts consecutive errors
    - OPEN: Provider down, all calls raise CircuitOpenError
    - HALF_OPEN: After cooldown, allows one test call

    Attributes:
        name: Provider name (for logging).
        failure_threshold: Consecutive errors before opening.
        cooldown_seconds: Wait time before half-open.
        state: Current circuit state.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        cooldown_seconds: float = 300.0,
    ) -> None: ...

    @property
    def state(self) -> CircuitState: ...

    def record_success(self) -> None:
        """Record a successful call. Resets error count and closes circuit."""

    def record_failure(self, exc: Exception) -> None:
        """Record a failed call. Opens circuit if threshold reached.

        Only counts 5xx, Timeout, ConnectionError.
        Does NOT count 429 (handled by tenacity) or 4xx (client errors).

        Args:
            exc: The exception that caused the failure.
        """

    def can_proceed(self) -> bool:
        """Check if a call is allowed.

        Returns:
            True if CLOSED or HALF_OPEN (after cooldown elapsed).
            False if OPEN (cooldown not yet elapsed).
        """

    def reset(self) -> None:
        """Reset to CLOSED state (for testing)."""


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an OPEN circuit.

    Attributes:
        provider: Provider name.
        remaining_seconds: Seconds until cooldown expires.
    """
```

### 2. TMDBClient modifications (`scraper/tmdb_client.py`)

```python
class TMDBClient:
    def __init__(self, api_key: str, language: str = "fr-FR") -> None:
        # ... existing init ...
        self._circuit = CircuitBreaker(name="TMDB")

    @retry(...)
    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        # ADDED: Check circuit before call
        if not self._circuit.can_proceed():
            raise CircuitOpenError("TMDB", self._circuit._remaining_cooldown())
        try:
            resp = ...  # existing logic
            self._circuit.record_success()
            return resp.json()
        except (TMDBError, ConnectionError, Timeout) as e:
            self._circuit.record_failure(e)
            raise

    @property
    def circuit(self) -> CircuitBreaker:
        """Expose circuit breaker for scraper fallback logic."""
        return self._circuit
```

### 3. TVDBClient modifications (`scraper/tvdb_client.py`)

Same pattern as TMDBClient — add `self._circuit = CircuitBreaker(name="TVDB")`.

### 4. Scraper fallback logic (`scraper/scraper.py`)

```python
# In Scraper.process_movies() / process_tvshows():
# When CircuitOpenError is caught:
#   1. If primary provider (TMDB for movies) is down → try TVDB
#   2. If both down → skip item with warning
# The circuit breaker handles cooldown/half-open automatically
```

### 5. Anti-faux-positifs fuzzy matching

#### MediaIndex.find() (`dispatch/media_index.py`)

```python
def find(self, name: str, media_type: str) -> IndexEntry | None:
    """Find with anti-false-positive guards.

    Guards:
    1. Year constraint: ±1 year tolerance (if both have years)
    2. Length ratio: len(shorter) / len(longer) >= 0.67 (ratio ≤ 1.5x)
    3. Adaptive threshold: ≤10 chars → 95%, >10 chars → 90%
    """
```

#### find_matching_directory() (`sorter/matcher.py`)

```python
def find_matching_directory(
    name: str,
    candidates: list[Path],
    respect_year: bool = True,
    threshold: float = 85.0,  # kept for backward compat but overridden internally
) -> Path | None:
    """Find with anti-false-positive guards.

    Same guards as MediaIndex.find() for consistency:
    1. Year constraint: already exists (respect_year), tighten to ±1 an
    2. Length ratio: add len constraint
    3. Adaptive threshold: override the fixed threshold
    """
```

#### Shared guard function (`text_utils.py`)

```python
def fuzzy_match_score(
    query: str,
    candidate: str,
    query_year: int | None = None,
    candidate_year: int | None = None,
) -> float | None:
    """Score a fuzzy match with anti-false-positive guards.

    Returns the WRatio score if all guards pass, None otherwise.

    Guards applied:
    1. Year: if both present, abs(diff) <= 1
    2. Length ratio: len(shorter)/len(longer) >= 0.67
    3. Adaptive threshold: processed_len <= 10 → 95, else → 90

    Args:
        query: Search term (processed via media_processor).
        candidate: Candidate to compare (processed via media_processor).
        query_year: Year extracted from query (optional).
        candidate_year: Year extracted from candidate (optional).

    Returns:
        WRatio score if all guards pass, None if rejected.
    """
```

### 6. Dispatch rollback (`dispatch/dispatcher.py`)

```python
class Dispatcher:
    def _move_new(self, source: Path, dest: Path) -> bool:
        """Move new item with staging→commit pattern.

        CHANGED: Previously wrote directly to dest.
        NOW: rsync → _tmp_dispatch_{name}, then atomic rename.

        1. rsync source → dest.parent / _tmp_dispatch_{name}
        2. Success → os.rename(tmp, dest)
        3. Failure → shutil.rmtree(tmp), return False
        """

    def _merge(self, source: Path, dest: Path) -> bool:
        """Merge TV show episodes into existing directory.

        CHANGED: Merge is inherently non-atomic (adding files to existing dir).
        Rollback strategy: rsync with --backup to preserve originals.
        On failure: restore from backups.

        Note: _replace() already has staging→commit pattern — no change needed.
        """
```

### 7. Disk fallback (`dispatch/disk_scanner.py`)

```python
def choose_disk(
    disks: list[DiskStatus],
    category: str,
    min_free_gb: float,
    item_size_gb: float = 0,
    allow_create_category: bool = False,
) -> DiskStatus | None:
    """Choose best disk with fallback.

    CHANGED: New parameter allow_create_category.

    Strategy:
    1. First pass: disks that have the category AND enough space
    2. If none found AND allow_create_category=True:
       Second pass: any mounted disk with enough space (most free wins)
    3. If still none: return None

    The category directory is NOT created here — just the disk is chosen.
    The caller (dispatcher) creates the directory.

    Args:
        disks: List of disk statuses.
        category: Media category.
        min_free_gb: Minimum free space.
        item_size_gb: Item size.
        allow_create_category: Allow choosing a disk without the category.

    Returns:
        Best DiskStatus, or None if no disk qualifies.
    """
```

Dispatcher usage:

```python
# In dispatch_movie / dispatch_tvshow:
if existing:
    # Replace/merge: DO NOT use allow_create_category
    # If disk is full → skip with log
else:
    # New item: allow_create_category=True
    target = choose_disk(..., allow_create_category=True)
    if target:
        dest = target.config.path / category / item.name
        dest.parent.mkdir(parents=True, exist_ok=True)  # create category dir if needed
```

### 8. Timeout dynamique E2E (`tests/e2e/setup_torrents.py`)

```python
class TorrentSetup:
    def wait_for_completion(self, hashes: list[str]) -> None:
        """Wait for torrents with dynamic timeout.

        CHANGED: Added ceil(GB) × 3 min timeout.

        Timeout formula:
        - Get total size from qBit API: sum(t.total_size for t in torrents)
        - timeout_minutes = max(ceil(total_gb) * 3, 10)  # minimum 10 min
        - If elapsed > timeout → raise TimeoutError

        Args:
            hashes: Info hashes to monitor.

        Raises:
            TimeoutError: If download exceeds the dynamic timeout.
        """
```

## Flux de données détaillé

```
                ┌────────────────────────────────────────────┐
                │              V3 SCRAPE                      │
                │                                             │
                │  TMDBClient._get()                          │
                │    ├─ tenacity retry (429/5xx, 4 attempts)  │
                │    └─ CircuitBreaker                        │
                │        ├─ record_success() → reset counter  │
                │        ├─ record_failure() → increment      │
                │        │   5 failures → OPEN (5min cooldown)│
                │        └─ can_proceed() → check state       │
                │                                             │
                │  Scraper.process_*()                        │
                │    ├─ Try primary provider                  │
                │    ├─ CircuitOpenError → try fallback        │
                │    └─ Both down → skip + log warning        │
                └────────────────────────────────────────────┘
                                    │
                ┌────────────────────────────────────────────┐
                │              V5 DISPATCH                    │
                │                                             │
                │  MediaIndex.find()                          │
                │    ├─ Exact lookup (unchanged)              │
                │    └─ Fuzzy: fuzzy_match_score()            │
                │        ├─ Year guard: ±1 an                 │
                │        ├─ Length guard: ratio ≤ 1.5x        │
                │        └─ Adaptive threshold: 90% / 95%    │
                │                                             │
                │  Dispatcher.dispatch_*()                    │
                │    ├─ existing → replace/merge on SAME disk │
                │    │   └─ disk full → SKIP (not fallback)   │
                │    └─ new → choose_disk(allow_create=True)  │
                │        ├─ disk with category + space → use  │
                │        └─ no disk has category →            │
                │            disk with most space + mkdir     │
                │                                             │
                │  _move_new() / _replace()                   │
                │    ├─ rsync → _tmp_dispatch_{name}          │
                │    ├─ success → os.rename(tmp, dest)        │
                │    └─ failure → shutil.rmtree(tmp)          │
                └────────────────────────────────────────────┘
```

## Configuration

### Nouveaux settings (config.py)

```python
# Circuit breaker (optional, sensible defaults)
circuit_breaker_threshold: int = 5
circuit_breaker_cooldown: int = 300  # seconds
```

### Pas de nouveau .env

Les settings utilisent des valeurs par défaut. Pas besoin de modifier `.env.example` sauf pour documenter les nouvelles options.

## Gestion d'erreurs

| Situation                                            | Comportement                                             |
| ---------------------------------------------------- | -------------------------------------------------------- |
| TMDB 5xx × 5 consécutifs                             | Circuit OPEN → cooldown 5 min → HALF_OPEN → retry 1 call |
| TMDB + TVDB tous deux down                           | Skip items restants, log warning, pipeline continue      |
| TMDB 429 (rate limit)                                | Géré par tenacity (existant) — PAS le circuit breaker    |
| Fuzzy match "Matrix" vs "Matrix Reloaded"            | Rejeté par length guard (ratio 0.46 < 0.67)              |
| Fuzzy match "Alien" vs "Aliens"                      | Rejeté par adaptive threshold (5 chars → seuil 95%)      |
| rsync crash mid-transfer (\_move_new)                | Supprimer _tmp_dispatch_\*, skip item, log error         |
| rsync crash mid-transfer (\_replace)                 | Déjà géré (restaurer depuis dest.old.tmp)                |
| Disk plein pour replace/merge                        | Skip + log warning (pas de déplacement inter-disque)     |
| Disk plein pour new item + catégorie existe ailleurs | Créer catégorie sur disque le moins plein                |
| Aucun disque n'a la catégorie (new item)             | Créer catégorie sur disque le moins plein                |
| Torrent E2E dépasse timeout                          | TimeoutError avec détails (taille, temps)                |

## Sécurité

- Le circuit breaker ne leak pas de credentials (seul le nom du provider est loggé)
- Le rollback dispatch ne supprime que les dossiers `_tmp_dispatch_*` créés par le pipeline
- L'auto-create catégorie ne crée que des dossiers dans les répertoires medias connus (Disk1-4/medias/)
- Le timeout E2E n'affecte pas le pipeline production
