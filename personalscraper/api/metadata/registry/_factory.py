"""Provider factory — name-to-class resolution and instantiation (DESIGN §6.1).

Each builder function handles one provider's specific constructor shape.
IMDbClient and RottenTomatoesClient share a single OMDbAdapter backend so
rate-limit and circuit-breaker budgets stay consolidated (DESIGN §4).
"""

from __future__ import annotations

import importlib
import os
from typing import TYPE_CHECKING, Any, Callable, cast

from personalscraper.api.metadata.registry._errors import UnknownProviderError
from personalscraper.logger import get_logger

log = get_logger("registry.factory")

if TYPE_CHECKING:
    from personalscraper.api.transport._policy import CircuitPolicy
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus

# ---------------------------------------------------------------------------
# Provider class registry (dotted-path strings — lazy import means missing
# optional deps do not break import-time).
# ---------------------------------------------------------------------------

PROVIDER_CLASSES: dict[str, str] = {
    "tmdb": "personalscraper.api.metadata.tmdb:TMDBClient",
    "tvdb": "personalscraper.api.metadata.tvdb:TVDBClient",
    "imdb": "personalscraper.api.metadata.imdb:IMDbClient",
    "omdb": "personalscraper.api.metadata.omdb:OMDbAdapter",
    "trakt": "personalscraper.api.metadata.trakt:TraktClient",
    "rotten_tomatoes": "personalscraper.api.metadata.rotten_tomatoes:RottenTomatoesClient",
}


def resolve_provider_class(name: str) -> type:
    """Import and return the provider class for *name*.

    Args:
        name: Provider name key (e.g. ``"tmdb"``).

    Returns:
        The provider class.

    Raises:
        UnknownProviderError: If *name* is not in ``PROVIDER_CLASSES``.
        ImportError: If the module or class cannot be imported (propagated).
    """
    dotted = PROVIDER_CLASSES.get(name)
    if dotted is None:
        raise UnknownProviderError(name)
    module_path, _, class_name = dotted.partition(":")
    module = importlib.import_module(module_path)
    return cast(type, getattr(module, class_name))


# ---------------------------------------------------------------------------
# Per-provider builder helpers
# ---------------------------------------------------------------------------


def _build_tmdb(
    settings: Settings,
    cb_policy: CircuitPolicy,
    event_bus: EventBus,
    **_kwargs: Any,
) -> object:
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.api.transport._http import HttpTransport

    tmdb_policy = TMDBClient.policy(settings.tmdb_api_key, circuit=cb_policy)
    tmdb_transport = HttpTransport(tmdb_policy, event_bus=event_bus)
    return TMDBClient(tmdb_transport, language="fr-FR")


def _build_tvdb(
    settings: Settings,
    cb_policy: CircuitPolicy,
    event_bus: EventBus,
    **_kwargs: Any,
) -> object:
    from personalscraper.api.metadata.tvdb import TVDBClient

    return TVDBClient(
        settings.tvdb_api_key,
        language="fr-FR",
        circuit=cb_policy,
        event_bus=event_bus,
    )


def _build_omdb(
    settings: Settings,
    cb_policy: CircuitPolicy,
    event_bus: EventBus,
    **_kwargs: Any,
) -> object:
    from personalscraper.api.metadata.omdb import OMDbAdapter
    from personalscraper.api.transport._http import HttpTransport

    key = os.environ.get("OMDB_API_KEY", "")
    policy = OMDbAdapter.policy(key)
    transport = HttpTransport(policy, event_bus=event_bus)
    return OMDbAdapter(transport)


def _build_imdb(
    settings: Settings,
    cb_policy: CircuitPolicy,
    event_bus: EventBus,
    *,
    _cache: dict[str, object] | None = None,
    **_kwargs: Any,
) -> object:
    from personalscraper.api.metadata.imdb import IMDbClient
    from personalscraper.api.metadata.omdb import OMDbAdapter

    if _cache is not None and "omdb" in _cache:
        omdb = cast(OMDbAdapter, _cache["omdb"])
    else:
        omdb = cast(OMDbAdapter, _build_omdb(settings, cb_policy, event_bus))
        if _cache is not None:
            _cache["omdb"] = omdb
    return IMDbClient(omdb)


def _build_rotten_tomatoes(
    settings: Settings,
    cb_policy: CircuitPolicy,
    event_bus: EventBus,
    *,
    _cache: dict[str, object] | None = None,
    **_kwargs: Any,
) -> object:
    from personalscraper.api.metadata.omdb import OMDbAdapter
    from personalscraper.api.metadata.rotten_tomatoes import RottenTomatoesClient

    if _cache is not None and "omdb" in _cache:
        omdb = cast(OMDbAdapter, _cache["omdb"])
    else:
        omdb = cast(OMDbAdapter, _build_omdb(settings, cb_policy, event_bus))
        if _cache is not None:
            _cache["omdb"] = omdb
    return RottenTomatoesClient(omdb)


def _build_trakt(
    settings: Settings,
    cb_policy: CircuitPolicy,
    event_bus: EventBus,
    **_kwargs: Any,
) -> object:
    from personalscraper.api.metadata.trakt import TraktClient
    from personalscraper.api.transport._http import HttpTransport

    key = os.environ.get("TRAKT_CLIENT_ID", "")
    policy = TraktClient.policy(key)
    transport = HttpTransport(policy, event_bus=event_bus)
    return TraktClient(transport)


# ---------------------------------------------------------------------------
# Builder registry (name → callable)
# ---------------------------------------------------------------------------

_BUILDERS: dict[str, Callable[..., object]] = {
    "tmdb": _build_tmdb,
    "tvdb": _build_tvdb,
    "imdb": _build_imdb,
    "omdb": _build_omdb,
    "trakt": _build_trakt,
    "rotten_tomatoes": _build_rotten_tomatoes,
}


def build_providers(
    provider_names: list[str],
    settings: Settings,
    cb_policy: CircuitPolicy,
    event_bus: EventBus,
) -> dict[str, object]:
    """Instantiate each named provider once. Returns ``name → instance`` dict.

    IMDb and RottenTomatoes share a single OMDbAdapter backend so their
    rate-limit and circuit-breaker budgets stay consolidated (DESIGN §4).

    Does NOT catch exceptions — the caller (registry ``__init__``) wraps
    with ``try/finally`` + cleanup.

    Args:
        provider_names: Provider names to instantiate.
        settings: The pipeline ``Settings`` for credentials.
        cb_policy: Shared ``CircuitPolicy`` for non-TMDB providers.
        event_bus: ``EventBus`` for transport instrumentation.

    Returns:
        Dict mapping ``{name: instance}`` for each requested provider.
    """
    _backend_cache: dict[str, object] = {}
    providers: dict[str, object] = {}
    for name in provider_names:
        builder = _BUILDERS[name]
        providers[name] = builder(
            settings,
            cb_policy,
            event_bus,
            _cache=_backend_cache,
        )
    return providers


# ---------------------------------------------------------------------------
# Eligibility gate
# ---------------------------------------------------------------------------

_NO_CIRCUIT_ALLOWLIST: frozenset[str] = frozenset({
    "imdb",            # façade over shared OMDbAdapter circuit
    "rotten_tomatoes", # façade over shared OMDbAdapter circuit
})


def _eligible(provider: object) -> bool:
    """Return ``True`` if the provider's circuit is CLOSED or HALF_OPEN.

    HALF_OPEN eligibility (DESIGN §7.6): a provider is eligible if its
    circuit is CLOSED OR HALF_OPEN.  The HALF_OPEN state acts as a probe
    — the underlying HttpTransport lets one request through; if it fails,
    the transport raises NetworkError which the registry catches and falls
    through to the next provider in the same iteration.

    Providers without a ``.circuit`` attribute fall into three categories,
    only two of which are accepted:

    1. **Documented no-circuit providers** (IMDb / RottenTomatoes façades
       whose circuit lives on the shared OMDbAdapter backend) — allowed.
    2. **Test fakes** (classes named ``Fake*`` or ``_Fake*``) — allowed.
    3. **Unknown real provider without circuit** — rejected with a warning,
       catching refactor regressions where ``.circuit`` was accidentally
       dropped.
    """
    circuit = getattr(provider, "circuit", None)
    if circuit is not None:
        state = getattr(circuit, "state", None)
        return state != "OPEN"

    name = getattr(provider, "provider_name", None)
    if name in _NO_CIRCUIT_ALLOWLIST:
        return True

    cls_name = type(provider).__name__
    if cls_name.startswith(("Fake", "_Fake")):
        return True

    log.warning(
        "registry_provider_no_circuit",
        provider=name or "<unknown>",
        cls=cls_name,
    )
    return False
