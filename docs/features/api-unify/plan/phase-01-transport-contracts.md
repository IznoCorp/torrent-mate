# Phase 1 — Transport + Contracts

## Gate

**Prerequisites**: `feat/api-unify` branch exists, `docs/features/api-unify/DESIGN.md` present.

**Input from previous phase**: none (first phase).

## Goal

Create the `api/` package foundation: shared HTTP transport, auth methods, rate limiter, circuit breaker, and contract types. Move existing `scraper/circuit_breaker.py` and integrate `scraper/http_retry.py`.

## Sub-phases

### 1.1 — Create `api/` package + `_contracts.py`

**Files to create**:

- `personalscraper/api/__init__.py`
- `personalscraper/api/_contracts.py`

`_contracts.py` contains `ApiError`, `CircuitOpenError`, `AuthMode`:

```python
"""Shared types for the api/ package."""
from dataclasses import dataclass, field
from enum import Enum


class AuthMode(Enum):
    BEARER = "bearer"
    API_KEY = "api_key"
    LOGIN = "login"
    NONE = "none"


@dataclass
class ApiError(Exception):
    """Unified API error replacing provider-specific types (TMDBError, TVDBError)."""
    provider: str
    http_status: int
    provider_code: int = 0
    message: str = ""

    def __str__(self) -> str:
        return f"{self.provider} {self.http_status} (code {self.provider_code}): {self.message}"


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an OPEN circuit."""

    def __init__(self, provider: str, remaining_seconds: float) -> None:
        self.provider = provider
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit breaker OPEN for {provider} ({remaining_seconds:.0f}s remaining)"
        )
```

**Commit**: `feat(api-unify): add api/ package with shared contracts`

### 1.2 — Create `api/transport/` package

**Files to create**:

- `personalscraper/api/transport/__init__.py`
- `personalscraper/api/transport/_circuit.py` — moved from `scraper/circuit_breaker.py`

Move `scraper/circuit_breaker.py` to `api/transport/_circuit.py`. Replace all `from personalscraper.scraper.tmdb_client import TMDBError` and `from personalscraper.scraper.tvdb_client import TVDBError` in `_is_circuit_error` with `ApiError` checks:

```python
@staticmethod
def _is_circuit_error(exc: Exception) -> bool:
    from personalscraper.api._contracts import ApiError

    if isinstance(exc, ApiError):
        return exc.http_status >= 500

    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500

    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True

    return False
```

Update all imports of `CircuitBreaker`, `CircuitOpenError`, `CircuitState` in the codebase. `CircuitOpenError` is now in `api/_contracts.py` — update consumers to import from there.

Grep for existing importers:

```bash
rg "from personalscraper.scraper.circuit_breaker import" personalscraper/ --files-with-matches
rg "from personalscraper.scraper import circuit_breaker" personalscraper/ --files-with-matches
```

Delete `scraper/circuit_breaker.py`.

**Commit**: `refactor(api-unify): move circuit breaker to api/transport/_circuit.py`

### 1.3 — Create `api/transport/_auth.py`

Auth method Protocol + implementations:

```python
"""Authentication methods for API providers."""
from typing import Protocol
import requests


class AuthMethod(Protocol):
    """Protocol for applying authentication to an HTTP session."""
    def apply(self, session: requests.Session) -> None: ...


class BearerAuth:
    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, session: requests.Session) -> None:
        session.headers["Authorization"] = f"Bearer {self._token}"


class ApiKeyAuth:
    def __init__(self, key: str, param: str = "api_key", location: str = "query") -> None:
        self._key = key
        self._param = param
        self._location = location

    def apply(self, session: requests.Session) -> None:
        if self._location == "header":
            session.headers[self._param] = self._key
        # query auth handled per-request via params in HttpTransport


class LoginAuth:
    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def apply(self, session: requests.Session) -> None:
        session.auth = (self._username, self._password)


class NoAuth:
    def apply(self, session: requests.Session) -> None:
        pass
```

**Commit**: `feat(api-unify): add AuthMethod protocol and implementations`

### 1.4 — Create `api/transport/_rate.py`

Token-bucket rate limiter:

```python
"""Token-bucket rate limiter for API providers."""
import time
import threading


class RateLimiter:
    def __init__(self, requests_per_second: float = 0) -> None:
        self._rate = requests_per_second
        self._tokens = float(requests_per_second) if requests_per_second > 0 else float("inf")
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        if self._rate <= 0:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                time.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0
```

**Commit**: `feat(api-unify): add RateLimiter token-bucket`

### 1.5 — Create `api/transport/_http.py`

The shared `HttpTransport` class:

```python
"""Shared HTTP transport with retry, circuit breaker, and logging."""
from typing import Any
import time

import requests
from requests.adapters import HTTPAdapter
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)
from urllib3.util.retry import Retry as Urllib3Retry

from personalscraper.api._contracts import ApiError
from personalscraper.api.transport._auth import AuthMethod
from personalscraper.api.transport._circuit import CircuitBreaker
from personalscraper.api.transport._rate import RateLimiter
from personalscraper.logger import get_logger

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, ApiError):
        return exc.http_status in _RETRYABLE_STATUSES
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code in _RETRYABLE_STATUSES
    return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))


class HttpTransport:
    def __init__(
        self,
        provider_name: str,
        auth: AuthMethod,
        base_url: str,
        default_timeout: float = 10,
        circuit_threshold: int = 5,
        circuit_cooldown: float = 300,
        rate_limit_rps: float = 0,
    ) -> None:
        self._provider = provider_name
        self._base_url = base_url.rstrip("/")
        self._timeout = default_timeout
        self._log = get_logger(f"api.{provider_name.lower()}")

        # Transport-level retry (DNS/TCP/TLS)
        transport_retry = Urllib3Retry(total=2, backoff_factor=0.5, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=transport_retry)

        self._session = requests.Session()
        self._session.mount("https://", adapter)
        self._session.headers["Accept"] = "application/json"
        auth.apply(self._session)

        self._circuit = CircuitBreaker(
            name=provider_name,
            failure_threshold=circuit_threshold,
            cooldown_seconds=circuit_cooldown,
        )
        self._rate_limiter = RateLimiter(rate_limit_rps)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "HttpTransport":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential_jitter(initial=0.5, max=10, jitter=0.5),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _request(self, method: str, path: str, params: dict | None = None,
                 data: dict | None = None) -> dict[str, Any]:
        self._circuit.guard()
        self._rate_limiter.acquire()

        url = f"{self._base_url}{path}" if path else self._base_url
        start = time.monotonic()

        try:
            resp = self._session.request(
                method, url, params=params, json=data, timeout=self._timeout
            )
            duration = time.monotonic() - start
            self._log.debug("api_call", provider=self._provider, method=method,
                            path=path, status=resp.status_code, duration_ms=int(duration * 1000))

            if not resp.ok:
                try:
                    error_body = resp.json()
                except ValueError:
                    resp.raise_for_status()
                raise ApiError(
                    provider=self._provider,
                    http_status=resp.status_code,
                    provider_code=error_body.get("status_code", error_body.get("code", 0)),
                    message=error_body.get("status_message", error_body.get("message", resp.reason)),
                )

            self._circuit.record_success()
            return resp.json(objects_pairs_hook=dict)
        except ApiError:
            raise
        except Exception as exc:
            self._circuit.record_failure(exc)
            raise

    def get(self, path: str = "", params: dict | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(self, path: str = "", data: dict | None = None) -> dict[str, Any]:
        return self._request("POST", path, data=data)

    def get_raw(self, url: str) -> bytes:
        self._circuit.guard()
        self._rate_limiter.acquire()
        resp = self._session.get(url, timeout=self._timeout)
        resp.raise_for_status()
        self._circuit.record_success()
        return resp.content

    @property
    def circuit(self) -> CircuitBreaker:
        return self._circuit
```

Delete `scraper/http_retry.py`. Update all consumers:

```bash
rg "from personalscraper.scraper.http_retry import" personalscraper/ --files-with-matches
```

**Commit**: `feat(api-unify): add HttpTransport with retry, circuit, rate-limit`

### 1.6 — Phase 1 gate

Run quality gate:

```bash
make check && python3 scripts/check-module-size.py
```

Verify `python -c "from personalscraper.api._contracts import ApiError, CircuitOpenError; from personalscraper.api.transport._http import HttpTransport"` succeeds.

Verify existing circuit breaker tests still pass (update import paths in test files):

```bash
python -m pytest tests/ -k "circuit" -v
```

**Commit**: `chore(api-unify): phase 1 gate — transport + contracts done`
