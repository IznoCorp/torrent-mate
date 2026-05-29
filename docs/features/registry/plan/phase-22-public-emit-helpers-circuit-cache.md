# Phase 22 — Promote emit helpers to public + cache TVDB circuit reference

Created from `code-reviewer` audit (2026-05-27) findings I1 + I2.

**I1**: `_emit_provider_fallback` / `_emit_provider_exhausted` are documented as
the public API for chain-iteration sites but carry leading-underscore names.
11+ call sites across `movie_service.py`, `tv_service.py`, and
`tv_service_episodes.py` import them — they are de-facto public.

**I2**: `_eligible()` in `_factory.py:246` does `getattr(provider, "circuit", None)`.
For `TVDBClient`, `.circuit` is a `@property` that calls `_ensure_transport()`,
triggering the JWT bootstrap HTTP call. Phase 14 deferred the bootstrap from
`__init__`, but the first `registry.chain(...)` or `registry.status()` post-boot
still triggers JWT exchange unexpectedly — eligibility checks should not be
network operations.

## Gate

- Phase 14 complete (TVDB deferred bootstrap).
- Phase 7 complete (chain helpers established).

## Goal

1. Rename the two emit helpers to public names; update 11+ call sites.
2. Add a non-network `circuit_state` accessor on `TVDBClient` so eligibility
   checks read state without triggering bootstrap.

## Scope

- `personalscraper/api/metadata/registry/__init__.py` — rename helpers + update
  internal usage.
- `personalscraper/api/metadata/tvdb.py` — add cached `_circuit` reference.
- `personalscraper/api/metadata/registry/_factory.py::_eligible` — read the
  cached circuit reference.
- `personalscraper/scraper/movie_service.py` (3 call sites).
- `personalscraper/scraper/tv_service.py` (3 call sites).
- `personalscraper/scraper/tv_service_episodes.py` (4 call sites).
- Tests in `tests/unit/api/metadata/registry/` and `tests/integration/`.

## Sub-phases

### 22.1 — Promote emit helpers to public names

Rename:

- `_emit_provider_fallback` → `emit_provider_fallback`
- `_emit_provider_exhausted` → `emit_provider_exhausted`

Keep the underscore aliases as deprecation shims for one cycle (or skip the
aliases since the feature is unreleased pre-1.0 per project memo). Update
every call site.

Commit: `refactor(registry): promote emit_provider_fallback/emit_provider_exhausted to public`

### 22.2 — Cache TVDB circuit reference for eligibility checks

In `TVDBClient.__init__`, store the circuit policy directly (it's already
passed in via `circuit` parameter or `_DEFAULT_CIRCUIT`). Expose
`circuit_state -> str` (or expose the CircuitBreaker as a plain attribute
non-property) so `getattr(provider, "circuit", None)` returns without
triggering `_ensure_transport()`.

Concrete plan:

- Add `self._circuit_breaker: CircuitBreaker | None = None` (cached, set when
  `_ensure_transport` runs).
- Override the `circuit` property: if `__transport` is None, return a sentinel
  CLOSED-by-default breaker (or None — `_eligible` already handles `None`).
- After first `_ensure_transport()`, the cached `self._circuit_breaker` is
  populated and the property returns it.

Alternative simpler approach: `_eligible` doesn't need the live breaker — it
needs the eligibility decision (CLOSED or HALF_OPEN). Add
`TVDBClient.is_eligible() -> bool` that returns True (no bootstrap) before
first transport access, then delegates to the real circuit afterward.

Pick the cleanest path. Document in commit body.

Commit: `fix(api/metadata): cache TVDB circuit reference; eligibility checks avoid bootstrap`

### 22.3 — Regression test: eligibility doesn't bootstrap

Smoke test:

```python
from personalscraper.api.metadata.tvdb import TVDBClient
from personalscraper.api.metadata.registry._factory import _eligible
from unittest.mock import MagicMock

client = TVDBClient(api_key="bogus", event_bus=MagicMock())
# Construction is HTTP-free (Phase 14 anchor).
assert _eligible(client) is True
# _eligible should ALSO be HTTP-free (Phase 22 anchor).
# Verify by patching _ensure_transport and asserting it was NOT called.
```

Add as unit test in `tests/unit/test_tvdb_client.py`.

Commit: `test(api/metadata): regression — TVDB eligibility check is HTTP-free`

## Phase gate

- `rg --type py "_emit_provider_fallback\|_emit_provider_exhausted" personalscraper/ tests/`
  returns only the definition lines + any explicit alias-deprecation entries.
- The eligibility-no-bootstrap regression test passes.
- `make test` 5636+ passed.

## ACC criteria touched

- None directly. Hardens Phase 14 + Phase 7 outcomes.

## Cost estimate

- 22.1: ~10 min DeepSeek (rename + call-site sweep).
- 22.2: ~15–20 min Opus or DeepSeek (modest architectural change).
- 22.3: ~5 min DeepSeek.
- Total: ~30–40 min.

## Risk

Low-medium. The rename touches 11+ files but is mechanical. The circuit-cache
change requires careful reasoning about the eligibility-vs-real-circuit-state
distinction.
