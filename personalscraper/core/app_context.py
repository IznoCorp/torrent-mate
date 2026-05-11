"""Process-scoped service bundle — Sub-phase 2.1.

``AppContext`` is the long-lived service container constructed once per
process at the system boundary (CLI entry, launchd scan entry, future Web UI
or Watcher boot). It carries the three services that EVERY pipeline run,
indexer scan, or trailer-CLI invocation needs: ``config`` (the typed JSON5
configuration), ``settings`` (Pydantic env-var settings), and ``event_bus``
(the in-process EventBus from Sub-phase 1.2/1.3).

**Boundary-only rule** (DESIGN.md §Architecture, codified by the AST test
landed in Sub-phase 2.6): internal components MUST NOT receive AppContext
"for convenience". Inject the specific services they need (a ``Config``, a
single ``MetadataClient``, etc.) — never the whole bundle. The allowlist of
authorized boundary modules lives in
``tests/architecture/test_app_context_boundary.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Imported under TYPE_CHECKING to avoid a circular import: ``config`` and
    # ``Settings`` may transitively import modules that reach back here as
    # the AppContext usage spreads in Phase 2.2/2.3. The frozen dataclass
    # stores them by reference; the runtime never inspects their types.
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus


@dataclass(frozen=True)
class AppContext:
    """Long-lived process-scoped service bundle.

    Constructed exactly once per process at the system boundary. Frozen
    because the bundle's identity is part of every event's correlation
    context — swapping a service mid-process would break invariants that
    later phases (subscribers, AST boundary test) rely on.

    Attributes:
        config: The typed JSON5 configuration loaded at boundary.
        settings: The Pydantic env-var settings (API keys, paths).
        event_bus: The in-process ``EventBus`` for cross-component events.

    Future v2 additions (NOT in scope for the event-bus feature):
        provider_registry, service_container — see ROADMAP.md.
    """

    config: Config
    settings: Settings
    event_bus: EventBus


__all__ = ["AppContext"]
