"""Gate tests for ``EVENT_SAMPLE_FACTORIES`` and the production event registry.

Sub-phase 1.8: ships the gate but it is **vacuously green** in Phase 1
because no concrete events have been introduced. From Phase 3 onwards,
every concrete production event MUST register a factory or this gate fires.
"""

from __future__ import annotations

from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY, Event
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES, register_factory


def test_every_event_has_factory() -> None:
    """Every production event subclass must have an entry in EVENT_SAMPLE_FACTORIES.

    Iterates over the bus's ``_EVENT_CLASS_REGISTRY`` (already filtered to
    ``personalscraper.*`` modules by ``Event.__init_subclass__`` per
    Invariant 9), so test stubs from ``tests/`` do NOT need factories.

    Vacuously green in Phase 1 (no concrete events yet); becomes a real gate
    from Phase 3 onwards.
    """
    missing = [
        event_class.__name__
        for event_class in _EVENT_CLASS_REGISTRY.values()
        if event_class not in EVENT_SAMPLE_FACTORIES
    ]
    assert not missing, (
        f"Production events without a factory: {missing}. "
        f"Register one in tests/fixtures/event_samples.py via @register_factory."
    )


def test_registered_factories_produce_correct_type() -> None:
    """Each registered factory returns an instance of the registered class."""
    for event_class, factory in EVENT_SAMPLE_FACTORIES.items():
        instance = factory()
        assert isinstance(instance, event_class), (
            f"Factory for {event_class.__name__} returned {type(instance).__name__} instead",
        )
        assert isinstance(instance, Event), f"Factory for {event_class.__name__} returned a non-Event"


def test_register_factory_rejects_duplicate_registration() -> None:
    """A second factory for the same event type raises ``ValueError``."""

    class _Tmp(Event):
        """Test stub — module-path filtered out of the production registry."""

    @register_factory(_Tmp)
    def _make_tmp() -> _Tmp:
        return _Tmp()

    try:
        with __import__("pytest").raises(ValueError, match="already registered"):

            @register_factory(_Tmp)
            def _make_tmp_again() -> _Tmp:
                return _Tmp()
    finally:
        # Tear down the test-only entry so it doesn't leak into other tests.
        EVENT_SAMPLE_FACTORIES.pop(_Tmp, None)
