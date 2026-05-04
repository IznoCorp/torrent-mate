# Phase 24 — Healthchecks Migration

**Type**: impl
**Goal**: Migrate healthchecks half from `notifier.py` → `api/notify/healthchecks.py`. Final deletion of `notifier.py`.

## Gate (prereq)

Phase 23 complete. Transport option decided.

## Sub-phases

### 24.1 (conditional) — Text-response support in HttpTransport (if Option A from Phase 23)

Extend `TransportPolicy.response_format` type to `Literal["json", "xml", "text"]` (adds `"text"` to the existing Literal; `"json"` is always present since Phase 1, `"xml"` was added in Phase 20 if Option A was chosen). Add `text` branch returning `resp.text` directly in `_do_request`. Update reference test to cover.

If Phase 20 chose Option B (no `"xml"`), the Literal goes from `Literal["json"]` to `Literal["json", "text"]` — same process, just one less member.

If Option B chosen (bypass transport entirely), skip this sub-phase.

**Commit**: `feat(api-unify): add text-response support to HttpTransport`

### 24.2 — Build `api/notify/healthchecks.py`

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

### 24.3 — Delete `notifier.py`

```bash
rg "from personalscraper\.notifier import" personalscraper/ tests/
rg "from personalscraper import notifier" personalscraper/ tests/
```

Rewrite all remaining imports. Then:

```bash
git rm personalscraper/notifier.py
```

### 24.4 — Tests

`tests/unit/test_healthcheck_client.py`:

- `ping_start()` → GET to `/start`.
- `ping_success()` → GET to base URL.
- `ping_fail()` → GET to `/fail`.
- All three on connection error → no exception raised, warning logged.

### 24.5 — Phase 24 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.notify.healthchecks import HealthcheckClient"
! rg "personalscraper\.notifier" personalscraper/ tests/ --files-with-matches
! ls personalscraper/notifier.py 2>/dev/null
```

**Commit**: `chore(api-unify): phase 24 gate — healthchecks migration done, notifier.py deleted`
