"""In-process typed event bus — Sub-phase 1.1 scaffold.

This module is the single substrate for cross-component asynchronous
communication in PersonalScraper. Sub-phase 1.1 introduces only:

- ``current_correlation_id``: module-level ``ContextVar`` for run/job tagging.
- ``Event``: frozen dataclass base for every concrete event type.

Subsequent sub-phases extend this module with ``SubscriptionToken``,
``EventBus``, JSON serialization helpers, and the event class registry.
The module-level docstring will be expanded as those layers land — see
``docs/features/event-bus/plan/phase-01-foundation.md``.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

# Local alias matches the convention used elsewhere in the codebase
# (e.g. ``personalscraper.trailers.state``, ``personalscraper.scraper.json_ttl_cache``).
# We re-alias rather than ``from datetime import UTC`` so the module remains
# import-clean on Python 3.10 (per ``pyproject.toml`` ``requires-python = ">=3.10"``);
# the ``datetime.UTC`` alias only became importable in Python 3.11.
UTC = timezone.utc

# ---------------------------------------------------------------------------
# Correlation-id ContextVar
# ---------------------------------------------------------------------------
# A pipeline run, indexer scan, or trailer-CLI invocation binds this ContextVar
# at its outer boundary so every ``Event`` constructed inside that bound region
# captures the correlation id at construction time. The value is *frozen on the
# event*: emit does not re-read the ContextVar (see Sub-phase 1.7 tests).
#
# Default ``None`` means "no correlation id" — events constructed outside any
# bound region are still valid and carry ``correlation_id=None``.
current_correlation_id: ContextVar[str | None] = ContextVar(
    "current_correlation_id",
    default=None,
)


@dataclass(frozen=True)
class Event:
    """Base class for every typed event in the system.

    Concrete events inherit from ``Event`` and add their own typed fields.
    Subclasses are auto-registered by ``__init_subclass__`` (added in
    Sub-phase 1.6) and each must remain a ``@dataclass(frozen=True)``.

    Attributes:
        timestamp: UTC-aware construction time (default: ``datetime.now(UTC)``).
        source: Origin tag, e.g. ``"personalscraper.pipeline.PipelineStarted"``.
            Auto-derived in ``__post_init__`` from ``f"{cls.__module__}.{cls.__name__}"``
            when the caller passes ``source=""`` (the default). Explicit non-empty
            values are respected.
        event_id: Per-instance UUID — unique across the process lifetime.
        correlation_id: Snapshot of ``current_correlation_id`` at construction
            time. ``None`` when constructed outside any bound region. An explicit
            argument (including explicit ``None``) wins over the ContextVar.
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: str | None = field(
        default_factory=lambda: current_correlation_id.get(),
    )

    def __post_init__(self) -> None:
        """Auto-derive ``source`` when empty.

        Uses ``object.__setattr__`` because the dataclass is ``frozen=True``;
        in ``__post_init__`` this is the canonical pattern documented in PEP 557
        for one-shot derived defaults.
        """
        if not self.source:
            cls = type(self)
            object.__setattr__(self, "source", f"{cls.__module__}.{cls.__name__}")


__all__ = [
    "Event",
    "current_correlation_id",
]
