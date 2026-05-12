"""Event catalog package.

Eagerly imports every producer module so ``Event.__init_subclass__`` populates
``personalscraper.core.event_bus._EVENT_CLASS_REGISTRY`` at import time. This
guarantees ``event_from_envelope`` can resolve any production event class even
if its declaring module has not been touched by the caller's import graph
(DESIGN §Event catalog).

The public re-export surface mirrors the canonical catalog in
``docs/features/event-bus/DESIGN.md`` (§Event catalog). Importers should
prefer the producer module (e.g. ``from personalscraper.pipeline_events
import StepCompleted``) but the package re-exports are stable.
"""

from __future__ import annotations

# Eager-import every producer module so each event class is auto-registered
# by ``Event.__init_subclass__`` before any consumer calls
# ``event_from_envelope``.
from personalscraper import pipeline_events as _pipeline_events  # noqa: F401
from personalscraper.core import circuit as _circuit_events  # noqa: F401
from personalscraper.core.circuit import (
    CircuitBreakerClosed,
    CircuitBreakerHalfOpened,
    CircuitBreakerOpened,
)
from personalscraper.dispatch import events as _dispatch_events  # noqa: F401
from personalscraper.dispatch.events import ItemDispatched
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
