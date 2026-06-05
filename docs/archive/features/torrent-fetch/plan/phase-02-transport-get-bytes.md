# Phase 2 — Transport binary GET

## Gate

**Requires Phase 1 complete:**

```bash
python -c "from personalscraper.api.tracker._errors import TrackerAuthError, TorrentFetchError; print('ok')"
```

Expected: `ok`

---

## Goal

Extend `HttpTransport` (`personalscraper/api/transport/_http.py`) with four changes:

1. **`_do_request_raw`** — extracted inner helper that executes a single HTTP call, handles rate-limiting, URL build, logging, and non-2xx raising, then calls a `response_mapper`. Eliminates duplication between the JSON/XML path and the new binary path (survey C1).
2. **`_request_outer` refactor** — parameterized with `(circuit, rate_limiter, response_mapper)`. `get`/`post` pass the search breaker; `get_bytes` passes the download breaker. Zero duplication of the retry/circuit logic.
3. **`self._download_circuit` + `self._download_rate_limiter`** — a dedicated second pair (D3), named `"<provider>-download"`, built from the same `TransportPolicy` thresholds in `__init__`. A download 5xx **never** opens the search circuit.
4. **`get_bytes(self, url: str, *, max_bytes: int = 10_485_760) -> bytes`** — binary GET with absolute/relative URL detection (D10), no auth-param re-merge (D9), streamed size cap + empty-body reject (D5), using the download circuit/limiter (D3). **On empty/oversize it raises a provider-agnostic `ValueError`** — NOT a tracker error. `HttpTransport` must stay "fully decoupled from any specific provider" (its own docstring) and import **nothing** from `api/tracker`; the fetcher (Phase 3) maps this `ValueError` to `TorrentFetchError`.

> **Read the live file first.** The current `_http.py` has `_request_outer` (`:104`) and `_do_request` (`:145`). The refactor renames `_do_request` → `_do_request_raw` and splits format parsing into a `response_mapper` callable. Confirm exact field names (`_circuit`, `_rate_limiter`) before editing.

---

## Files

- **Modify:** `personalscraper/api/transport/_http.py`
- **Create:** `tests/unit/test_http_transport_get_bytes.py`

---

## Tasks

### Task 2.1 — Refactor `_http.py`

Read the current `_http.py` before editing. The changes are:

**`__init__`** — add download circuit + limiter after the existing `_circuit`/`_rate_limiter`:

```python
# Download circuit + limiter — used exclusively by get_bytes() (D3).
# Named "<provider>-download" so CircuitBreakerOpened events are distinguishable.
self._download_circuit = CircuitBreaker(
    name=f"{policy.provider_name}-download",
    failure_threshold=policy.circuit.failure_threshold,
    cooldown_seconds=policy.circuit.cooldown_seconds,
    event_bus=event_bus,
)
self._download_rate_limiter = RateLimiter(policy.rate_limit.requests_per_second)
```

**`get` and `post`** — delegate to `_request_outer` with explicit `circuit`/`rate_limiter`/`response_mapper` args (use `self._format_response` for the mapper, extracted from the current `_do_request` tail).

**`get_bytes`** — new public method:

```python
def get_bytes(self, url: str, *, max_bytes: int = _DEFAULT_MAX_BYTES) -> bytes:
    # D10: absolute URL verbatim; relative joined onto base_url.
    if url.lower().startswith(("http://", "https://")):
        full_url = url
    else:
        full_url = f"{self._policy.base_url.rstrip('/')}{url}"

    def _download_mapper(resp: requests.Response) -> bytes:
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=65536):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"download exceeds max_bytes={max_bytes}")  # D5 oversize (agnostic)
            chunks.append(chunk)
        data = b"".join(chunks)
        if not data:
            raise ValueError("empty download body")  # D5 empty (agnostic)
        return data

    return self._request_outer(
        "GET", "",
        circuit=self._download_circuit,
        rate_limiter=self._download_rate_limiter,
        response_mapper=_download_mapper,
        override_url=full_url,  # D9: skip auth_params() merge
        stream=True,
    )
```

**`_request_outer`** — add `(circuit, rate_limiter, response_mapper, override_url, stream)` params; the rate limiter arg is forwarded to `_do_request_raw` (which acquires it).

**`_do_request_raw`** — renamed from `_do_request`; accepts `(rate_limiter, override_url, stream, response_mapper)`. Key invariant: when `override_url` is set, URL is used verbatim and `auth.auth_params()` is **not** merged (D9). `rate_limiter.acquire()` is called here (inside the retry loop), not in `_request_outer`.

- [ ] Apply the refactor to `_http.py`.
- [ ] Verify: `python -c "from personalscraper.api.transport._http import HttpTransport; print('ok')"`

---

### Task 2.2 — Run existing transport tests (no regression)

- [ ] `pytest tests/unit/ -k "transport" -v` — all pass, same count as before.

---

### Task 2.3 — Write `tests/unit/test_http_transport_get_bytes.py`

Use `MagicMock` for the session; `monkeypatch` to replace `transport._session.request`. No real network calls.

The `_make_transport` factory uses `ApiKeyAuth(key=..., param=..., location=...)` — check the real `_auth.py` for the exact constructor signature before writing the factory.

**Design reference:** `Design: §5.1 — get_bytes uses download circuit/limiter (D3); absolute URL verbatim, relative joined onto base_url (D10); no auth-param re-merge (D9); rejects empty body and oversized body (D5); response_format=xml still returns raw bytes.`
**Contract:** fake sessions via monkeypatching; circuit isolation via direct `_download_circuit.state` / `_circuit.state` inspection.

- [ ] Create the file with the following test cases (write real pytest code):

**TestGetBytesUrlHandling (D10):**

- `test_absolute_url_used_verbatim` — `https://c411.org/dl/abc?apikey=xyz` → `requests.request` receives that exact URL unchanged.
- `test_relative_url_joined_onto_base_url` — `/api/download/abc123?token=jwt` with `base_url="https://lacale.io"` → `requests.request` receives `https://lacale.io/api/download/abc123?token=jwt`.

**TestGetBytesNoAuthRemerge (D9):**

- `test_no_apikey_appended_to_absolute_url` — capture `kwargs["params"]`; must be `None` or empty (no second `apikey`).

**TestGetBytesSizeCap (D5) — agnostic `ValueError` (NOT TorrentFetchError; transport stays decoupled):**

- `test_oversize_body_raises_value_error` — `iter_content` yields 100 bytes; `max_bytes=10` → `ValueError` with `"max_bytes"` in message.
- `test_empty_body_raises_value_error` — `iter_content` yields no chunks → `ValueError` with `"empty"` in message.
- (The `TorrentFetchError` surfacing for these cases is asserted at the fetcher level in Phase 3, not here.)

**TestGetBytesNon2xx:**

- `test_401_raises_api_error` — fake 401 response → `ApiError(http_status=401)`.
- `test_500_raises_api_error` — fake 500 response → `ApiError(http_status=500)`.

**TestDownloadCircuitIsolation (D3):**

- `test_download_500_does_not_open_search_circuit` — `failure_threshold=2`; two failing `get_bytes` → `_download_circuit.state == OPEN`, `_circuit.state == CLOSED`.
- `test_search_rate_limiter_not_acquired_by_get_bytes` — spy on `_rate_limiter.acquire`; call `get_bytes` with a succeeding response → spy never called.

**TestGetBytesResponseFormat (survey F9):**

- `test_xml_transport_returns_raw_bytes` — `response_format="xml"` transport; `get_bytes` returns `bytes`, not a parsed dict.

- [ ] Run: `pytest tests/unit/test_http_transport_get_bytes.py -v` — all 10 pass.

---

### Task 2.4 — Run full unit suite

- [ ] `pytest tests/unit/ -v --tb=short 2>&1 | tail -20` — `NNNN passed`, 0 failed/errors.

---

### Task 2.5 — Commit

```bash
git add personalscraper/api/transport/_http.py tests/unit/test_http_transport_get_bytes.py
git commit -m "feat(torrent-fetch): HttpTransport.get_bytes + dedicated download circuit/limiter"
```

---

## Gate exit checklist

- [ ] `python -c "from personalscraper.api.transport._http import HttpTransport; _ = HttpTransport.get_bytes; print('ok')"` → `ok`
- [ ] `pytest tests/unit/test_http_transport_get_bytes.py` → 10 passed, 0 failed
- [ ] Existing transport/search tests unchanged
- [ ] Commit SHA recorded
