"""In-process typed event bus — Sub-phase 1.5 layer.

This module is the single substrate for cross-component asynchronous
communication in PersonalScraper. Layers landed so far:

- 1.1: ``Event`` frozen base + ``current_correlation_id`` ContextVar.
- 1.2: ``SubscriptionToken`` + ``EventBus.subscribe`` / ``unsubscribe`` with
       copy-on-write subscriber storage.
- 1.3: ``EventBus.emit`` with MRO-walking dispatch, an MRO cache, and the
       no-subscribers zero-allocation fast path (DESIGN §Performance notes).
- 1.4: per-subscriber ``try/except Exception`` error isolation,
       ``event_emit_failed`` structlog WARNING, immutable-snapshot iteration
       (re-entrant ``subscribe`` / ``unsubscribe`` / ``emit`` are all safe).
- 1.5: ``event_to_dict`` pure-payload JSON-safe encoder (datetime, UUID,
       Path, Enum, nested dataclasses, lists, tuples, dicts, primitives).

Subsequent sub-phases extend this module with the tagged envelope encoder
``event_to_envelope`` and its decoder + class registry hooked via
``Event.__init_subclass__`` (1.6). See
``docs/features/event-bus/plan/phase-01-foundation.md``.
"""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePath
from typing import Any
from uuid import UUID, uuid4

from personalscraper.logger import get_logger

# Module-level structlog binding — used to log subscriber failures (1.4).
# Imported once at module load time; ``get_logger`` returns a bound logger
# that includes the module name as a context field.
_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# JSON-safe encoder (Sub-phase 1.5 — pure-payload form)
# ---------------------------------------------------------------------------
# ``event_to_dict`` is the single recursive encoder shared by Event.to_dict()
# (sugar) and ``event_to_envelope`` (Sub-phase 1.6, adds the {"_type", "data"}
# tag layer). Its rules verbatim from DESIGN §JSON serialization contract:
#
#   datetime → ISO 8601 string (timezone-aware values keep their offset)
#   UUID     → str
#   PurePath → str (covers Path on every platform)
#   Enum     → enum.value
#   dataclass→ recursive {field_name: encoded(value)} mapping
#   list/tuple → list of recursively encoded elements
#   dict     → dict of {key: encoded(value)} — keys MUST be JSON-safe scalars
#   None / str / int / float / bool → unchanged
#
# Anything else raises ``TypeError`` (fail-loud — never silent fallback). The
# error message names the offending type so callers can extend the encoder
# (or coerce in the producer) rather than chasing a silent serialization bug.
#
# Allowed JSON-safe key types for dicts: str, int, float, bool, None
# (matching the JSON object key contract; non-string keys are coerced to
# strings by ``json.dumps`` but we keep them as-is here so the round-trip
# at envelope level can decide).

_JSON_SAFE_KEY_TYPES: tuple[type, ...] = (str, int, float, bool, type(None))


def event_to_dict(value: Any) -> Any:
    """Recursively encode ``value`` to JSON-safe primitives.

    Acts as a single-dispatch encoder: each branch covers one type-class from
    the contract table above. Reaches the bottom on a primitive (returned
    unchanged) or raises ``TypeError`` if the type is not in the contract.

    Args:
        value: Any object — usually an ``Event`` instance, but the function
            is recursive and called with field values too.

    Returns:
        A JSON-safe representation: a dict, list, str, int, float, bool, or
        ``None``. The result can be passed straight to ``json.dumps`` without
        a custom encoder.

    Raises:
        TypeError: if ``value`` (or any nested element) is not in the
            contract — for example a ``socket``, an arbitrary ``object``,
            or a dict with a non-JSON-safe key type.
    """
    # Order matters: ``bool`` is a subclass of ``int`` in CPython, so the
    # ``int`` branch would silently swallow bools. Primitives are listed
    # first because they are by far the most common case during a real
    # pipeline emit (most event field values are int / str).
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime):
        # ``isoformat`` keeps the timezone offset (`+00:00` for UTC).
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, PurePath):
        # ``PurePath`` covers ``Path``, ``PurePosixPath``, ``PureWindowsPath``.
        return str(value)
    if isinstance(value, Enum):
        # The contract is to encode the *value*, not the name — value is the
        # representation that survives database / wire / log round-trip.
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # ``asdict`` would walk the tree itself but we want our own encoding
        # rules applied at every node — so we iterate fields() and recurse.
        return {f.name: event_to_dict(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        # Tuples encode as lists — JSON has no tuple type and decoding with
        # the field annotation in 1.6 will reconstruct the tuple from the list.
        return [event_to_dict(item) for item in value]
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, val in value.items():
            if not isinstance(key, _JSON_SAFE_KEY_TYPES):
                raise TypeError(
                    f"Cannot encode dict key of type {type(key).__name__} "
                    f"for JSON serialization (allowed: str, int, float, bool, None)",
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

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe payload form of this event.

        Thin alias for module-level ``event_to_dict(self)`` — provided as a
        method for ergonomic ``event.to_dict()`` calls in subscriber code.
        Sub-phase 1.6 layers ``event_to_envelope`` on top to add the
        ``{"_type", "data"}`` tag for cross-process / Web-UI consumers.

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


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------
# Sub-phase 1.2 lands the storage shape and the ``subscribe`` / ``unsubscribe``
# methods. ``emit`` is intentionally absent — added in Sub-phase 1.3. Storage is
# ``dict[type[Event], tuple[tuple[SubscriptionToken, Callable], ...]]``: the
# outer dict is keyed by event class; the inner tuple is *immutable* per
# subscriber set, rebuilt on every ``subscribe`` / ``unsubscribe`` call. This
# copy-on-write discipline ensures ``emit`` (added later) can safely iterate
# the captured snapshot even if a subscriber re-enters the bus mid-dispatch.

_SubscriberEntry = tuple[SubscriptionToken, Callable[[Event], None]]


class EventBus:
    """In-process typed event bus.

    Sub-phase 1.2 surface: ``subscribe`` and ``unsubscribe`` only. Emit is added
    in Sub-phase 1.3 with MRO-walking dispatch and a fast path for the
    no-subscribers case.

    Concurrency: this bus is **not thread-safe** by design. Subscribers and
    emitters run inside a single process, single thread (the pipeline runner,
    the trailer CLI invocation, etc.). The ContextVar mechanism handles
    per-task isolation for asyncio Tasks (verified in Sub-phase 1.7 tests).
    """

    def __init__(self) -> None:
        """Initialize an empty subscriber registry and an empty MRO cache."""
        # Outer dict: event class → tuple of (token, callback) entries.
        # The tuple is rebuilt on every subscribe/unsubscribe — never mutated
        # in place — so emit can iterate a captured snapshot.
        self._subscribers: dict[type[Event], tuple[_SubscriberEntry, ...]] = {}
        # MRO cache: event class → tuple of callables in dispatch order
        # (concrete-type subscribers first, ancestor subscribers last).
        # Cleared entirely on every subscribe / unsubscribe — invalidating
        # only the affected entries would require tracking which cached
        # entries depend on which subscriber set, and the whole-cache flush
        # is cheap because it rebuilds on the next emit per-type.
        self._mro_cache: dict[type[Event], tuple[Callable[[Event], None], ...]] = {}

    def subscribe(
        self,
        event_type: type[Event],
        callback: Callable[[Event], None],
    ) -> SubscriptionToken:
        """Register a callback for events of ``event_type`` (or any subclass).

        Subscriber-of-base semantics — i.e. subscribing to ``Event`` catches
        every concrete subclass via the MRO walk — is implemented in
        Sub-phase 1.3's ``emit``; ``subscribe`` here only stores the binding.

        Args:
            event_type: The ``Event`` subclass to listen for.
            callback: Single-argument callable invoked with the event on emit.

        Returns:
            A ``SubscriptionToken`` to be passed to ``unsubscribe``.
        """
        token = SubscriptionToken(
            _id=next(_token_id_counter),
            event_type=event_type,
        )
        # Copy-on-write: build a brand-new tuple containing the existing
        # entries plus the new (token, callback) pair. The previous tuple
        # object is preserved unchanged for any in-flight emit iteration
        # (relevant from Sub-phase 1.4 onwards).
        existing = self._subscribers.get(event_type, ())
        self._subscribers[event_type] = (*existing, (token, callback))
        # Invalidate the MRO cache wholesale — the new subscriber may need
        # to fire for any event type whose MRO contains ``event_type``.
        self._mro_cache.clear()
        return token

    def unsubscribe(self, token: SubscriptionToken) -> None:
        """Remove the subscription identified by ``token``.

        Idempotent: passing a token that was never returned by ``subscribe``
        (or one already unsubscribed) is a no-op — no exception is raised.
        This matches the contract documented in DESIGN §Subscriber lifecycle:
        callers may unsubscribe defensively without try/except.

        Args:
            token: The token previously returned by ``subscribe``.
        """
        existing = self._subscribers.get(token.event_type)
        if not existing:
            # No subscriptions for this event type — nothing to remove.
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

        Error isolation and re-entrant emit safety land in Sub-phase 1.4.

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
    "Event",
    "EventBus",
    "SubscriptionToken",
    "current_correlation_id",
    "event_to_dict",
]
