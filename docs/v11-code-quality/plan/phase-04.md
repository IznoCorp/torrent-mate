# Phase 4: Extract Shared `_is_retryable` via Factory

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace 3 near-identical `_is_retryable()` functions with a single `make_retryable_predicate()` factory in a shared module.

**Architecture:** New module `personalscraper/scraper/http_retry.py` with a factory function. Each client calls it at module level to create its `_is_retryable` — existing `@retry` decorators unchanged.

**Tech Stack:** Python, tenacity, requests, pytest

---

## Task 1: Write failing tests for the shared predicate factory

**Files:**

- Create: `tests/scraper/test_http_retry.py`

- [ ] **Step 1: Create test file**

Create `tests/scraper/test_http_retry.py`:

```python
"""Tests for personalscraper.scraper.http_retry — shared retry predicates."""

import requests
import requests.exceptions

from personalscraper.scraper.http_retry import make_retryable_predicate


class _FakeProviderError(Exception):
    """Fake provider error with http_status for testing."""

    def __init__(self, http_status: int) -> None:
        self.http_status = http_status
        super().__init__(f"HTTP {http_status}")


class TestMakeRetryablePredicate:
    """Tests for make_retryable_predicate factory."""

    def test_provider_error_429_is_retryable(self) -> None:
        """Provider error with 429 (rate limit) should be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(429)) is True

    def test_provider_error_500_is_retryable(self) -> None:
        """Provider error with 500 (server error) should be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(500)) is True

    def test_provider_error_502_is_retryable(self) -> None:
        """Provider error with 502 (bad gateway) should be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(502)) is True

    def test_provider_error_404_not_retryable(self) -> None:
        """Provider error with 404 (not found) should NOT be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(404)) is False

    def test_provider_error_401_not_retryable(self) -> None:
        """Provider error with 401 (unauthorized) should NOT be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(_FakeProviderError(401)) is False

    def test_connection_error_is_retryable(self) -> None:
        """requests.ConnectionError should always be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(requests.exceptions.ConnectionError()) is True

    def test_timeout_is_retryable(self) -> None:
        """requests.Timeout should always be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(requests.exceptions.Timeout()) is True

    def test_value_error_not_retryable(self) -> None:
        """ValueError (non-HTTP error) should NOT be retryable."""
        predicate = make_retryable_predicate(_FakeProviderError)
        assert predicate(ValueError("oops")) is False

    def test_no_provider_types_connection_error(self) -> None:
        """Without provider types (artwork config), ConnectionError is retryable."""
        predicate = make_retryable_predicate()
        assert predicate(requests.exceptions.ConnectionError()) is True

    def test_no_provider_types_timeout(self) -> None:
        """Without provider types (artwork config), Timeout is retryable."""
        predicate = make_retryable_predicate()
        assert predicate(requests.exceptions.Timeout()) is True

    def test_no_provider_types_value_error(self) -> None:
        """Without provider types, ValueError is NOT retryable."""
        predicate = make_retryable_predicate()
        assert predicate(ValueError("oops")) is False

    def test_http_error_500_is_retryable(self) -> None:
        """requests.HTTPError with 500 response should be retryable."""
        predicate = make_retryable_predicate()
        response = requests.models.Response()
        response.status_code = 500
        exc = requests.exceptions.HTTPError(response=response)
        assert predicate(exc) is True

    def test_http_error_404_not_retryable(self) -> None:
        """requests.HTTPError with 404 response should NOT be retryable."""
        predicate = make_retryable_predicate()
        response = requests.models.Response()
        response.status_code = 404
        exc = requests.exceptions.HTTPError(response=response)
        assert predicate(exc) is False

    def test_multiple_provider_types(self) -> None:
        """Factory should accept multiple provider error types."""

        class _AnotherError(Exception):
            def __init__(self, http_status: int) -> None:
                self.http_status = http_status

        predicate = make_retryable_predicate(_FakeProviderError, _AnotherError)
        assert predicate(_FakeProviderError(503)) is True
        assert predicate(_AnotherError(504)) is True
        assert predicate(_AnotherError(403)) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/scraper/test_http_retry.py -v`

Expected: FAIL — `ImportError: cannot import name 'make_retryable_predicate' from 'personalscraper.scraper.http_retry'` (module does not exist yet).

- [ ] **Step 3: Commit test file**

```bash
git add tests/scraper/test_http_retry.py
git commit -m "v11.4.1: Add failing tests for shared retry predicate factory"
```

## Task 2: Create http_retry.py module

**Files:**

- Create: `personalscraper/scraper/http_retry.py`

- [ ] **Step 1: Create the module**

Create `personalscraper/scraper/http_retry.py`:

```python
"""Shared HTTP retry predicates for tenacity.

Provides a factory to create retry predicates that handle provider-specific
errors (TMDBError, TVDBError) alongside standard requests exceptions.
Used by tmdb_client, tvdb_client, and artwork modules.
"""

from collections.abc import Callable

import requests.exceptions

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def make_retryable_predicate(*provider_error_types: type) -> Callable[[BaseException], bool]:
    """Create a retry predicate for tenacity.

    Retries on:
    - Provider-specific errors with http_status in {429, 500-504}
    - requests.HTTPError with status in {429, 500-504}
    - Connection errors and timeouts

    Does NOT retry on 4xx client errors (401, 403, 404).

    Args:
        *provider_error_types: Exception classes with an http_status attribute
            (e.g., TMDBError, TVDBError). Pass none for generic HTTP retry.

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

- [ ] **Step 2: Run the new tests**

Run: `python -m pytest tests/scraper/test_http_retry.py -v`

Expected: PASS — all 15 tests pass.

- [ ] **Step 3: Commit**

```bash
git add personalscraper/scraper/http_retry.py
git commit -m "v11.4.2: Add shared make_retryable_predicate factory"
```

## Task 3: Replace \_is_retryable in all 3 clients

**Files:**

- Modify: `personalscraper/scraper/tmdb_client.py:59-76`
- Modify: `personalscraper/scraper/tvdb_client.py:70-88`
- Modify: `personalscraper/scraper/artwork.py:41-58`

- [ ] **Step 1: Replace \_is_retryable in tmdb_client.py**

In `personalscraper/scraper/tmdb_client.py`, replace the local `_is_retryable` function (lines 59-76) with:

```python
from personalscraper.scraper.http_retry import make_retryable_predicate

_is_retryable = make_retryable_predicate(TMDBError)
```

Remove the entire `def _is_retryable(exc: BaseException) -> bool:` function and its docstring. The `_is_retryable` name is preserved so the `@retry(retry=retry_if_exception(_is_retryable))` decorator on line 140 stays unchanged.

- [ ] **Step 2: Replace \_is_retryable in tvdb_client.py**

In `personalscraper/scraper/tvdb_client.py`, replace the local `_is_retryable` function (lines 70-88) with:

```python
from personalscraper.scraper.http_retry import make_retryable_predicate

_is_retryable = make_retryable_predicate(TVDBError)
```

Remove the entire `def _is_retryable(exc: BaseException) -> bool:` function. The `@retry` decorator on line 184 stays unchanged.

- [ ] **Step 3: Replace \_is_retryable in artwork.py**

In `personalscraper/scraper/artwork.py`, replace the local `_is_retryable` function (lines 41-58) with:

```python
from personalscraper.scraper.http_retry import make_retryable_predicate

_is_retryable = make_retryable_predicate()
```

No provider error type needed — artwork only has generic HTTP errors. Remove the entire `def _is_retryable(exc: BaseException) -> bool:` function. The `@retry` decorator on line 117 stays unchanged.

- [ ] **Step 4: Run existing retryable tests**

Run: `python -m pytest tests/scraper/test_tmdb_client.py::TestIsRetryable tests/scraper/test_tvdb_client.py::TestIsRetryable -v`

Expected: PASS — existing tests still pass because `_is_retryable` is still importable with the same behavior.

- [ ] **Step 5: Run full scraper test suite**

Run: `python -m pytest tests/scraper/ -v`

Expected: All tests pass.

- [ ] **Step 6: Run full test suite for regressions**

Run: `python -m pytest tests/ -x -q`

Expected: All tests pass, 0 failures.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/scraper/tmdb_client.py personalscraper/scraper/tvdb_client.py personalscraper/scraper/artwork.py
git commit -m "v11.4.3: Replace 3 local _is_retryable with shared make_retryable_predicate"
```

## Task 4: Update test imports (if needed)

**Files:**

- Modify: `tests/scraper/test_tmdb_client.py` (if import path changed)
- Modify: `tests/scraper/test_tvdb_client.py` (if import path changed)

- [ ] **Step 1: Check if existing test imports still work**

The existing tests import `_is_retryable` from the client modules:

```python
# test_tmdb_client.py line 18
from personalscraper.scraper.tmdb_client import _is_retryable

# test_tvdb_client.py line 20
from personalscraper.scraper.tvdb_client import _is_retryable
```

Since `_is_retryable` is now a module-level variable (not a function) in each client, these imports still work. No changes needed unless the import fails.

- [ ] **Step 2: Verify by running tests**

Run: `python -m pytest tests/scraper/test_tmdb_client.py::TestIsRetryable tests/scraper/test_tvdb_client.py::TestIsRetryable tests/scraper/test_http_retry.py -v`

Expected: All pass. If any import fails, update the import path in the test file to:

```python
from personalscraper.scraper.http_retry import make_retryable_predicate
```

And recreate the predicate in the test setup.

- [ ] **Step 3: Commit (only if changes were needed)**

```bash
git add tests/scraper/test_tmdb_client.py tests/scraper/test_tvdb_client.py
git commit -m "v11.4.4: Update test imports for shared _is_retryable"
```

## Task 5: Update IMPLEMENTATION.md

- [ ] **Step 1: Update V11 Phase 4 entry**

Mark Phase 4 as complete in `docs/IMPLEMENTATION.md`. Add V11 acceptance criteria check:

- [ ] Per-torrent error isolation works
- [ ] CLI config errors show friendly messages
- [ ] Dead `select_best_image` removed
- [ ] Shared `make_retryable_predicate` replaces 3 copies
- [ ] All tests pass

- [ ] **Step 2: Run final full test suite**

Run: `python -m pytest tests/ -x -q`

Expected: All tests pass, 0 failures.

- [ ] **Step 3: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v11.4.5: Update IMPLEMENTATION.md — V11 complete"
```
