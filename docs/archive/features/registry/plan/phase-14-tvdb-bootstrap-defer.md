# Phase 14 — Defer TVDB client bootstrap HTTP call

Created in response to Phase 9 finding: `TVDBClient.__init__` makes a live `tvdb-bootstrap` HTTP call (POST `/login`) during construction. This blocks removing the autouse `_patch_provider_registry_for_cli_tests` fixture (Phase 9.1 deferred concern).

## Gate

- Phase 9 complete (typed_settings_stub introduced).
- Phase 10 complete (existing_validator refactor doesn't conflict).

## Goal

Move the TVDB bootstrap login from `TVDBClient.__init__` to a lazy `_ensure_session()` that runs on first real HTTP call. After this phase, `TVDBClient(settings=...)` is a pure-Python construction (no network) — the registry can boot on dummy credentials without hitting the live TVDB API.

## Scope

- `personalscraper/api/metadata/tvdb.py` (or wherever `TVDBClient` lives — verify by grep).
- `tests/integration/api/metadata/test_tvdb_client.py` (or similar) — bootstrap test must still cover the deferred-login path.
- `tests/unit/api/metadata/test_tvdb_bootstrap.py` (if exists) — adjust expectation: bootstrap is lazy now.

## Sub-phases

### 14.1 — Locate TVDB bootstrap call

```bash
rg --type py "tvdb-bootstrap|TVDB.*login|bootstrap.*tvdb" personalscraper/ -l
```

Read the current `TVDBClient.__init__`. Document the bootstrap sequence:

1. What HTTP call is made on construction?
2. What state does it persist (auth token, session ID)?
3. What happens if bootstrap fails at construction time? (Currently: `ApiError` raised — see Phase 9 finding.)

Commit: `docs(scraper): document TVDB bootstrap call sequence (Phase 14 prep)`

### 14.2 — Extract bootstrap into `_ensure_session()`

Replace direct call in `__init__` with stored-state-only construction. Add private helper:

```python
class TVDBClient:
    def __init__(self, settings: Settings, ...) -> None:
        self._settings = settings
        self._session_token: str | None = None  # lazy
        # ... no HTTP call ...

    def _ensure_session(self) -> str:
        """Fetch and cache a bootstrap session token (idempotent)."""
        if self._session_token is None:
            response = self._http_transport.post(
                f"{self._base_url}/login",
                json={"apikey": self._settings.tvdb_api_key},
            )
            self._session_token = response.json()["data"]["token"]
        return self._session_token
```

Every method that uses the token (search, get_series, get_episodes, …) calls `_ensure_session()` first.

Commit: `refactor(scraper): defer TVDB bootstrap login to first HTTP call`

### 14.3 — Update existing tests

- Tests that construct `TVDBClient` and then make HTTP calls: no change needed (bootstrap fires on first method call as before).
- Tests that construct `TVDBClient` and ASSERT bootstrap fired at construction: rewrite to assert it fires on first method call.
- Tests that assert construction RAISES on bad credentials: rewrite to assert the raise happens on first method call.

Find affected tests: `rg --type py "TVDBClient\(" tests/`. Audit each.

Commit: `test(scraper): adjust TVDB bootstrap tests for deferred login`

### 14.4 — Verify

- `python -m pytest tests/integration/api/metadata/test_tvdb_client.py -q` → all pass.
- `make test` → 5625 passed baseline.
- `make lint` → clean.

```python
# Smoke test (manual): TVDBClient construction with bogus key should NOT raise
from personalscraper.api.metadata.tvdb import TVDBClient
from personalscraper.config import Settings
c = TVDBClient(settings=Settings(tvdb_api_key="bogus", ...))  # MUST NOT raise
# Only this should raise:
try:
    c.search_series("foo")  # triggers _ensure_session → raises ApiError 401
except ApiError:
    pass
```

Commit: `chore(scraper): verify TVDB deferred bootstrap (Phase 14 gate)`

## Phase gate

- `TVDBClient(settings=...)` does NOT make HTTP calls during construction.
- All TVDB integration tests pass.
- `make test` exit 0.

## ACC criteria touched

- None directly.

## Cost estimate

- DeepSeek dispatch: ~10-15 min.
- Test adjustments: ~10 min.
- Total: ~25 min.

## Risk

Low-medium. The refactor is mechanical (move call site). Risk: subtle ordering bug if a method assumes session is already initialized. Mitigation: targeted tests + smoke test.

## Unblocks

- Phase 15 (remove autouse CLI fixture).
