"""Unit tests for the shared registry-chain iterator ``scraper._match.run_chain``.

``run_chain`` is the single home for the per-provider try/except classification,
``AttemptOutcome`` accumulation, ``ProviderFallbackTriggered`` /
``ProviderExhaustedEvent`` emission, and the terminal ``ProviderExhausted`` raise
that four scraper call sites previously duplicated (SCRAPER-01). These tests pin
that behaviour directly with a recording bus and a stub registry, independent of
any concrete provider.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Literal
from unittest.mock import MagicMock

import pytest

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api.metadata._contracts import MovieDetailsProvider
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.api.metadata.registry._errors import ProviderExhausted
from personalscraper.api.metadata.registry._events import (
    ProviderExhaustedEvent,
    ProviderFallbackTriggered,
)
from personalscraper.scraper._match import run_chain

_CTX: dict[str, Any] = {"title": "Whatever", "year": 2020, "media_type": "movie"}


class _RecordingBus:
    """Minimal EventBus stub recording every ``emit`` call."""

    def __init__(self) -> None:
        self.emitted: list[Any] = []

    def emit(self, event: Any) -> None:
        """Append the emitted event."""
        self.emitted.append(event)


def _make_registry(providers: list[Any], bus: _RecordingBus) -> MagicMock:
    """MagicMock(spec=ProviderRegistry) whose emit helpers route to ``bus``."""
    registry = MagicMock(spec=ProviderRegistry)
    registry.chain.side_effect = lambda _capability: list(providers)

    def _emit_fallback(
        *,
        capability: str,
        from_provider: str,
        reason: Literal["circuit_open", "network", "empty_result", "other"],
        item: dict[str, Any],
        to_provider: str | None = None,
        exc_type: str | None = None,
    ) -> None:
        bus.emit(
            ProviderFallbackTriggered(
                capability=capability,
                from_provider=from_provider,
                to_provider=to_provider or "",
                reason=reason,
                exc_type=exc_type,
                item=item,
            )
        )

    def _emit_exhausted(*, capability: str, attempted: list[Any], item: dict[str, Any]) -> None:
        bus.emit(ProviderExhaustedEvent(capability=capability, attempted=tuple(attempted), item=item))

    registry.emit_provider_fallback.side_effect = _emit_fallback
    registry.emit_provider_exhausted.side_effect = _emit_exhausted
    return registry


def _provider(name: str) -> SimpleNamespace:
    """Tiny stand-in provider exposing ``provider_name``."""
    return SimpleNamespace(provider_name=name)


def _fallbacks(bus: _RecordingBus) -> list[ProviderFallbackTriggered]:
    return [e for e in bus.emitted if isinstance(e, ProviderFallbackTriggered)]


def _exhausted(bus: _RecordingBus) -> list[ProviderExhaustedEvent]:
    return [e for e in bus.emitted if isinstance(e, ProviderExhaustedEvent)]


def test_success_first_provider_no_events() -> None:
    """The first provider succeeding returns its result and emits nothing."""
    bus = _RecordingBus()
    registry = _make_registry([_provider("tvdb"), _provider("tmdb")], bus)

    def _attempt(provider: Any) -> str | None:
        return f"hit:{provider.provider_name}"

    out = run_chain(registry, MovieDetailsProvider, _attempt, item_context=_CTX)

    assert out == "hit:tvdb"
    assert bus.emitted == []


def test_empty_result_rolls_forward() -> None:
    """A provider returning ``None`` emits an empty_result fallback and continues."""
    bus = _RecordingBus()
    registry = _make_registry([_provider("tvdb"), _provider("tmdb")], bus)

    def _attempt(provider: Any) -> str | None:
        return None if provider.provider_name == "tvdb" else "hit:tmdb"

    out = run_chain(registry, MovieDetailsProvider, _attempt, item_context=_CTX)

    assert out == "hit:tmdb"
    fbs = _fallbacks(bus)
    assert len(fbs) == 1
    assert fbs[0].from_provider == "tvdb"
    assert fbs[0].reason == "empty_result"
    assert _exhausted(bus) == []


def test_circuit_open_skips_to_next() -> None:
    """A CircuitOpenError classifies as circuit_open and rolls forward."""
    bus = _RecordingBus()
    registry = _make_registry([_provider("tvdb"), _provider("tmdb")], bus)

    def _attempt(provider: Any) -> str | None:
        if provider.provider_name == "tvdb":
            raise CircuitOpenError("tvdb", 30.0)
        return "hit:tmdb"

    out = run_chain(registry, MovieDetailsProvider, _attempt, item_context=_CTX)

    assert out == "hit:tmdb"
    fbs = _fallbacks(bus)
    assert len(fbs) == 1
    assert fbs[0].reason == "circuit_open"
    assert fbs[0].from_provider == "tvdb"


def test_network_error_then_success() -> None:
    """An ApiError classifies as network with the exc_type recorded."""
    bus = _RecordingBus()
    registry = _make_registry([_provider("tvdb"), _provider("tmdb")], bus)

    def _attempt(provider: Any) -> str | None:
        if provider.provider_name == "tvdb":
            raise ApiError("tvdb", 500)
        return "hit:tmdb"

    out = run_chain(registry, MovieDetailsProvider, _attempt, item_context=_CTX)

    assert out == "hit:tmdb"
    fbs = _fallbacks(bus)
    assert len(fbs) == 1
    assert fbs[0].reason == "network"
    assert fbs[0].exc_type == "ApiError"


def test_unclassified_exception_reason_other() -> None:
    """Any other exception classifies as other with exc_type recorded."""
    bus = _RecordingBus()
    registry = _make_registry([_provider("tvdb"), _provider("tmdb")], bus)

    def _attempt(provider: Any) -> str | None:
        if provider.provider_name == "tvdb":
            raise ValueError("malformed")
        return "hit:tmdb"

    out = run_chain(registry, MovieDetailsProvider, _attempt, item_context=_CTX)

    assert out == "hit:tmdb"
    fbs = _fallbacks(bus)
    assert len(fbs) == 1
    assert fbs[0].reason == "other"
    assert fbs[0].exc_type == "ValueError"


def test_all_error_raises_provider_exhausted() -> None:
    """Every provider erroring emits the exhausted event then raises."""
    bus = _RecordingBus()
    registry = _make_registry([_provider("tvdb"), _provider("tmdb")], bus)
    boom = ApiError("tmdb", 503)

    def _attempt(provider: Any) -> str | None:
        if provider.provider_name == "tvdb":
            raise CircuitOpenError("tvdb", 30.0)
        raise boom

    with pytest.raises(ProviderExhausted) as exc_info:
        run_chain(registry, MovieDetailsProvider, _attempt, item_context=_CTX)

    # Both providers tried, one fallback each, one exhausted event.
    fbs = _fallbacks(bus)
    assert {e.from_provider for e in fbs} == {"tvdb", "tmdb"}
    exhausted = _exhausted(bus)
    assert len(exhausted) == 1
    assert {a.reason for a in exhausted[0].attempted} == {"circuit_open", "network"}
    # Last underlying exception is preserved for the ACC-13 fail-soft shape.
    assert exc_info.value.last_exception is boom
    assert exc_info.value.capability is MovieDetailsProvider


def test_all_empty_returns_none_without_raising() -> None:
    """An all-empty chain is the legacy 'no match' path — None, no exhausted."""
    bus = _RecordingBus()
    registry = _make_registry([_provider("tvdb"), _provider("tmdb")], bus)

    out = run_chain(registry, MovieDetailsProvider, lambda _p: None, item_context=_CTX)

    assert out is None
    assert {e.reason for e in _fallbacks(bus)} == {"empty_result"}
    assert _exhausted(bus) == []


def test_empty_chain_returns_none() -> None:
    """No eligible providers → None, no events, no raise."""
    bus = _RecordingBus()
    registry = _make_registry([], bus)

    out = run_chain(registry, MovieDetailsProvider, lambda _p: "never", item_context=_CTX)

    assert out is None
    assert bus.emitted == []


def test_source_filter_skips_silently() -> None:
    """Providers rejected by ``source_filter`` are skipped without any event."""
    bus = _RecordingBus()
    registry = _make_registry([_provider("tvdb"), _provider("tmdb")], bus)
    seen: list[str] = []

    def _attempt(provider: Any) -> str:
        seen.append(provider.provider_name)
        return f"hit:{provider.provider_name}"

    out = run_chain(
        registry,
        MovieDetailsProvider,
        _attempt,
        item_context=_CTX,
        source_filter=lambda p: p.provider_name == "tmdb",
    )

    assert out == "hit:tmdb"
    assert seen == ["tmdb"]  # tvdb never attempted
    assert bus.emitted == []  # silent skip — no fallback event


def test_source_filter_excluding_all_returns_none() -> None:
    """When ``source_filter`` rejects every provider run_chain returns None."""
    bus = _RecordingBus()
    registry = _make_registry([_provider("tvdb"), _provider("tmdb")], bus)

    out = run_chain(
        registry,
        MovieDetailsProvider,
        lambda _p: "never",
        item_context=_CTX,
        source_filter=lambda _p: False,
    )

    assert out is None
    assert bus.emitted == []
