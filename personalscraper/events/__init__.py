"""Event catalog package — Sub-phase 3.1 onwards.

Eagerly imports every producer module so ``Event.__init_subclass__`` populates
``personalscraper.core.event_bus._EVENT_CLASS_REGISTRY`` at import time. This
guarantees ``event_from_envelope`` can resolve any production event class even
if its declaring module has not been touched by the caller's import graph
(DESIGN §Event catalog).

Phase 3 lands the pipeline events; Phase 4 adds cross-cutting events
(``ItemDispatched``, ``CircuitBreaker*``, ``DiskFullWarning``, …); Phase 5
adds the debug-log subscriber. Each phase appends its producer module to the
import list below.

The public re-export surface mirrors the canonical catalog in
``docs/features/event-bus/DESIGN.md`` (§Event catalog). Importers should
prefer the producer module (e.g. ``from personalscraper.pipeline_events
import StepCompleted``) but the package re-exports are stable.
"""

from __future__ import annotations

# Sub-phase 3.1: eager-import the pipeline events producer module so its
# six event classes are auto-registered before any consumer calls
# ``event_from_envelope``.
from personalscraper import pipeline_events as _pipeline_events  # noqa: F401

# Sub-phase 4.1: eager-import the circuit-breaker events producer module so
# the three CircuitBreaker* classes are registered before consumers call
# ``event_from_envelope``.
from personalscraper.core import circuit as _circuit_events  # noqa: F401
from personalscraper.core.circuit import (
    CircuitBreakerClosed,
    CircuitBreakerHalfOpened,
    CircuitBreakerOpened,
)

# Sub-phase 4.3: eager-import the dispatch events producer module so
# ``ItemDispatched`` is registered before consumers call
# ``event_from_envelope``.
from personalscraper.dispatch import events as _dispatch_events  # noqa: F401
from personalscraper.dispatch.events import ItemDispatched

# Sub-phase 4.2b: eager-import the indexer events producer module so
# ``DiskFullWarning`` (and, from 4.5, ``LibraryScanCompleted``) is
# registered before consumers call ``event_from_envelope``.
from personalscraper.indexer import events as _indexer_events  # noqa: F401
from personalscraper.indexer.events import DiskFullWarning, LibraryScanCompleted
from personalscraper.pipeline_events import (
    ItemProgressed,
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepErrored,
    StepStarted,
)

# Sub-phase 4.4: eager-import the trailers events producer module so
# ``TrailerDownloaded`` is registered before ``event_from_envelope``.
from personalscraper.trailers import events as _trailers_events  # noqa: F401
from personalscraper.trailers.events import TrailerDownloaded

__all__ = [
    "CircuitBreakerClosed",
    "CircuitBreakerHalfOpened",
    "CircuitBreakerOpened",
    "DiskFullWarning",
    "ItemDispatched",
    "ItemProgressed",
    "LibraryScanCompleted",
    "PipelineEnded",
    "PipelineStarted",
    "StepCompleted",
    "StepErrored",
    "StepStarted",
    "TrailerDownloaded",
]
