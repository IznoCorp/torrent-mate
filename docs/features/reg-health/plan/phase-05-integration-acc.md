# Phase 5 — Integration + ACC + docs

## Gate

```bash
make check          # lint + test + module-size + typed-api (zero errors)
make openapi        # verify no drift
cd frontend && npm run lint && npm run typecheck && npx vitest run
```

Additionally, the design-gaps and feature-map must be clean:

```bash
python scripts/audit_design_coverage.py --strict 2>&1 | tail -5
python scripts/update_feature_map.py --check 2>&1 | tail -5
```

No regressions from the Phase 1 freeze test:

```bash
pytest tests/api/metadata/registry/test_status_contract_frozen.py -v
```

No stale imports (for any file deleted across these phases):

```bash
rg "old.module.path" tests/   # must return zero matches for any removed module
```

## Objectives

1. Write a manual E2E test script that verifies: REST snapshot returns
   `providers[]` with the frozen shape, and a live `CircuitBreakerOpened`
   event is reflected in the panel without a page reload.
2. Write the executable ACCEPTANCE criteria in `docs/features/reg-health/ACCEPTANCE.md`
   (every criterion must be an executable shell command with documented
   expected output — no prose criteria per SH-16 / tech-debt 0.16.0).
3. Add a §registry section to `docs/reference/web-ui.md` documenting the
   new route, the freeze test, and the page + WS integration.
4. Run the complete gate and verify `make check` is green end-to-end.

## Files to create

- `docs/features/reg-health/ACCEPTANCE.md`
- `tests/e2e/test_registry_health.py` (manual E2E test script)

## Files to modify

- `docs/reference/web-ui.md` — add §registry section.

## E2E test (`tests/e2e/test_registry_health.py`)

A manual E2E test (requires a running dev server with a configured
registry). Marked with `@pytest.mark.e2e` so it only runs when explicitly
invoked. Uses the project's `TestClient` pattern with the real app (not
mocked).

```python
"""Manual E2E tests for the registry health page (reg-health S6).

These tests require a running dev server with a configured
``ProviderRegistry`` on ``app.state``.  They are marked ``e2e`` and are
NOT run by ``make test`` — invoke explicitly:

    pytest tests/e2e/test_registry_health.py -v -m e2e
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestRegistryHealthE2E:
    """End-to-end tests for the registry health surface."""

    def test_rest_snapshot_returns_frozen_shape(self, auth_client):
        """GET /api/registry/status returns providers[] with the frozen shape."""
        resp = auth_client.get("/api/registry/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)
        # Every provider item must have all 7 frozen keys.
        for item in data["providers"]:
            assert set(item.keys()) == {
                "provider_name",
                "circuit_state",
                "failure_count_recent",
                "last_success_at",
                "last_failure_at",
                "last_latency_ms",
                "degraded",
            }
            assert item["circuit_state"] in {"closed", "open", "half_open"}
            assert isinstance(item["failure_count_recent"], int)
            assert item["failure_count_recent"] >= 0

    def test_unauthenticated_returns_401(self, client):
        """GET /api/registry/status without auth → 401."""
        resp = client.get("/api/registry/status")
        assert resp.status_code == 401

    def test_staging_returns_200(self, auth_client_staging):
        """GET /api/registry/status on staging → 200 (read allowed)."""
        resp = auth_client_staging.get("/api/registry/status")
        assert resp.status_code == 200

    def test_freeze_test_still_passes(self):
        """The characterization freeze test must pass after all phases."""
        # Run inline — this is the same test from Phase 1.
        from tests.api.metadata.registry.test_status_contract_frozen import (
            test_circuitstate_enum_identity_preserved,
            test_circuitstate_values_closed_set,
            test_providerstatus_fields_exact_set,
            test_providerstatus_json_roundtrip,
        )

        test_providerstatus_fields_exact_set()
        test_circuitstate_values_closed_set()
        test_providerstatus_json_roundtrip()
        test_circuitstate_enum_identity_preserved()

    def test_frontend_page_accessible(self, auth_client):
        """The /registry SPA route serves the index.html shell (200)."""
        resp = auth_client.get("/registry")
        # The SPA serves index.html for client-side routes.
        assert resp.status_code == 200
```

## ACCEPTANCE (`docs/features/reg-health/ACCEPTANCE.md`)

Every criterion must be an executable shell command with documented
expected output (SH-16 / tech-debt 0.16.0). No prose-only criteria.

````markdown
# ACCEPTANCE — reg-health (S6 Web UI: Registry + Health)

## ACC-01 — REST endpoint returns frozen shape (authed)

```bash
curl -s --connect-timeout 10 --max-time 30 \
  -b "session=$(cat /tmp/test_session_cookie)" \
  http://localhost:8710/api/registry/status | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert 'providers' in data, 'missing providers key'
for p in data['providers']:
    assert set(p.keys()) == {
        'provider_name', 'circuit_state', 'failure_count_recent',
        'last_success_at', 'last_failure_at', 'last_latency_ms', 'degraded'
    }, f'Key drift: {set(p.keys())}'
    assert p['circuit_state'] in {'closed', 'open', 'half_open'}, f'Bad state: {p[\"circuit_state\"]}'
    assert isinstance(p['failure_count_recent'], int) and p['failure_count_recent'] >= 0
print('ACC-01 PASS')
"
```
````

Expected: `ACC-01 PASS`

## ACC-02 — Unauthenticated → 401

```bash
curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 30 \
  http://localhost:8710/api/registry/status
```

Expected: `401`

## ACC-03 — Staging (8711) → 200 (read allowed)

```bash
curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 30 \
  -b "session=$(cat /tmp/test_session_cookie)" \
  http://localhost:8711/api/registry/status
```

Expected: `200`

## ACC-04 — Freeze test fails on removed field

```bash
# Simulate: temporarily comment out last_latency_ms from ProviderStatus,
# run the freeze test, verify it FAILS, then restore.
pytest tests/api/metadata/registry/test_status_contract_frozen.py -v
```

Expected: all 4 tests PASS (field set exact, CircuitState values closed,
JSON roundtrip, enum identity). A removed/renamed field would make
`test_providerstatus_fields_exact_set` FAIL.

## ACC-05 — Frontend page renders provider cards

```bash
# Manual: open https://tm-staging.iznogoudatall.xyz/registry,
# verify each provider has a card with name + circuit badge + latency.
# Cannot be fully automated without Playwright — the vitest suite covers
# the rendering logic (Phase 4).  This ACC documents the manual check.
echo "ACC-05: vérifier manuellement dans le navigateur"
```

## ACC-06 — make check green

```bash
make check
```

Expected: zero errors (lint, test, module-size, typed-api). Summary line:
`NNNN passed` with 0 failed/errors.

## ACC-07 — OpenAPI drift clean

```bash
make openapi
git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
```

Expected: exit 0 (no diff — regenerated files match committed).

## ACC-08 — Design gaps + feature map clean

```bash
python scripts/audit_design_coverage.py --strict 2>&1 | tail -5
python scripts/update_feature_map.py --check 2>&1 | tail -5
```

Expected: both exit 0, no unaccounted `Design:`/`Contract:` gaps.

````

## Web-UI docs (`docs/reference/web-ui.md`)

Add a new `## Registry (§S6)` section after the existing S5/scrape-arbiter
section. Follow the established pattern: route, auth perimeter, response
shape, staging behavior, WS integration, freeze test.

```markdown
## Registry (§S6)

The `/api/registry/status` endpoint (reg-health feature, ticket #185)
exposes the live health of every configured metadata provider: circuit-
breaker state, recent failure count, last success/failure timestamps,
and last call latency.

### Route: `GET /api/registry/status`

- Mounted under `guarded_api` (single auth perimeter — §6).
- Read-only — no `X-Requested-With` header required.
- Staging-allowed: returns 200 on 8711 (no `require_not_staging`).
- `response_model`: `RegistryStatusResponse` → `openapi.json` → `schema.d.ts`.
- Timestamps as Unix-epoch floats (consistency with `pipeline_run` convention).
- Fail-soft: a provider whose status read raises is reported `degraded=true`
  rather than 500-ing the whole list.

### Response shape

```json
{
  "providers": [
    {
      "provider_name": "tmdb",
      "circuit_state": "closed",
      "failure_count_recent": 0,
      "last_success_at": 1719792000.0,
      "last_failure_at": null,
      "last_latency_ms": 42.5,
      "degraded": false
    }
  ]
}
````

### Freeze test

`tests/api/metadata/registry/test_status_contract_frozen.py` pins the
public contract as **additive-only**. A removed/renamed `ProviderStatus`
field or `CircuitState` value fails the test. A new field is allowed only
when the test is deliberately extended in the same commit.

### WS integration

The frontend `/registry` page subscribes to the existing event stream
(`useEventStreamContext`) and filters for `CircuitBreakerOpened`,
`CircuitBreakerClosed`, `CircuitBreakerHalfOpened`, and
`RegistryFanOutCompleted`. No backend WS wiring is needed — events
auto-publish through the existing `EventBus → Redis → WS relay` path.

### Frontend

- Page: `frontend/src/pages/RegistryPage.tsx` — one card per provider
  with circuit-state badge, recent failures, relative timestamps, latency.
- Typed client: `frontend/src/api/registry.ts` (R15 — `apiFetch` with
  schema-typed paths).
- Hook: `frontend/src/hooks/useRegistryStatus.ts` (`useQuery` with
  `registryKeys.status()`).

```

## Gotchas

- **ACCEPTANCE criterion ACC-05 is manual**: the rendering logic is
  covered by Vitest (Phase 4). E2E with a real browser requires Playwright
  which is not in this scope. The manual check is documented as ACC-05.

- **Staging test needs auth cookie**: ACC-03 tests staging (8711) with a
  session cookie. The staging instance is read-only for mutating endpoints
  but allows reads. The `write_test_session_cookie.py` helper (if it
  exists) or a manual login step must precede ACC-01/ACC-03.

- **`make openapi` gate is cumulative**: Phase 2 already ran `make openapi`
  and committed the regen. Phase 5 re-runs it to verify no drift was
  introduced by Phases 3-4 (frontend changes do not affect the OpenAPI
  spec, but this is a defense-in-depth check).

- **`audit_design_coverage.py --strict`**: this CI-check script verifies
  that every `Design:` section in the feature map has a matching
  `Contract:` entry. The new `reg-health` feature map entry must be
  added (tests/feature_map/reg-health.json) or the check will fail.

- **Feature map JSON**: if `tests/feature_map/reg-health.json` does not
  exist, create it by running `python scripts/update_feature_map.py`
  (without `--check`) to generate the initial map from the test files
  created in Phases 1-4.

- **No mutation of `IMPLEMENTATION.md`**: the plan files are committed
  under `docs/features/reg-health/plan/`. `IMPLEMENTATION.md` is NOT
  modified by this phase — it is the implement:feature lifecycle
  orchestrator's responsibility.
```
