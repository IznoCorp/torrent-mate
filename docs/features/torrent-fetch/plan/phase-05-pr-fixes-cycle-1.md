# Phase 5 — PR fixes cycle 1

Fixes from `/implement:pr-review` cycle 1 (PR #90, 4-agent review). All findings are coherent with DESIGN scope — no design contradiction. One commit for the phase.

## Gate

**Requires Phases 1–4 complete + PR #90 reviewed.** All fixes land in the existing feature files; tests extended.

## Sub-phases

### 5.1 — Fix (major): empty-string `download_url` → useless GET

**Finding:** `resolve_source` guards `if download_url is None`, but an empty string `""` is falsy-yet-not-None: it bypasses the magnet check AND the None-guard, reaching `fetch_torrent_source("")` → `get_bytes("")` joins `""` onto `base_url` and GETs the tracker root instead of raising.
**Location:** `personalscraper/api/tracker/_fetch.py` `resolve_source` (the `if download_url is None`) + `fetch_torrent_source` (no empty-url guard).
**Fix:** `resolve_source` → `if not download_url:` (catches `None` and `""`). Also harden `fetch_torrent_source`: at the top, after the magnet check, `if not url: raise TorrentFetchError(...)` (it is publicly exported; an empty url is invalid input). Keep messages accurate.
**Acceptance:** `resolve_source` with `download_url=""` raises `TorrentFetchError`; `fetch_torrent_source("", transport)` raises `TorrentFetchError` and never calls `get_bytes`. Tests added for both.

### 5.2 — Fix (medium): silent skip of non-canonicalizable `expected_info_hash`

**Finding:** when `expected_info_hash` is truthy but non-canonicalizable, the cross-check is silently skipped (`except ValueError: return source`) with no log and no test — a requested integrity check downgraded to no-check invisibly.
**Location:** `personalscraper/api/tracker/_fetch.py` cross-check branch.
**Fix:** add a module-level logger (`get_logger("api.tracker.fetch")`) and log a `warning` (`expected_info_hash_uncanonicalizable`, with provider + url + the offending value) before `return source`. Use the module logger — do NOT reach into `transport._log`. Behavior unchanged (still returns the structurally-valid source); only observability added.
**Acceptance:** a valid `.torrent` + a truthy junk `expected_info_hash` (e.g. `"zzz"`, 31-char) returns the source without raising; a regression test pins this; the warning is emitted (assert via `caplog` if practical).

### 5.3 — Fix (medium): streamed response not closed on oversize abort

**Finding:** on the oversize `raise ValueError`, the partially-consumed `stream=True` response is abandoned without `close()` — connection leak on the exact path defending against an unbounded stream.
**Location:** `personalscraper/api/transport/_http.py` `get_bytes._download_mapper`.
**Fix:** wrap the stream consumption so the response is closed on every exit — `try: … finally: resp.close()` inside `_download_mapper` (covers success, oversize, and empty paths). Search path (`_format_response`, non-streamed) unchanged.
**Acceptance:** on oversize, `resp.close()` is called (assert via a spy on the fake response). Existing get_bytes tests still pass.

### 5.4 — Fix (minor→medium): public `provider_name` accessor

**Finding:** `_fetch.py:147` reads `transport._policy.provider_name` (cross-module double-private access; no public accessor).
**Location:** `personalscraper/api/transport/_http.py` (add accessor) + `personalscraper/api/tracker/_fetch.py` (use it).
**Fix:** add `@property def provider_name(self) -> str: return self._policy.provider_name` to `HttpTransport`; replace `transport._policy.provider_name` with `transport.provider_name` in `_fetch.py`.
**Acceptance:** `HttpTransport.provider_name` returns the policy provider name; `_fetch.py` no longer touches `_policy`. mypy clean.

### 5.5 — Fix (minor): delete dead `_ResponseMapper` alias

**Finding:** `_http.py:34-36` defines `_ResponseMapper = Callable[[requests.Response], _T]`, referenced nowhere, with a factually-wrong "keeps the import live" comment (`Callable` is used directly in the real signatures).
**Fix:** delete the alias + its comment. Keep `_T = TypeVar("_T")` (used). Confirm ruff/mypy still clean.
**Acceptance:** alias gone; `ruff check` + `mypy` clean.

### 5.6 — Fix (minor): stale `_is_retryable` docstring

**Finding:** `_is_retryable` docstring says "exc: The exception raised by \_do_request" — the method was renamed to `_do_request_raw` in Phase 2.
**Fix:** update the docstring reference to `_do_request_raw`.
**Acceptance:** docstring accurate.

### 5.7 — Fix (minor): add 404 propagation test

**Finding:** non-auth/non-2xx propagation is only tested for 500; the `_AUTH_STATUSES` lower boundary (404 → `ApiError`, not `TrackerAuthError`) is untested.
**Location:** `tests/unit/test_tracker_fetch.py`.
**Fix:** add `test_404_propagates_as_api_error_not_auth_error`.
**Acceptance:** a 404 `ApiError` from the transport propagates as `ApiError`, asserted `not isinstance(e, TrackerAuthError)`.

### 5.8 — Commit

One commit: `fix(torrent-fetch): PR review cycle 1 — empty-url guard, skip-log, stream close, provider_name accessor, dead-alias + docstring + 404 test`.
(Avoid a `fetch`-word-start token in the subject if it trips the block_curl hook; the `torrent-fetch` scope is safe — mid-token.)

## Gate exit checklist

- [ ] `ruff check personalscraper/ tests/` + `ruff format --check personalscraper/ tests/` clean
- [ ] `mypy` clean on the touched modules
- [ ] `pytest tests/unit/test_tracker_fetch.py tests/unit/test_http_transport_get_bytes.py` green (new tests included)
- [ ] full `pytest tests/unit/` no regression
- [ ] `_fetch.py` no longer references `transport._policy`
- [ ] Commit SHA recorded
