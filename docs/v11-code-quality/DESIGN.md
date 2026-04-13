# V11 — CODE QUALITY HARDENING — Design Spec

> Fix 4 architectural issues identified by comprehensive code review that were
> too structural to auto-fix: error isolation, CLI UX, dead code removal, and
> DRY extraction.

## Scope

4 focused phases, each independently testable and committable.
No new features — strictly quality improvements to existing code.

## Phase 1: Ingest per-torrent error isolation

### Problem

`personalscraper/ingest/ingest.py` lines 203-312: a single `except Exception`
wraps ~85 lines covering qBit session, torrent loop, tracker, disk checks, and
file transfers. One failure aborts ALL remaining torrents. Error classification
uses fragile `type(e).__name__` string matching.

### Design

Split into two error-handling levels:

**Outer level** — around `with client:` — catches only session/connection errors:

```python
except (
    qbittorrentapi.LoginFailed,
    qbittorrentapi.APIConnectionError,
    QBitAuthLockoutError,
    requests.ConnectionError,
) as e:
```

Each exception type has its own actionable message. No more string heuristics.

**Inner level** — inside `for torrent in torrents:` — isolates each torrent:

```python
for torrent in torrents:
    try:
        # ... process single torrent (resolve path, check space, transfer)
    except Exception as exc:
        log.error("torrent_failed", name=name, error=str(exc), exc_info=True)
        report.error_count += 1
        report.details.append(f"{name}: {exc}")
        continue
```

The inner `except Exception` is acceptable here: it is an isolation boundary
whose purpose is to ensure one torrent failure does not block the rest.

### Files modified

- `personalscraper/ingest/ingest.py` — restructure `run_ingest()`

### Tests

- Mock a batch of 3 torrents where the 2nd raises `OSError` during transfer.
  Assert: torrent 1 and 3 are processed, torrent 2 is reported as error.
- Mock `QBitClient` raising `LoginFailed` → assert actionable message in report.
- Mock `QBitClient` raising `APIConnectionError` → assert actionable message.
- Verify existing ingest tests still pass.

## Phase 2: CLI config error decorator

### Problem

`personalscraper/cli.py`: `get_settings()` can raise pydantic `ValidationError`
with raw technical tracebacks. `acquire_lock()` calls `get_settings()` indirectly
via `_default_lock_file()`, so config errors crash before the try block. The user
sees `pydantic_core._pydantic_core.ValidationError: 1 validation error...` instead
of a clear message.

### Design

A decorator `@handle_cli_errors` applied to all 7 CLI commands:

```python
import functools
from pydantic import ValidationError

def handle_cli_errors(func):
    """Catch configuration and file errors, display user-friendly messages."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            console.print(f"[red]Configuration error:[/red] {_format_validation(exc)}")
            raise typer.Exit(1)
        except FileNotFoundError as exc:
            console.print(f"[red]Missing file:[/red] {exc}")
            raise typer.Exit(1)
    return wrapper
```

Helper `_format_validation(exc: ValidationError) -> str`: extracts field names
and error messages from pydantic's structured errors, formats as one-liner:
`"QBIT_HOST: field required; QBIT_PORT: value is not a valid integer"`.

The decorator covers `get_settings()` called from any point inside the command
(including indirectly via `acquire_lock() → _default_lock_file()`), because the
entire command body runs inside the decorator's try block.

### Files modified

- `personalscraper/cli.py` — add `handle_cli_errors` decorator, `_format_validation`
  helper, apply decorator to all 7 commands

### Tests

- Mock `.env` with invalid `QBIT_PORT=abc` → invoke CLI command via `CliRunner`
  → assert output contains "Configuration error" and exit code 1.
- Mock missing `.env` entirely → assert user-friendly message.
- Verify existing CLI tests still pass.

## Phase 3: Remove dead `TMDBClient.select_best_image`

### Problem

`personalscraper/scraper/tmdb_client.py` line 397: `select_best_image()` method
is identical to `artwork.select_best_image()` but has **zero callers**. It is
NOT part of the `ScraperProvider` Protocol (unlike `get_artwork_urls()` which
IS a Protocol method and must be kept).

### Design

1. Delete `TMDBClient.select_best_image()` method only
2. Keep `TMDBClient.get_artwork_urls()` — it implements the `ScraperProvider`
   Protocol and has conformance tests
3. Delete the `lang_priority` local dict inside `select_best_image` (duplicate
   of `_LANG_PRIORITY` in `artwork.py`)
4. The `_LANG_PRIORITY` dict and `select_best_image()` in `artwork.py` remain
   as the single source of truth (already used by `ArtworkDownloader`)

### Files modified

- `personalscraper/scraper/tmdb_client.py` — remove `select_best_image()` only

### Tests

- Run full test suite to confirm no test references the removed methods.
- If tests exist for these methods, delete them (testing dead code is waste).

## Phase 4: Extract shared `_is_retryable` via factory

### Problem

Three near-identical `_is_retryable()` functions in `tmdb_client.py`,
`tvdb_client.py`, and `artwork.py`. Same retry logic (429 + 5xx + network
errors), only difference is the provider-specific error type.

### Design

New module `personalscraper/scraper/http_retry.py`:

```python
"""Shared HTTP retry predicates for tenacity.

Provides a factory to create retry predicates that handle provider-specific
errors (TMDBError, TVDBError) alongside standard requests exceptions.
"""

import requests

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def make_retryable_predicate(*provider_error_types: type) -> callable:
    """Create a retry predicate for tenacity.

    Retries on:
    - Provider-specific errors with http_status in {429, 500-504}
    - requests.HTTPError with status in {429, 500-504}
    - Connection errors and timeouts

    Does NOT retry on 4xx client errors (401, 403, 404).

    Args:
        *provider_error_types: Exception classes with an http_status attribute
            (e.g., TMDBError, TVDBError).

    Returns:
        A callable(BaseException) -> bool for retry_if_exception().
    """
    def _is_retryable(exc: BaseException) -> bool:
        for err_type in provider_error_types:
            if isinstance(exc, err_type):
                return exc.http_status in _RETRYABLE_STATUS_CODES
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            return exc.response.status_code in _RETRYABLE_STATUS_CODES
        return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
    return _is_retryable
```

Usage in each file (variable name stays the same — decorators unchanged):

```python
# tmdb_client.py
from personalscraper.scraper.http_retry import make_retryable_predicate
_is_retryable = make_retryable_predicate(TMDBError)

# tvdb_client.py
from personalscraper.scraper.http_retry import make_retryable_predicate
_is_retryable = make_retryable_predicate(TVDBError)

# artwork.py (no provider error type)
from personalscraper.scraper.http_retry import make_retryable_predicate
_is_retryable = make_retryable_predicate()
```

No import cycle risk: `http_retry.py` imports only `requests`. Provider error
types are passed as arguments at module level, not imported by `http_retry.py`.

### Files modified

- `personalscraper/scraper/http_retry.py` — new module
- `personalscraper/scraper/tmdb_client.py` — replace local `_is_retryable`
- `personalscraper/scraper/tvdb_client.py` — replace local `_is_retryable`
- `personalscraper/scraper/artwork.py` — replace local `_is_retryable`

### Tests

- Unit tests for `make_retryable_predicate()`:
  - With TMDBError(status=429) → True
  - With TMDBError(status=404) → False
  - With ConnectionError → True
  - With Timeout → True
  - With ValueError → False
  - Without provider types (artwork config) → test HTTPError 500 → True
- Run full test suite to verify no regressions.

## Acceptance Criteria

V11 is complete when:

1. A torrent that crashes does not prevent processing of remaining torrents
2. A `.env` config error produces a user-friendly message, not a pydantic traceback
3. `TMDBClient.select_best_image` and `TMDBClient.get_artwork_urls` no longer exist
4. A single `make_retryable_predicate()` in `http_retry.py` replaces 3 copies
5. All tests pass (994+), zero regressions
6. Each phase has its own tests validating the fix

## Phase Dependencies

Phases are independent — no cross-dependencies. They can be implemented in any
order. The proposed order (1→2→3→4) goes from highest impact to lowest.

## Commit Convention

Format: `v11.{phase}.{sub}: Description`

- Phase 1: v11.1.x
- Phase 2: v11.2.x
- Phase 3: v11.3.x
- Phase 4: v11.4.x
