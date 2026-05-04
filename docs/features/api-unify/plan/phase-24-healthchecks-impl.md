# Phase 24 — Healthchecks Migration

**Type**: impl
**Goal**: Migrate healthchecks half from `notifier.py` → `api/notify/healthchecks.py`. Final deletion of `notifier.py`.

## Gate (prereq)

Phase 23 complete. Transport option decided. `HttpTransport` already supports
`response_format="text"` from Phase 1.

## Sub-phases

### 24.1 — Build `api/notify/healthchecks.py`

```python
class HealthcheckClient:
    REQUIRED_CREDS: ClassVar[list[str]] = ["HEALTHCHECK_PING_URL"]
    provider_name = "healthchecks"

    @classmethod
    def policy(cls, ping_url: str) -> TransportPolicy:
        return TransportPolicy(
            provider_name="healthchecks",
            base_url=ping_url,
            auth=NoAuth(),
            timeout_seconds=5,
            retry=RetryPolicy(max_attempts=2),
            circuit=CircuitPolicy(failure_threshold=10, cooldown_seconds=60),
            response_format="text",  # if Option A — else use the bypass path
        )

    def __init__(self, transport: HttpTransport) -> None:
        self._transport = transport

    def ping_start(self) -> None:
        self._safe_get("/start")

    def ping_success(self) -> None:
        self._safe_get("")

    def ping_fail(self) -> None:
        self._safe_get("/fail")

    def _safe_get(self, suffix: str) -> None:
        try:
            self._transport.get(suffix)
        except Exception as e:
            log.warning("healthcheck_ping_failed", suffix=suffix, error=str(e))
            # fail-soft — never raise
```

### 24.2 — Delete `notifier.py`

```bash
rg "from personalscraper\.notifier import" personalscraper/ tests/
rg "from personalscraper import notifier" personalscraper/ tests/
```

Rewrite all remaining imports. Then:

```bash
git rm personalscraper/notifier.py
```

### 24.3 — Tests

`tests/unit/test_healthcheck_client.py`:

- `ping_start()` → GET to `/start`.
- `ping_success()` → GET to base URL.
- `ping_fail()` → GET to `/fail`.
- All three on connection error → no exception raised, warning logged.

### 24.4 — Phase 24 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.notify.healthchecks import HealthcheckClient"
! rg "personalscraper\.notifier" personalscraper/ tests/ --files-with-matches
! ls personalscraper/notifier.py 2>/dev/null
```

**Commit**: `chore(api-unify): phase 24 gate — healthchecks migration done, notifier.py deleted`
