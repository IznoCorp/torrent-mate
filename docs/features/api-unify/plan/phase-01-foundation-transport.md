# Phase 1 — Foundation: Contracts + Transport

**Type**: infra
**Goal**: Build the `api/` package skeleton, contracts, custom types, and the
`HttpTransport` consuming a `TransportPolicy`. This phase is the architectural
spine: every later phase depends on it.

## Gate (prereq)

`feat/api-unify` branch exists. `docs/features/api-unify/DESIGN.md` v2 present. No prior `api/` directory.

## Sub-phases

### 1.1 — `api/_contracts.py` + `api/__init__.py`

Create:

- `personalscraper/api/__init__.py` (empty re-export-free).
- `personalscraper/api/_contracts.py` — `AuthMode`, `ApiError`, `CircuitOpenError` (from DESIGN §3.1).

`ApiError` is a `@dataclass` Exception. `CircuitOpenError(provider, remaining_seconds)`.

**Commit**: `feat(api-unify): add api package with shared contracts`

### 1.2 — `api/_units.py` — ByteSize

Implement `ByteSize` per DESIGN §3.2. Tests in `tests/unit/test_api_units.py`:

- `parse(1024)` → 1024 bytes.
- `parse("1GB")` → 1_000_000_000 bytes.
- `parse("1GiB")` → 1_073_741_824 bytes.
- `parse("500MiB")` → 524_288_000 bytes.
- Comparison: `ByteSize.parse("1GB") > ByteSize.parse("999MB")` is True.
- `parse("not-a-size")` raises `ValueError`.
- Idempotence: `ByteSize.parse(ByteSize(1024)) == ByteSize(1024)`.

**Commit**: `feat(api-unify): add ByteSize custom type`

### 1.3 — `api/transport/_policy.py` — TransportPolicy contract

Implement DESIGN §3.3 verbatim:

- `RetryPolicy` (frozen dataclass) — `max_attempts`, `initial_wait`, `max_wait`, `retryable_statuses`.
- `CircuitPolicy` (frozen dataclass) — `failure_threshold`, `cooldown_seconds`, `count_retries: bool = False`.
- `RateLimitPolicy` (frozen dataclass) — `requests_per_second: float = 0.0`.
- `AuthMethod` Protocol with `apply(session)` AND `auth_params() -> dict[str, str]`.
- `TransportPolicy` (mutable dataclass) — `provider_name`, `base_url`, `auth`, `timeout_seconds`, `retry`, `circuit`, `rate_limit`, `extra_headers`, `response_format: Literal["json"] = "json"` (extended to `"xml"` in Phase 20 and `"text"` in Phase 24).

No imports from concrete providers (foundation must stay decoupled).

**Commit**: `feat(api-unify): add TransportPolicy contract`

### 1.4 — `api/transport/_auth.py`

Implement `BearerAuth`, `ApiKeyAuth` (with `location="header"|"query"`), `LoginAuth`, `NoAuth` per DESIGN §3.4.

**Critical**: every class implements `auth_params()` even when returning `{}`. This is enforced by the Protocol.

Unit tests in `tests/unit/test_api_auth.py`:

- `BearerAuth.apply()` sets `Authorization: Bearer <token>`. `auth_params() == {}`.
- `ApiKeyAuth(location="query")` does not mutate session. `auth_params() == {"api_key": "..."}`.
- `ApiKeyAuth(location="header", param="trakt-api-key")` mutates session header. `auth_params() == {}`.
- `LoginAuth.apply()` sets `session.auth` tuple.
- `NoAuth` is a no-op for both `apply()` and `auth_params()`.

**Commit**: `feat(api-unify): add AuthMethod implementations`

### 1.5 — `api/transport/_rate.py` — RateLimiter

Token-bucket. `requests_per_second=0` → no-op `acquire()`. Thread-safe with a `Lock`.

Unit test: rate-limited at 10 rps, 20 calls take ≥ 1.9s (allow some jitter).

**Commit**: `feat(api-unify): add RateLimiter token-bucket`

### 1.6 — `api/transport/_circuit.py`

`git mv personalscraper/scraper/circuit_breaker.py personalscraper/api/transport/_circuit.py`.

Update `_is_circuit_error` per DESIGN §3.5 — drop `TMDBError`/`TVDBError` references, add `ApiError` branch.

Update `CircuitOpenError` import: it now lives in `api/_contracts.py`. Replace any inline class definition in `_circuit.py` with `from personalscraper.api._contracts import CircuitOpenError`.

Grep for existing importers and rewrite them:

```bash
rg "from personalscraper.scraper.circuit_breaker import" personalscraper/ --files-with-matches
rg "from personalscraper.scraper import circuit_breaker" personalscraper/ --files-with-matches
```

All importers update to `from personalscraper.api.transport._circuit import CircuitBreaker, CircuitState`. `CircuitOpenError` consumers re-import from `personalscraper.api._contracts`.

Existing circuit-breaker tests: update import paths in same commit.

**Commit**: `refactor(api-unify): move circuit breaker to api/transport/_circuit.py`

### 1.7 — `api/transport/_http.py` — HttpTransport

Implement DESIGN §3.7. Key invariants:

- Constructor takes a single `policy: TransportPolicy` argument.
- `Accept: application/json` set by default; `policy.extra_headers` overlaid.
- Tenacity built dynamically from `policy.retry`:

```python
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

def _build_retry(policy: TransportPolicy):
    return retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential_jitter(initial=policy.retry.initial_wait,
                                     max=policy.retry.max_wait,
                                     jitter=0.5),
        stop=stop_after_attempt(policy.retry.max_attempts),
        reraise=True,
    )
```

- `_request_outer` wraps `_tenacity_retry`. Circuit breaker:
  - `count_retries=False`: outer try/except records failure once after retries exhaust.
  - `count_retries=True`: each `_do_request` failure records inside the tenacity loop.
- `_do_request` merges `policy.auth.auth_params()` with caller params **before** every request.
- On non-2xx, raise `ApiError` populated from response JSON if available, else from `resp.reason`.
- `_do_request` body parsing branches on `policy.response_format`: `"json"` → `resp.json()`. Future formats (`"xml"`, `"text"`) added in Phase 20/24 with their own branches.
- `HttpTransport` implements `__enter__` / `__exit__` and calls `close()` on exit. Bootstrap flows (TVDB login, pre-checks) may use `with HttpTransport(policy) as transport:`.
- No `get_raw()` (YAGNI — DESIGN §1.2).
- No `objects_pairs_hook` typo. Use `resp.json()` default.

Delete `scraper/http_retry.py`. Grep importers, rewrite:

```bash
rg "from personalscraper.scraper.http_retry import" personalscraper/ --files-with-matches
```

`scraper/http_retry.py` exposes utility functions used by `tmdb_client.py` and `tvdb_client.py`. Those imports stay in the OLD modules (which still exist) until Phase 5/7 migrations replace the entire client. **Therefore**: this sub-phase keeps `http_retry.py` for now and DOES NOT delete it. Deletion happens in Phase 5 (TMDB migration is the last consumer's first move).

**Wait** — that creates a cross-phase orphan. Better approach: leave `http_retry.py` in place but route the new `HttpTransport` independently. `tmdb_client.py` and `tvdb_client.py` still use `http_retry.py` until they're replaced (Phases 5, 7). Delete `http_retry.py` in Phase 7 (after TVDB).

**Adjust**: `scraper/http_retry.py` deletion is moved to Phase 7 (the last legacy consumer disappears there). This phase only adds `_http.py` without touching the legacy file.

**Commit**: `feat(api-unify): add HttpTransport consuming TransportPolicy`

### 1.8 — `scripts/check-typed-api.py` (new guardrail)

Tiny script (~30 LOC) — greps for `dict[str, Any]` in `personalscraper/api/` non-`_*.py` files (public modules). Exits non-zero on hit. Wired into `make check`.

```python
#!/usr/bin/env python3
"""Forbid dict[str, Any] in public api/ surface."""
from pathlib import Path
import re, sys

ROOT = Path(__file__).parent.parent / "personalscraper" / "api"
PATTERN = re.compile(r"dict\[\s*str\s*,\s*Any\s*\]")
violations = []
for py in ROOT.rglob("*.py"):
    if py.name.startswith("_") or py.parent.name.startswith("_"):
        continue
    for i, line in enumerate(py.read_text().splitlines(), 1):
        if PATTERN.search(line) and not line.lstrip().startswith("#"):
            violations.append(f"{py}:{i}: {line.strip()}")
if violations:
    print("dict[str, Any] forbidden in api/ public surface:", file=sys.stderr)
    for v in violations:
        print(f"  {v}", file=sys.stderr)
    sys.exit(1)
```

Add to Makefile `check` target.

**Commit**: `chore(api-unify): add check-typed-api guardrail`

### 1.9 — Reference integration test

Create `tests/integration/test_transport_policy.py` — single test using a fake `responses` mock:

- Builds a `TransportPolicy` with `ApiKeyAuth(location="query")`, `RetryPolicy(max_attempts=3)`, `CircuitPolicy(failure_threshold=2, count_retries=False)`.
- Verifies query auth param is sent on every request.
- Verifies retry attempts on 503 then success on 3rd call (within max_attempts).
- Verifies circuit opens after 2 final failures (NOT 2 attempts inside one call).

**Commit**: `test(api-unify): add TransportPolicy reference integration test`

### 1.10 — Phase 1 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api._contracts import ApiError, CircuitOpenError"
python -c "from personalscraper.api._units import ByteSize; assert ByteSize.parse('1GB').bytes == 1_000_000_000"
python -c "from personalscraper.api.transport._http import HttpTransport"
python -c "from personalscraper.api.transport._policy import TransportPolicy, RetryPolicy, CircuitPolicy, RateLimitPolicy, AuthMethod"
python -c "from personalscraper.api.transport._auth import BearerAuth, ApiKeyAuth, LoginAuth, NoAuth"
! rg "from personalscraper.scraper.circuit_breaker" personalscraper/ tests/
```

**Commit**: `chore(api-unify): phase 1 gate — foundation + transport done`
