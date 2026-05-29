"""Leaf type definitions for the provider registry.

This module is a **leaf**: it MUST NOT import from
:mod:`personalscraper.api.metadata.registry` (the package ``__init__``) nor from
any module that does, so that other registry submodules (notably ``_events``)
can import these types at runtime without an import cycle.

It hosts the small value types shared between the registry shell
(``__init__``), the event dataclasses (``_events``), and external callers:

* :data:`RegistryProviderName` — open-string provider identity NewType.
* :class:`ProviderMatch` — ``(provider, id, media_type)`` identifier.
* :class:`AttemptOutcome` — one diagnostic row of a chain/fan-out attempt.

The canonical definitions live here; ``registry/__init__.py`` re-exports them
(explicit ``X as X`` aliases) so the public import path
``from personalscraper.api.metadata.registry import AttemptOutcome, ProviderMatch``
keeps resolving for all existing callers (DESIGN §5.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NewType

from personalscraper.core._contracts import MediaType

# ---------------------------------------------------------------------------
# RegistryProviderName — open-string provider identity for the registry layer
# ---------------------------------------------------------------------------
#
# The project uses TWO distinct provider-name types at different architectural
# layers.  This is intentional — see DESIGN §5.3 "Provider name dual surface"
# (Option B, sub-phase 8.4) for the full rationale.
#
# ``personalscraper.api._contracts.ProviderName``
#     A closed ``str``-Enum of the real providers known to the transport-config
#     world: TMDB, TVDB, OMDB, TRAKT, QBITTORRENT, TRANSMISSION, LACALE, C411,
#     TELEGRAM, HEALTHCHECKS.  Code that builds ``Settings``, constructs an
#     ``HttpTransport``, or dispatches on a fixed provider family uses this Enum.
#
# ``RegistryProviderName`` (defined below)
#     An open ``NewType`` over ``str`` for the registry layer.  The registry is a
#     capability-keyed dispatch framework that accepts **any** provider name
#     appearing in user config (``config/providers.json5``) — including names
#     that do not correspond to a transport-layer provider, such as synthetic
#     test fixtures (``"multi"``, ``"xref"``).  A closed Enum would be too
#     restrictive here: the registry does not own the valid-name set; user
#     config does.
#
# Boundary rule:
#     - Transport contracts, settings, HTTP policy → ``_contracts.ProviderName`` Enum.
#     - Registry dispatch, provider iteration, introspection → ``RegistryProviderName`` NewType.
#
# The two coexist by design — the registry is layered *above* transport.
#
# Historical note: sub-phase 5.2 of the registry tech-debt sweep discovered
# that both types were originally named ``ProviderName`` (once as Enum, once as
# NewType), causing silent type aliasing because ``str``-Enum subclasses
# ``str``.  After a cycle-1 review, the types were separated and the comment
# block expanded (sub-phase 8.4, Option B).  Moved into this leaf module in
# arch-cleanup-2 Phase 5 to break the ``_events`` runtime-import cycle.
# ---------------------------------------------------------------------------

RegistryProviderName = NewType("RegistryProviderName", str)


@dataclass(frozen=True)
class ProviderMatch:
    """Identifies a media item by (provider, id) pair.

    Invariants enforced in ``__post_init__``: ``provider`` and ``id`` must be
    non-empty. The registry validates that ``provider`` corresponds to a
    configured provider at every call site that accepts a ``ProviderMatch``.
    """

    provider: RegistryProviderName
    id: str
    media_type: MediaType

    def __post_init__(self) -> None:
        """Validate non-empty provider and id after frozen dataclass init."""
        if not self.provider:
            raise ValueError("ProviderMatch.provider must be non-empty")
        if not self.id:
            raise ValueError("ProviderMatch.id must be non-empty")


@dataclass(frozen=True)
class AttemptOutcome:
    """One row of ``ProviderExhausted.attempted`` — used for diagnostics and metrics.

    ``reason`` is a closed ``Literal`` so downstream consumers (ScrapeResult,
    metrics, EventBus event payloads) can dispatch on a stable enum, not
    free-form strings.
    """

    provider: RegistryProviderName
    reason: Literal["circuit_open", "network", "empty_result", "other"]
    detail: str | None = None
