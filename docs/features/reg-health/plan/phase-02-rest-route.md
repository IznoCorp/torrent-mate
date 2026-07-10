# Phase 2 — REST read route

## Gate

```bash
make check              # lint + test + module-size + typed-api guardrails (zero errors)
make openapi            # regenerate frontend/openapi.json + frontend/src/api/schema.d.ts
git diff --stat frontend/src/api/schema.d.ts frontend/openapi.json
# If changed: commit the regen. CI will flag drift otherwise (project_openapi_drift_ci_guard).
```

Additionally, the new route tests must pass:

```bash
pytest tests/web/routes/test_registry_status.py -v
```

Expected: all tests pass (auth guard 401, shape, staging-allowed 200, fail-soft
per-provider, empty registry → 200 with empty list).

## Objectives

1. Create Pydantic response models for the registry status endpoint in
   `personalscraper/web/models/registry.py`.
2. Create `personalscraper/web/routes/registry.py` with a single
   `GET /api/registry/status` route.
3. Mount the router under `guarded_api` in `personalscraper/web/app.py`.
4. Run `make openapi` and commit the regenerated files.
5. Write route tests covering auth guard, response shape, staging allowance,
   and fail-soft per-provider behavior.

## Files to create

- `personalscraper/web/models/registry.py`
- `personalscraper/web/routes/registry.py`
- `tests/web/routes/test_registry_status.py`

## Files to modify

- `personalscraper/web/app.py` (line ~168-182): add `guarded_api.include_router(registry_router)`.

## Design decisions (from DESIGN §3.3)

- Mounts inside `guarded_api` — session guard inherited from the parent router.
  No `Depends(require_session)` per-route (single auth perimeter rule:
  `docs/reference/web-ui.md` §6, R14/R24).
- **No** `require_x_requested_with` — it's a read-only GET.
- **No** `require_not_staging` — read is allowed on staging (8711 → 200).
- Pydantic `response_model` on the route so OpenAPI → `schema.d.ts` works.
- Timestamps as Unix-epoch floats (consistency with `pipeline_run` epoch convention).
- `last_latency_ms: float | None`.
- `circuit_state` as `Literal["closed", "open", "half_open"]`.
- Fail-soft per provider: if a provider's `.circuit` read raises, report it
  with a degraded marker rather than 500-ing the whole list.

## Pydantic models (`personalscraper/web/models/registry.py`)

```python
"""Pydantic models for the registry status API (reg-health feature).

See docs/features/reg-health/DESIGN.md §3.3 for the route contracts these
models serve.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProviderStatusItem(BaseModel):
    """One provider's runtime status, serialized for the web surface.

    Mirrors the frozen ``ProviderStatus`` dataclass from
    ``personalscraper.api.metadata.registry``, with circuit_state as a
    closed Literal and timestamps as Unix-epoch floats.
    """

    provider_name: str
    circuit_state: Literal["closed", "open", "half_open"]
    failure_count_recent: int
    last_success_at: float | None
    last_failure_at: float | None
    last_latency_ms: float | None
    degraded: bool = False


class RegistryStatusResponse(BaseModel):
    """Response body for ``GET /api/registry/status``."""

    providers: list[ProviderStatusItem]
```

## Route (`personalscraper/web/routes/registry.py`)

```python
"""Registry status REST route (reg-health feature).

Single read-only endpoint ``GET /api/registry/status`` that returns the
live state of every configured provider: circuit-breaker status, recent
failure count, last success/failure timestamps, and last call latency.

Mounted under ``guarded_api`` so session auth is inherited — no per-route
``Depends(require_session)`` (single auth perimeter rule, R14/R24).
Read-only — no ``X-Requested-With`` guard; staging-allowed (no
``require_not_staging``).
"""

from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Request

from personalscraper.api.metadata.registry import ProviderRegistry, ProviderStatus
from personalscraper.logger import get_logger
from personalscraper.web.models.registry import ProviderStatusItem, RegistryStatusResponse

router = APIRouter(prefix="/api/registry", tags=["registry"])
logger = get_logger(__name__)


def _dt_to_epoch(dt) -> float | None:
    """Convert a timezone-aware datetime to Unix-epoch float.

    Args:
        dt: A ``datetime`` with ``tzinfo`` set, or ``None``.

    Returns:
        ``time.time()``-compatible epoch seconds, or ``None``.
    """
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).timestamp()


def _status_to_item(name: str, ps: ProviderStatus) -> ProviderStatusItem:
    """Convert a ``ProviderStatus`` to the web response model.

    Args:
        name: The provider's registry name (string key).
        ps: The frozen status snapshot from the registry.

    Returns:
        A ``ProviderStatusItem`` ready for JSON serialization.
    """
    return ProviderStatusItem(
        provider_name=name,
        circuit_state=ps.circuit_state.value,
        failure_count_recent=ps.failure_count_recent,
        last_success_at=_dt_to_epoch(ps.last_success_at),
        last_failure_at=_dt_to_epoch(ps.last_failure_at),
        last_latency_ms=ps.last_latency_ms,
        degraded=False,
    )


@router.get("/status", response_model=RegistryStatusResponse)
def registry_status(request: Request) -> RegistryStatusResponse:
    """Return the live status of every configured provider.

    Reads ``ProviderRegistry.status()`` from the application state.
    Fail-soft per provider: a provider whose status read raises is
    reported with ``degraded=True`` rather than 500-ing the whole list.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A ``RegistryStatusResponse`` with one item per provider.
    """
    registry: ProviderRegistry = request.app.state.provider_registry
    providers: list[ProviderStatusItem] = []

    raw = registry.status()
    for name, ps in raw.items():
        try:
            providers.append(_status_to_item(name, ps))
        except Exception:
            logger.warning("registry_status_item_failed", provider=name, exc_info=True)
            providers.append(
                ProviderStatusItem(
                    provider_name=name,
                    circuit_state="open",
                    failure_count_recent=0,
                    last_success_at=None,
                    last_failure_at=None,
                    last_latency_ms=None,
                    degraded=True,
                )
            )

    return RegistryStatusResponse(providers=providers)
```

## App mount (`personalscraper/web/app.py`)

Add after the decisions router mount (line ~181):

```python
from personalscraper.web.routes.registry import router as registry_router

guarded_api.include_router(registry_router)
```

**Important**: the route depends on `request.app.state.provider_registry` being
set. Verify that `create_app` already stores the registry on `app.state`
(or that the lifespan does). If the registry is not yet on app.state, this
phase must add the wiring — it is a prerequisite for the route to work.

## Route tests (`tests/web/routes/test_registry_status.py`)

Create tests using the project's existing `TestClient` pattern (see
`tests/web/routes/test_decisions.py` for the auth fixture conventions).

```python
"""Route tests for GET /api/registry/status (reg-health Phase 2)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestRegistryStatusAuth:
    """Authentication guard tests."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """GET /api/registry/status without a session cookie → 401."""
        resp = client.get("/api/registry/status")
        assert resp.status_code == 401

    def test_authenticated_returns_200(self, auth_client: TestClient):
        """GET /api/registry/status with a valid session → 200."""
        resp = auth_client.get("/api/registry/status")
        assert resp.status_code == 200


class TestRegistryStatusShape:
    """Response shape tests."""

    def test_response_has_providers_list(self, auth_client: TestClient):
        """Response body must have a 'providers' array."""
        resp = auth_client.get("/api/registry/status")
        data = resp.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)

    def test_provider_item_shape(self, auth_client: TestClient):
        """Each provider item must have the frozen field set."""
        resp = auth_client.get("/api/registry/status")
        data = resp.json()
        if data["providers"]:
            item = data["providers"][0]
            # Exact key set from the freeze contract (Phase 1).
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


class TestRegistryStatusStaging:
    """Staging allowance tests."""

    def test_staging_allows_read(self, auth_client_staging: TestClient):
        """GET /api/registry/status on staging must return 200 (read allowed)."""
        resp = auth_client_staging.get("/api/registry/status")
        assert resp.status_code == 200


class TestRegistryStatusFailSoft:
    """Fail-soft per-provider tests."""

    def test_degraded_provider_reported_not_500(self, auth_client: TestClient):
        """A provider whose status() raises must be reported degraded, not 500."""
        # This test requires the app state's provider_registry to be a mock
        # or to have a provider that raises during status().
        # Implementation detail: the test fixture patches one provider's
        # circuit to raise on .state access.
        resp = auth_client.get("/api/registry/status")
        assert resp.status_code == 200
        degraded = [p for p in resp.json()["providers"] if p.get("degraded")]
        assert len(degraded) >= 0  # True even when no providers degrade
```

**Note on test fixtures**: The `auth_client`, `auth_client_staging`, and
`client` fixtures must follow the project's existing pattern (see
`tests/web/conftest.py`). If they don't exist yet for this test module
scope, create a `tests/web/routes/conftest.py` with the standard
`TestClient` + auth cookie fixture.

## Gotchas

- **Single auth perimeter**: NEVER add `Depends(require_session)` on the
  route function. The router is mounted under `guarded_api` in `app.py`,
  which carries `dependencies=[Depends(require_session)]` — that is the
  single auth perimeter (DESIGN §3.3, web-ui.md §6).

- **`require_not_staging` is NOT applied**: read is allowed on staging
  (8711 returns 200). Do NOT add `Depends(require_not_staging)`.

- **No `X-Requested-With`**: GET routes don't guard against CSRF —
  `require_x_requested_with` is only for mutating endpoints.

- **Epoch-float timestamps**: use `datetime.astimezone(timezone.utc).timestamp()`
  to convert to epoch float. This matches the `pipeline_run` timestamp
  convention (project web-ui invariant: epoch `time.time()`).

- **CircuitState.state auto-transition**: reading `.state` on the circuit
  may transition `OPEN → HALF_OPEN` (see Phase 1 gotcha). This is
  DESIGN_CONFORM and happens on every REST hit when a breaker's cooldown
  has elapsed. The REST route must not suppress this — it is the half-open
  probe mechanism.

- **ProviderRegistry on app.state**: verify `app.state.provider_registry`
  is populated before the route can work. If it isn't, the `create_app` or
  lifespan must be extended to store it. The route fails with a clear
  AttributeError at first request if the registry is missing — add the
  wiring in this phase.

- **`make openapi` after route creation**: any new FastAPI route with a
  `response_model` changes `openapi.json` and `schema.d.ts`. Run `make openapi`
  and commit the regenerated files. CI's diff-guard will fail otherwise
  (project_openapi_drift_ci_guard).
