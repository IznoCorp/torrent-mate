"""In-process typed event bus.

Single substrate for cross-component asynchronous communication:

- ``Event`` frozen base + ``current_correlation_id`` ContextVar.
- ``SubscriptionToken`` + ``EventBus.subscribe`` / ``unsubscribe`` (COW).
- ``EventBus.emit`` — MRO-walking dispatch, MRO cache, fast path.
- per-subscriber try/except, ``event_emit_failed`` WARNING, snapshot
  iteration (re-entrant subscribe/unsubscribe/emit are all safe).
- ``event_to_dict`` pure-payload JSON-safe encoder.
- ``event_to_envelope`` / ``event_from_envelope`` + class registry
  (auto-populated via ``Event.__init_subclass__``, module-path filtered).

See ``docs/reference/event-bus.md`` for the public API.
"""

from __future__ import annotations

import dataclasses
import itertools
import types
import typing
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePath
from typing import Any, TypeVar, get_args, get_origin
from uuid import UUID, uuid4

from personalscraper.logger import get_logger

# ---------------------------------------------------------------------------
# Event class registry (1.6) — populated by Event.__init_subclass__
# ---------------------------------------------------------------------------
# Indexed by class name (e.g. "PipelineStarted"). Filtered by module path so
# test stubs defined in tests/* do NOT pollute the production registry
# (Invariant 9). Public re-exports for tests live below in __all__.
_EVENT_CLASS_REGISTRY: dict[str, type] = {}

# Both Union origins must be recognized: ``typing.Union[X, None]`` (PEP 484)
# and ``X | None`` (PEP 604) produce different ``get_origin`` results — the
# former returns ``typing.Union``, the latter ``types.UnionType``. Treating
# only one form silently broke datetime / dataclass round-trip whenever a
# field used the modern ``X | None`` syntax (PEP 604).
_UNION_ORIGINS: tuple[Any, ...] = (typing.Union, types.UnionType)

# Module-path prefix considered "production" for registry inclusion.
_PRODUCTION_MODULE_PREFIX = "personalscraper."

# Module-level structlog binding — used to log subscriber failures (1.4).
# Imported once at module load time; ``get_logger`` returns a bound logger
# that includes the module name as a context field.
_log = get_logger(__name__)


def _decode_field_value(value: Any, annotation: Any) -> Any:
    """Inverse of ``event_to_dict`` — walk ``annotation`` to coerce ``value``."""
    if value is None:
        return None
    origin = get_origin(annotation)
    if origin in _UNION_ORIGINS:
        # ``X | None`` → pick the non-None member for non-None values.
        # Covers both PEP 484 (``typing.Union[X, None]``) and PEP 604
        # (``X | None``) — see ``_UNION_ORIGINS`` rationale at module top.
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return _decode_field_value(value, non_none[0])
        return value
    if origin in (list, tuple):
        (item_type,) = get_args(annotation) or (Any,)
        decoded = [_decode_field_value(item, item_type) for item in value]
        return tuple(decoded) if origin is tuple else decoded
    if origin is dict:
        args = get_args(annotation)
        val_type: Any = args[1] if len(args) == 2 else Any
        return {k: _decode_field_value(v, val_type) for k, v in value.items()}
    if annotation is datetime:
        return datetime.fromisoformat(value)
    if annotation is UUID:
        return UUID(value)
    if isinstance(annotation, type):
        if issubclass(annotation, PurePath):
            # Always reconstruct as Path (OS-aware) regardless of subclass.
            return Path(value)
        if issubclass(annotation, Enum):
            return annotation(value)
        if dataclasses.is_dataclass(annotation):
            sub_hints = typing.get_type_hints(annotation)
            kw = {f.name: _decode_field_value(value[f.name], sub_hints[f.name]) for f in fields(annotation)}
            return annotation(**kw)
    return value  # primitives / Any pass through


def event_to_envelope(event: Event) -> dict[str, Any]:
    """Wrap ``event`` in a tagged envelope ``{"_type", "data"}``."""
    return {"_type": type(event).__name__, "data": event_to_dict(event)}


def event_from_envelope(envelope: dict[str, Any]) -> Event:
    """Reconstruct an ``Event`` from its tagged envelope.

    Raises ``KeyError`` (fail-loud) if ``envelope["_type"]`` is unknown.
    """
    type_name = envelope["_type"]
    cls = _EVENT_CLASS_REGISTRY.get(type_name)
    if cls is None:
        raise KeyError(f"Unknown event type: {type_name!r}")
    # typing.get_type_hints walks the MRO and uses each class's own module
    # globals, so inherited Event fields resolve correctly (e.g. event_id:
    # UUID resolves via core/event_bus.py even when cls lives in a test).
    hints = typing.get_type_hints(cls)
    data = envelope["data"]
    kwargs = {f.name: _decode_field_value(data[f.name], hints[f.name]) for f in fields(cls)}
    instance = cls(**kwargs)
    # Narrow type — the registry only ever stores Event subclasses.
    assert isinstance(instance, Event)
    return instance


# JSON-safe encoder (1.5) — rules per DESIGN §JSON serialization contract:
# datetime→ISO 8601, UUID→str, PurePath→str, Enum→value, dataclass→{field:
# encoded(value)}, list/tuple→list, dict→dict (str keys only — int/float/bool
# would round-trip back as strings, so the decoder cannot recover the key
# type. Reject them at encode time rather than corrupting silently),
# primitives unchanged. Anything else raises TypeError (fail-loud).


def event_to_dict(value: Any) -> Any:
    """Recursively encode ``value`` to JSON-safe primitives (see contract above).

    Args:
        value: Any value reachable from an :class:`Event` field.

    Returns:
        A JSON-safe representation: ``None`` / ``bool`` / ``int`` / ``float`` /
        ``str`` pass through; ``datetime`` becomes an ISO 8601 string;
        ``UUID`` / ``PurePath`` become strings; ``Enum`` becomes its ``.value``;
        dataclasses become nested ``dict[str, Any]``; lists / tuples become
        lists; dicts become dicts with ``str`` keys.

    Raises:
        TypeError: When *value* (or any nested value) is not JSON-safe, or
            when a dict contains a non-string key (the decoder cannot recover
            the original key type after a JSON round-trip).
    """
    # bool checked before int (bool is a subclass of int in CPython).
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: event_to_dict(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [event_to_dict(item) for item in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, val in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Cannot encode dict key of type {type(key).__name__} "
                    f"for JSON serialization (only str keys are allowed; the "
                    f"decoder cannot recover non-string key types after JSON "
                    f"round-trip).",
                )
            out[key] = event_to_dict(val)
        return out
    raise TypeError(
        f"Cannot encode {type(value).__name__} for JSON serialization (value: {value!r})",
    )


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
# event*: emit does not re-read the ContextVar (verified by the tests in
# ``tests/event_bus/test_correlation_id.py``).
#
# Default ``None`` means "no correlation id" — events constructed outside any
# bound region are still valid and carry ``correlation_id=None``.
current_correlation_id: ContextVar[str | None] = ContextVar(
    "current_correlation_id",
    default=None,
)


@dataclass(frozen=True, kw_only=True)
class Event:
    """Base class for every typed event in the system.

    Concrete events inherit from ``Event`` and add their own typed fields.
    Subclasses are auto-registered by ``__init_subclass__`` and each must
    remain a ``@dataclass(frozen=True, kw_only=True)``.

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

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-register concrete subclasses in ``_EVENT_CLASS_REGISTRY``.

        Filtered by module path: only classes whose ``__module__`` starts with
        ``personalscraper.`` are registered. Test stubs defined under
        ``tests.*`` are excluded so the registry size stays equal to the
        production catalog count regardless of pytest collection order
        (Invariant 9). ``Event`` itself is NOT registered because
        ``__init_subclass__`` only fires for subclasses.
        """
        super().__init_subclass__(**kwargs)
        if cls.__module__.startswith(_PRODUCTION_MODULE_PREFIX):
            _EVENT_CLASS_REGISTRY[cls.__name__] = cls

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe payload form of this event.

        Thin alias for module-level ``event_to_dict(self)`` — provided as a
        method for ergonomic ``event.to_dict()`` calls in subscriber code.
        ``event_to_envelope`` layers a ``{"_type", "data"}`` tag on top
        for cross-process / Web-UI consumers.

        Returns:
            A ``dict`` of JSON-safe primitives (the recursive encoding of
            every dataclass field via ``event_to_dict``).
        """
        # ``event_to_dict`` returns ``Any`` because its recursive contract
        # spans many shapes (dict, list, str, int, …); for any ``Event``
        # subclass (a dataclass) the encoder always lands in the dataclass
        # branch and returns a dict[str, Any] — narrow the type here.
        encoded = event_to_dict(self)
        assert isinstance(encoded, dict)
        return encoded


# ---------------------------------------------------------------------------
# Subscription tokens
# ---------------------------------------------------------------------------
# Tokens are opaque handles returned by ``EventBus.subscribe``. They carry the
# minimum data needed to identify a subscription for ``unsubscribe``: a
# process-unique integer id and the event type the subscription is bound to.
# A frozen dataclass gives us ``__eq__`` / ``__hash__`` for free, plus protects
# the internal id from accidental mutation by callers.
_token_id_counter = itertools.count(1)


@dataclass(frozen=True)
class SubscriptionToken:
    """Opaque handle for a single subscription, returned by ``EventBus.subscribe``.

    Attributes:
        _id: Process-monotonic integer assigned at creation time. Underscore
            prefix marks it as internal; callers MUST treat the token as opaque
            and only use it as the argument to ``EventBus.unsubscribe``.
        event_type: The ``Event`` subclass this subscription is bound to.
            Stored on the token so a future ``unsubscribe`` can locate the
            subscriber tuple in ``EventBus._subscribers`` without a full scan.
    """

    _id: int
    event_type: type[Event]


# EventBus storage: dict[type[Event], tuple[(SubscriptionToken, Callable), ...]].
# The inner tuple is rebuilt on every subscribe/unsubscribe (copy-on-write),
# so emit can safely iterate a captured snapshot under re-entrancy.
_SubscriberEntry = tuple[SubscriptionToken, Callable[[Event], None]]

# Bound TypeVar so ``EventBus.subscribe`` can express "the callback receives
# the same concrete subclass passed as ``event_type``". This removes the
# need for ``# type: ignore[arg-type]`` at every concrete subscriber call
# site (e.g. ``bus.subscribe(StepStarted, self._on_step_started)``).
E = TypeVar("E", bound="Event")


class EventBus:
    """In-process typed event bus — single-process, single-thread by design.

    Per-asyncio-task isolation comes from ``current_correlation_id``
    (a ContextVar), not from any locking inside the bus.
    """

    def __init__(self) -> None:
        """Initialize an empty subscriber registry and MRO cache."""
        self._subscribers: dict[type[Event], tuple[_SubscriberEntry, ...]] = {}
        # MRO cache: cleared wholesale on subscribe/unsubscribe — cheap rebuild
        # on next emit per-type, vs. tracking dependent entries.
        self._mro_cache: dict[type[Event], tuple[Callable[[Event], None], ...]] = {}

    def subscribe(
        self,
        event_type: type[E],
        callback: Callable[[E], None],
    ) -> SubscriptionToken:
        """Register *callback* against *event_type*; return a token for later ``unsubscribe``.

        Generic in ``E`` so mypy infers that ``callback`` receives the same
        concrete subclass passed as ``event_type``. This removes the need
        for ``# type: ignore[arg-type]`` at concrete subscriber call sites.

        Subscriber-of-base semantics (subscribing to ``Event`` catches every
        concrete subclass) lives in ``emit``'s MRO walk.

        Args:
            event_type: The ``Event`` subclass to listen for.
            callback: A callable receiving an instance of ``event_type``.

        Returns:
            An opaque :class:`SubscriptionToken` for ``unsubscribe``.
        """
        token = SubscriptionToken(_id=next(_token_id_counter), event_type=event_type)
        # Copy-on-write: previous tuple stays untouched for any in-flight emit.
        existing = self._subscribers.get(event_type, ())
        # Cast to the wider ``Callable[[Event], None]`` for storage — emit
        # only ever invokes callbacks with the concrete subclass instance
        # the generic narrowed them to, so the dispatch is sound.
        wider: Callable[[Event], None] = callback  # type: ignore[assignment]
        self._subscribers[event_type] = (*existing, (token, wider))
        self._mro_cache.clear()
        return token

    def unsubscribe(self, token: SubscriptionToken) -> None:
        """Remove the subscription identified by ``token`` (idempotent no-op if absent)."""
        existing = self._subscribers.get(token.event_type)
        if not existing:
            return
        # Rebuild the tuple without any entry whose token matches.
        # We compare on the token's _id (the process-monotonic counter value)
        # because dataclass __eq__ also matches on event_type (already known
        # to match here via the dict key); _id alone is the unique identifier.
        filtered = tuple(
            entry
            for entry in existing
            if entry[0]._id != token._id  # noqa: SLF001
        )
        if len(filtered) == len(existing):
            # Token not found in the current tuple — already-unsubscribed or
            # never-subscribed. Idempotent no-op.
            return
        if filtered:
            self._subscribers[token.event_type] = filtered
        else:
            # No subscribers left for this type — drop the dict key entirely
            # so the empty-bus fast path in ``emit`` stays effective.
            del self._subscribers[token.event_type]
        # Invalidate the MRO cache wholesale — the removed subscriber may
        # have been resolved into multiple cache entries via MRO walks.
        self._mro_cache.clear()

    def emit(self, event: Event) -> None:
        """Dispatch ``event`` to every subscriber whose type appears in its MRO.

        Dispatch ordering: concrete-type subscribers fire before ancestor
        subscribers (DESIGN §Dispatch semantics #5). Multiple subscribers of
        the same type fire in subscription order (FIFO).

        Fast path: when there are no subscribers at all (``self._subscribers``
        is the empty dict), this method returns after a single ``if`` check
        with zero allocations inside ``event_bus.py`` (DESIGN §Performance
        notes — verified by ``test_emit_no_subscribers_zero_allocation``).

        Error isolation: each callback invocation is wrapped in
        ``try/except`` so a misbehaving subscriber never breaks dispatch
        to the others (see the loop below).

        Args:
            event: The ``Event`` instance to dispatch.
        """
        # Fast path: empty registry → return immediately. ``not self._subscribers``
        # is True for the empty dict; the check itself is the only operation.
        if not self._subscribers:
            return
        event_type = type(event)
        callbacks = self._mro_cache.get(event_type)
        if callbacks is None:
            callbacks = self._resolve_mro_chain(event_type)
            # Memoize even when empty — emitting a type with no relevant
            # subscribers is still cheap on subsequent calls.
            self._mro_cache[event_type] = callbacks
        # Iterate the captured tuple snapshot. ``callbacks`` is an immutable
        # tuple, so any subscribe/unsubscribe a handler performs (which clears
        # ``_mro_cache`` and replaces an entry in ``_subscribers``) does NOT
        # mutate this local — the current emit always sees the snapshot taken
        # at dispatch start. This is the entire re-entrancy contract.
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                # Error isolation: a failing subscriber MUST NOT break dispatch
                # to the others. ``RecursionError`` is a subclass of
                # ``Exception`` and is therefore caught here too — the bus
                # documents that subscribers must not subscribe to their own
                # emit type (DESIGN §Dispatch semantics #4).
                _log.warning(
                    "event_emit_failed",
                    subscriber=getattr(callback, "__name__", repr(callback)),
                    event_type=type(event).__name__,
                    event_id=str(event.event_id),
                    exc_info=True,
                )

    def _resolve_mro_chain(
        self,
        event_type: type[Event],
    ) -> tuple[Callable[[Event], None], ...]:
        """Build the dispatch tuple for ``event_type`` by walking its MRO.

        Walks ``event_type.__mro__`` in order (concrete → ancestor) and
        concatenates the subscriber callbacks for every class in the chain
        that has registered subscribers. The result is *order-stable*: for a
        single class, subscribers fire in subscription (FIFO) order; across
        classes, concrete fires before ancestor.

        Args:
            event_type: The concrete event class being emitted.

        Returns:
            A tuple of callbacks in dispatch order, possibly empty.
        """
        chain: list[Callable[[Event], None]] = []
        for cls in event_type.__mro__:
            entries = self._subscribers.get(cls)
            if entries:
                # Each entry is (token, callback); we only need the callback.
                chain.extend(callback for _token, callback in entries)
        return tuple(chain)


__all__ = [
    "UTC",
    "Event",
    "EventBus",
    "SubscriptionToken",
    "current_correlation_id",
    "event_from_envelope",
    "event_to_dict",
    "event_to_envelope",
]
