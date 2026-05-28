"""Phase 21 regression coverage — DESIGN §6.2 fallback on unclassified Exception.

The Phase 7+16 chain implementations previously short-circuited on the
broad ``except Exception`` arm: a ``ValueError`` from one provider set
``result.error`` and returned ``None``, hiding the next eligible provider
from the chain. This violated DESIGN §6.2 ("Try providers in config
order; first one that returns a usable result wins.").

Phase 21 (C2/C3) restored the chain semantics: on any unclassified
exception, the iteration:

1. Records ``AttemptOutcome(reason="other", detail=type(exc).__name__)``.
2. Emits :class:`ProviderFallbackTriggered` with ``reason="other"``.
3. Continues to the next provider.
4. Raises :class:`ProviderExhausted` only when every provider failed.

These tests fail against the pre-Phase-21 code and pass against the
fix. ACC-13 contract (legacy fail-soft ``result.error`` shape) is
preserved end-to-end and exercised by the all-providers-fail branch.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.metadata._contracts import MovieDetailsProvider, TvDetailsProvider
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.api.metadata.registry._errors import ProviderExhausted
from personalscraper.api.metadata.registry._events import (
    ProviderExhaustedEvent,
    ProviderFallbackTriggered,
)
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.confidence import MatchResult
from personalscraper.scraper.movie_service import MovieServiceMixin
from personalscraper.scraper.tv_service_episodes import match_tvshow_candidates


class _RecordingBus:
    """Minimal EventBus stub recording every ``emit`` call."""

    def __init__(self) -> None:
        self.emitted: list[Any] = []

    def emit(self, event: Any) -> None:
        """Append the emitted event to ``self.emitted``."""
        self.emitted.append(event)


def _make_registry(providers_by_capability: dict[type, list[Any]], bus: _RecordingBus) -> MagicMock:
    """Build a MagicMock(spec=ProviderRegistry) wired to capture chain emissions.

    ``emit_provider_fallback`` and ``emit_provider_exhausted`` are wired
    through to the bus so callers can assert on the emitted dataclasses.
    """
    registry = MagicMock(spec=ProviderRegistry)
    registry.chain.side_effect = lambda capability: list(providers_by_capability.get(capability, []))

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
        bus.emit(
            ProviderExhaustedEvent(
                capability=capability,
                attempted=tuple(attempted),
                item=item,
            )
        )

    registry.emit_provider_fallback.side_effect = _emit_fallback
    registry.emit_provider_exhausted.side_effect = _emit_exhausted
    return registry


def _make_provider(name: str) -> SimpleNamespace:
    """Build a tiny stand-in provider exposing ``provider_name``."""
    return SimpleNamespace(provider_name=name)


def _make_movie_mixin(registry: MagicMock) -> MovieServiceMixin:
    """Instantiate a bare MovieServiceMixin wired to the test registry."""
    mixin = MovieServiceMixin.__new__(MovieServiceMixin)
    mixin._registry = registry  # type: ignore[assignment]
    return mixin


# ---------------------------------------------------------------------------
# Movie chain — DESIGN §6.2 fallback semantics
# ---------------------------------------------------------------------------


def test_movie_chain_continues_on_unclassified_exception() -> None:
    """A ValueError from provider 1 must NOT hide provider 2 from the chain.

    Asserts the chain rolls forward to ``tmdb`` after ``tvdb`` raises an
    unclassified ``ValueError`` (DESIGN §6.2). One
    ``ProviderFallbackTriggered(reason="other")`` is emitted; the eventual
    return is the second provider's successful match.
    """
    tvdb = _make_provider("tvdb")
    tmdb = _make_provider("tmdb")
    bus = _RecordingBus()
    registry = _make_registry({MovieDetailsProvider: [tvdb, tmdb]}, bus)
    mixin = _make_movie_mixin(registry)

    winning_match = MatchResult(
        api_id=42,
        api_title="The Matrix",
        api_year=1999,
        confidence=0.95,
        source="tmdb",
    )

    def _match_movie(provider: Any, title: str, year: int | None) -> MatchResult | None:
        if provider.provider_name == "tvdb":
            raise ValueError("malformed TVDB payload")
        return winning_match

    result = ScrapeResult(media_path=Path("/tmp/movie"), media_type="movie")
    with patch("personalscraper.scraper.scraper.match_movie", side_effect=_match_movie):
        returned = mixin._match_movie_candidates("The Matrix", 1999, result)

    assert returned is winning_match
    assert result.error is None  # fail-soft NOT triggered — chain succeeded

    fallback_events = [e for e in bus.emitted if isinstance(e, ProviderFallbackTriggered)]
    assert len(fallback_events) == 1
    event = fallback_events[0]
    assert event.from_provider == "tvdb"
    assert event.reason == "other"
    assert event.exc_type == "ValueError"
    assert event.capability == "MovieDetailsProvider"


def test_movie_chain_exhausted_on_all_unclassified_raises() -> None:
    """All providers raising unclassified → ProviderExhausted + exhausted event.

    Every chain provider raises a ``KeyError``. The chain must:

    - Emit one ``ProviderFallbackTriggered(reason="other")`` per provider.
    - Emit one ``ProviderExhaustedEvent`` with ``AttemptOutcome(reason="other")``
      rows.
    - Raise :class:`ProviderExhausted` so the orchestrator surfaces the
      ACC-13 ``result.error`` shape (with the last exception detail).
    """
    tvdb = _make_provider("tvdb")
    tmdb = _make_provider("tmdb")
    bus = _RecordingBus()
    registry = _make_registry({MovieDetailsProvider: [tvdb, tmdb]}, bus)
    mixin = _make_movie_mixin(registry)

    def _always_raise(provider: Any, title: str, year: int | None) -> MatchResult | None:
        raise KeyError(f"missing key from {provider.provider_name}")

    result = ScrapeResult(media_path=Path("/tmp/movie"), media_type="movie")
    with (
        patch("personalscraper.scraper.scraper.match_movie", side_effect=_always_raise),
        pytest.raises(ProviderExhausted) as exc_info,
    ):
        mixin._match_movie_candidates("The Matrix", 1999, result)

    fallback_events = [e for e in bus.emitted if isinstance(e, ProviderFallbackTriggered)]
    assert len(fallback_events) == 2
    assert {e.from_provider for e in fallback_events} == {"tvdb", "tmdb"}
    assert all(e.reason == "other" and e.exc_type == "KeyError" for e in fallback_events)

    exhausted_events = [e for e in bus.emitted if isinstance(e, ProviderExhaustedEvent)]
    assert len(exhausted_events) == 1
    reasons = {a.reason for a in exhausted_events[0].attempted}
    assert reasons == {"other"}

    # ProviderExhausted carries the original last_exception so the caller
    # can surface the ACC-13 fail-soft shape.
    assert exc_info.value.last_exception is not None
    assert isinstance(exc_info.value.last_exception, KeyError)


# ---------------------------------------------------------------------------
# TV chain — symmetric with movies
# ---------------------------------------------------------------------------


def test_tv_chain_continues_on_unclassified_exception() -> None:
    """A TVDB ValueError must roll forward to TMDB in match_tvshow_candidates."""
    tvdb = _make_provider("tvdb")
    tmdb = _make_provider("tmdb")
    bus = _RecordingBus()
    registry = _make_registry({TvDetailsProvider: [tvdb, tmdb]}, bus)

    winning_match = MatchResult(
        api_id=12345,
        api_title="Breaking Bad",
        api_year=2008,
        confidence=0.9,
        source="tmdb",
    )

    def _match_single(provider: Any, title: str, year: int | None, *, local_seasons: set[int]) -> MatchResult | None:
        if provider.provider_name == "tvdb":
            raise ValueError("malformed TVDB payload")
        return winning_match

    result = ScrapeResult(media_path=Path("/tmp/show"), media_type="tvshow")
    with patch("personalscraper.scraper.scraper.match_tvshow_single", side_effect=_match_single):
        returned = match_tvshow_candidates(registry, "Breaking Bad", 2008, set(), result)

    assert returned is winning_match
    assert result.error is None

    fallback_events = [e for e in bus.emitted if isinstance(e, ProviderFallbackTriggered)]
    assert len(fallback_events) == 1
    event = fallback_events[0]
    assert event.from_provider == "tvdb"
    assert event.reason == "other"
    assert event.exc_type == "ValueError"
    assert event.capability == "TvDetailsProvider"


def test_tv_chain_exhausted_on_all_unclassified_raises() -> None:
    """All TV providers raising unclassified → ProviderExhausted with reason='other'."""
    tvdb = _make_provider("tvdb")
    tmdb = _make_provider("tmdb")
    bus = _RecordingBus()
    registry = _make_registry({TvDetailsProvider: [tvdb, tmdb]}, bus)

    def _always_raise(provider: Any, title: str, year: int | None, *, local_seasons: set[int]) -> MatchResult | None:
        raise RuntimeError(f"unclassified from {provider.provider_name}")

    result = ScrapeResult(media_path=Path("/tmp/show"), media_type="tvshow")
    with (
        patch("personalscraper.scraper.scraper.match_tvshow_single", side_effect=_always_raise),
        pytest.raises(ProviderExhausted) as exc_info,
    ):
        match_tvshow_candidates(registry, "Breaking Bad", 2008, set(), result)

    fallback_events = [e for e in bus.emitted if isinstance(e, ProviderFallbackTriggered)]
    assert {e.from_provider for e in fallback_events} == {"tvdb", "tmdb"}
    assert all(e.reason == "other" for e in fallback_events)

    exhausted_events = [e for e in bus.emitted if isinstance(e, ProviderExhaustedEvent)]
    assert len(exhausted_events) == 1
    reasons = {a.reason for a in exhausted_events[0].attempted}
    assert reasons == {"other"}

    assert isinstance(exc_info.value.last_exception, RuntimeError)
