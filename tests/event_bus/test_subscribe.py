"""Tests for ``SubscriptionToken`` + ``EventBus.subscribe`` / ``unsubscribe``.

Locks Sub-phase 1.2 of the event-bus feature: copy-on-write subscriber storage,
distinct opaque tokens, idempotent unsubscribe.
"""

from __future__ import annotations

from personalscraper.core.event_bus import Event, EventBus, SubscriptionToken


class _Foo(Event):
    """Test-only Event subclass — outside production registry by Invariant 9."""


class _Bar(Event):
    """Distinct test-only subclass for per-type storage assertions."""


def _noop(_event: Event) -> None:
    """Subscriber that records nothing — used when only token semantics matter."""


def test_subscribe_returns_distinct_tokens() -> None:
    """Two subscribe calls return two distinct ``SubscriptionToken`` values."""
    bus = EventBus()
    token_a = bus.subscribe(_Foo, _noop)
    token_b = bus.subscribe(_Foo, _noop)
    assert isinstance(token_a, SubscriptionToken)
    assert isinstance(token_b, SubscriptionToken)
    assert token_a != token_b


def test_subscribers_stored_per_type() -> None:
    """Subscribing to two distinct event types yields two registry keys."""
    bus = EventBus()
    bus.subscribe(_Foo, _noop)
    bus.subscribe(_Bar, _noop)
    # Inspect the internal dict — Phase 1 has no public introspection API.
    keys = set(bus._subscribers.keys())  # noqa: SLF001
    assert _Foo in keys
    assert _Bar in keys


def test_subscribe_is_copy_on_write() -> None:
    """The internal tuple is replaced on each subscribe — never mutated in place."""
    bus = EventBus()
    bus.subscribe(_Foo, _noop)
    snapshot_before = bus._subscribers[_Foo]  # noqa: SLF001
    bus.subscribe(_Foo, _noop)
    snapshot_after = bus._subscribers[_Foo]  # noqa: SLF001
    # The captured tuple object is unchanged — copy-on-write contract.
    assert len(snapshot_before) == 1
    assert len(snapshot_after) == 2
    # Identity check: the new tuple is a fresh object, not the old one extended.
    assert snapshot_before is not snapshot_after


def test_unsubscribe_removes_callback() -> None:
    """Unsubscribing removes the matching ``(token, callback)`` entry."""
    bus = EventBus()
    token = bus.subscribe(_Foo, _noop)
    bus.unsubscribe(token)
    # The key may either be absent or map to an empty tuple — both are valid.
    remaining = bus._subscribers.get(_Foo, ())  # noqa: SLF001
    assert remaining == ()


def test_unsubscribe_unknown_token_is_noop() -> None:
    """Unsubscribing a never-registered token raises nothing and changes nothing."""
    bus = EventBus()
    bus.subscribe(_Foo, _noop)
    snapshot = bus._subscribers[_Foo]  # noqa: SLF001
    # Construct a synthetic token that was never returned by subscribe.
    fake_token = SubscriptionToken(_id=999_999_999, event_type=_Foo)
    bus.unsubscribe(fake_token)  # MUST NOT raise.
    # The original subscription is intact.
    assert bus._subscribers[_Foo] is snapshot  # noqa: SLF001


def test_subscription_token_is_frozen() -> None:
    """``SubscriptionToken`` is immutable — assignment raises on a frozen dataclass."""
    token = SubscriptionToken(_id=1, event_type=_Foo)
    try:
        token._id = 2  # type: ignore[misc]
    except (AttributeError, TypeError):
        pass
    else:  # pragma: no cover
        raise AssertionError("SubscriptionToken must be frozen")


def test_subscribe_returns_token_carrying_event_type() -> None:
    """The token records the event type it was issued for — needed for unsubscribe."""
    bus = EventBus()
    token = bus.subscribe(_Foo, _noop)
    assert token.event_type is _Foo
