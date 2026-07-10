"""Registry health REST route (reg-health feature).

A single read-only endpoint under ``/api/registry/`` that serves the
last-known per-provider health state derived from the event-stream
projection, merged with the configured provider roster so every known
provider renders even before its first event.

See docs/features/reg-health/DESIGN.md §3.3 and plan phase-02-rest-route.md §2.2.
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request

from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.logger import get_logger
from personalscraper.web.models.registry import ProviderStatusItem, RegistryStatusResponse

router = APIRouter(prefix="/api/registry", tags=["registry"])
logger = get_logger(__name__)


def _build_roster(providers_config: ProvidersConfig) -> set[str]:
    """Collect every provider name referenced in any capability section.

    Iterates over all sections of *providers_config* (each a
    ``dict[str, int]`` of provider_name → priority) and returns the union
    of their keys.

    Args:
        providers_config: The parsed providers configuration
            (``config.providers``).

    Returns:
        A set of provider name strings configured across all capability
        sections.
    """
    roster: set[str] = set()
    for section in providers_config.model_dump().values():
        if isinstance(section, dict):
            roster.update(section.keys())
    return roster


@router.get("/status", response_model=RegistryStatusResponse)
def registry_status(request: Request) -> RegistryStatusResponse:
    """Return the last-known health state for every provider.

    Reads the in-memory :class:`RegistryHealthProjection` (fed by the
    Redis event stream relay + boot warm-up replay) and merges it with
    the configured provider roster so that a provider with no event history
    still renders with an optimistic baseline (``circuit_state="closed"``,
    zero ``failure_count_recent``, all timestamps ``None``, ``live=False``).

    Fail-soft: any error reading the projection or config returns an empty
    provider list rather than a 500.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A :class:`RegistryStatusResponse` with one item per configured or
        observed provider, sorted by ``provider_name``.
    """
    try:
        snapshot = request.app.state.registry_projection.snapshot()
        roster = _build_roster(
            cast(ProvidersConfig, request.app.state.config.providers),
        )
    except Exception:
        logger.warning("registry_status_read_failed", exc_info=True)
        return RegistryStatusResponse(providers=[])

    providers: list[ProviderStatusItem] = []

    # 1. Roster providers: use projection state when observed, else baseline.
    for name in roster:
        if name in snapshot:
            entry = snapshot[name]
            providers.append(
                ProviderStatusItem(
                    provider_name=name,
                    circuit_state=entry["circuit_state"],
                    failure_count_recent=entry["failure_count_recent"],
                    last_success_at=entry.get("last_success_at"),
                    last_failure_at=entry.get("last_failure_at"),
                    last_latency_ms=entry.get("last_latency_ms"),
                    live=True,
                )
            )
        else:
            providers.append(
                ProviderStatusItem(
                    provider_name=name,
                    circuit_state="closed",
                    failure_count_recent=0,
                    last_success_at=None,
                    last_failure_at=None,
                    last_latency_ms=None,
                    live=False,
                )
            )

    # 2. Projection-only providers (observed but not in the roster).
    for name, entry in snapshot.items():
        if name not in roster:
            providers.append(
                ProviderStatusItem(
                    provider_name=name,
                    circuit_state=entry["circuit_state"],
                    failure_count_recent=entry["failure_count_recent"],
                    last_success_at=entry.get("last_success_at"),
                    last_failure_at=entry.get("last_failure_at"),
                    last_latency_ms=entry.get("last_latency_ms"),
                    live=True,
                )
            )

    providers.sort(key=lambda p: p.provider_name)
    return RegistryStatusResponse(providers=providers)
