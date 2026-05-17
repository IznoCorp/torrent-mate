"""Comprehensive ``current_correlation_id`` ContextVar capture tests.

Locks Sub-phase 1.7 of the event-bus feature. No production code change —
this sub-phase pins the capture semantics that Sub-phase 1.1 implemented:

- Default ``None`` outside any bound region.
- Captured at construction inside a bound region.
- Long-lived emitters (constructed before the bind) still capture properly.
- Emit does NOT re-read the ContextVar — value is frozen on the event.
- Explicit ``correlation_id=`` argument wins over the ContextVar value
  (including explicit ``None`` per dataclass default_factory semantics).
- Per-asyncio-task isolation.
- Per-thread isolation.
"""

from __future__ import annotations

import asyncio
import threading

from personalscraper.core.event_bus import Event, EventBus, current_correlation_id


class _Foo(Event):
    """Test-only subclass."""


def test_correlation_id_none_outside_bound_region() -> None:
    """No bind → ``correlation_id`` is ``None``."""
    assert current_correlation_id.get() is None
    assert _Foo().correlation_id is None


def test_correlation_id_captured_inside_bound_region() -> None:
    """Bind → captured; reset → next event again ``None``."""
    token = current_correlation_id.set("run-123")
    try:
        assert _Foo().correlation_id == "run-123"
    finally:
        current_correlation_id.reset(token)
    assert current_correlation_id.get() is None
    assert _Foo().correlation_id is None


def test_correlation_id_long_lived_emitter() -> None:
    """A singleton constructed BEFORE the bind still captures the ContextVar.

    Documents the CircuitBreaker scenario: a long-lived helper exists at
    module-load time, and a later pipeline-run binds the ContextVar before
    asking the helper to emit. The helper's emit happens INSIDE the bound
    region, so the event captures the correct correlation_id at construction.
    """

    class _Singleton:
        """Stand-in for CircuitBreaker / module-level helpers."""

        def make_event(self) -> _Foo:
            return _Foo()

    helper = _Singleton()
    assert helper.make_event().correlation_id is None  # outside bind
    token = current_correlation_id.set("run-456")
    try:
        event = helper.make_event()
        assert event.correlation_id == "run-456"
    finally:
        current_correlation_id.reset(token)


def test_correlation_id_emit_does_not_modify() -> None:
    """Emit reads no ContextVar — the value frozen at construction wins.

    Construct an event INSIDE a bound region (captures ``"run-A"``), then
    reset the ContextVar, then emit. The subscriber MUST receive an event
    whose ``correlation_id`` is still ``"run-A"`` — emit does not re-read.
    """
    bus = EventBus()
    captured: list[str | None] = []
    bus.subscribe(_Foo, lambda e: captured.append(e.correlation_id))
    token = current_correlation_id.set("run-A")
    try:
        event = _Foo()
    finally:
        current_correlation_id.reset(token)
    # ContextVar is now None again; emit must NOT re-read it.
    assert current_correlation_id.get() is None
    bus.emit(event)
    assert captured == ["run-A"]


def test_correlation_id_explicit_override() -> None:
    """Explicit ``correlation_id=`` wins over the bound ContextVar value."""
    token = current_correlation_id.set("from-context")
    try:
        assert _Foo(correlation_id="explicit").correlation_id == "explicit"
    finally:
        current_correlation_id.reset(token)


def test_correlation_id_explicit_none_does_not_capture() -> None:
    """Explicit ``correlation_id=None`` wins over the ContextVar (factory not called).

    Dataclass default_factory semantics: when the caller passes a value
    (even ``None``), the factory is not invoked. So ``_Foo(correlation_id=None)``
    produces an event with ``None`` regardless of the bound ContextVar.
    """
    token = current_correlation_id.set("from-context")
    try:
        assert _Foo(correlation_id=None).correlation_id is None
    finally:
        current_correlation_id.reset(token)


def test_correlation_id_isolated_across_asyncio_tasks() -> None:
    """Two asyncio tasks each see their own bound ContextVar value."""

    async def _task(value: str) -> str | None:
        token = current_correlation_id.set(value)
        try:
            await asyncio.sleep(0)  # yield so the other task can interleave
            return _Foo().correlation_id
        finally:
            current_correlation_id.reset(token)

    async def _runner() -> tuple[str | None, str | None]:
        a, b = await asyncio.gather(_task("task-A"), _task("task-B"))
        return a, b

    a, b = asyncio.run(_runner())
    assert a == "task-A"
    assert b == "task-B"


def test_correlation_id_isolated_across_threads() -> None:
    """Two threads each see their own bound ContextVar value."""
    results: dict[str, str | None] = {}

    def _worker(label: str, value: str) -> None:
        token = current_correlation_id.set(value)
        try:
            results[label] = _Foo().correlation_id
        finally:
            current_correlation_id.reset(token)

    t_a = threading.Thread(target=_worker, args=("a", "thread-A"))
    t_b = threading.Thread(target=_worker, args=("b", "thread-B"))
    t_a.start()
    t_b.start()
    t_a.join()
    t_b.join()
    assert results == {"a": "thread-A", "b": "thread-B"}
