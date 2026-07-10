"""Phase 25.3 — end-to-end chain exhaustion through ``Scraper.scrape_movie``.

Closes the gap identified by the pr-test-analyzer audit: no scraper-level
test asserted that when all chain providers raise classified network
errors, ``result.error`` reaches the legacy fail-soft shape via Phase 16's
``ProviderExhausted`` contract AND ``ProviderExhaustedEvent`` is emitted
on the bus.

Existing coverage (``tests/scraper/test_chain_fallback_unclassified.py``)
drives ``_match_movie_candidates`` in isolation. This test drives the
FULL ``scrape_movie`` flow with a real :class:`Scraper`, a mocked
:class:`ProviderRegistry`, and a real bus capture — so the integration
between mixin, orchestrator exception handling, and event-bus emission
is exercised end-to-end.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.api._contracts import ApiError
from personalscraper.api.metadata._contracts import MovieDetailsProvider
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.api.metadata.registry._events import (
    ProviderExhaustedEvent,
    ProviderFallbackTriggered,
)
from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.orchestrator import Scraper


class _RecordingBus:
    """Minimal EventBus stub that records every emitted event in order."""

    def __init__(self) -> None:
        self.emitted: list[Any] = []

    def emit(self, event: Any) -> None:
        """Append the emitted event to ``self.emitted``."""
        self.emitted.append(event)


def _make_chain_exhausted_registry(bus: _RecordingBus) -> MagicMock:
    """Build a MagicMock(spec=ProviderRegistry) wired to capture chain emissions.

    Two providers ("tvdb" and "tmdb") are exposed via ``chain()``; both
    will raise :class:`ApiError` when ``match_movie`` runs against them,
    triggering the chain-exhaustion path. ``emit_provider_fallback`` and
    ``emit_provider_exhausted`` are wired through to ``bus`` so the test
    asserts on the emitted dataclasses.

    Args:
        bus: The recording bus to forward emissions through.

    Returns:
        A configured :class:`MagicMock` matching the real
        :class:`ProviderRegistry` spec.
    """
    registry = MagicMock(spec=ProviderRegistry)
    tvdb = SimpleNamespace(provider_name="tvdb")
    tmdb = SimpleNamespace(provider_name="tmdb")
    registry.chain.side_effect = lambda capability: [tvdb, tmdb] if capability is MovieDetailsProvider else []

    def _emit_fallback(
        *,
        capability: str,
        from_provider: str,
        reason: str,
        item: dict[str, Any],
        to_provider: str | None = None,
        exc_type: str | None = None,
    ) -> None:
        bus.emit(
            ProviderFallbackTriggered(
                capability=capability,
                from_provider=from_provider,
                to_provider=to_provider or "",
                reason=reason,  # type: ignore[arg-type]
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


def test_scrape_movie_chain_exhaustion_preserves_last_exception_in_result(tmp_path: Path) -> None:
    """All chain providers raising ApiError → result.error contains last detail (ACC-13).

    Phase 25.3 closes the audit gap: this test asserts the FULL
    ``scrape_movie`` flow surfaces the legacy fail-soft shape when every
    chain provider raises a classified ``network`` error. Specifically:

    1. ``result.action == "error"`` (legacy contract).
    2. ``result.error`` contains the LAST provider's exception message —
       :attr:`ProviderExhausted.last_exception` carries the original
       :class:`ApiError` so the formatted message reaches the user.
    3. :class:`ProviderExhaustedEvent` is emitted on the bus exactly once.
    4. :class:`ProviderFallbackTriggered` is emitted once per attempted
       provider (one per chain iteration).

    Regression catches: a refactor that swallows ``last_exception`` inside
    :class:`ProviderExhausted` (silent ``result.error = None``), or one that
    deletes the ``emit_provider_exhausted`` call site before the
    ``raise``, breaking observability.
    """
    # Real movies directory layout — one subdir per movie.
    movies_dir = tmp_path / "001-MOVIES"
    movies_dir.mkdir()
    (movies_dir / "The Matrix (1999)").mkdir()

    bus = _RecordingBus()
    registry = _make_chain_exhausted_registry(bus)

    # Real Settings stub (typed) — required by Scraper.__init__.
    settings = MagicMock()
    settings.tmdb_api_key = "dummy_tmdb"
    settings.tvdb_api_key = "dummy_tvdb"

    scraper = Scraper(
        settings,
        NamingPatterns(),
        event_bus=EventBus(),
        registry=registry,
    )

    last_exc_message = "TMDB API HTTP 503 — service unavailable"

    def _always_raise(provider: Any, title: str, year: int | None) -> Any:
        """Raise a classified ApiError for every provider in the chain."""
        if provider.provider_name == "tvdb":
            raise ApiError(
                provider="tvdb",
                http_status=502,
                provider_code=0,
                message="TVDB API HTTP 502 — bad gateway",
            )
        raise ApiError(
            provider="tmdb",
            http_status=503,
            provider_code=0,
            message=last_exc_message,
        )

    with patch("personalscraper.scraper.confidence.match_movie_detailed", side_effect=_always_raise):
        results = scraper.process_movies(movies_dir)

    # --- result.error reaches legacy shape ---
    assert len(results) == 1
    result = results[0]
    assert result.action == "error", f"expected action='error', got {result.action!r}"
    assert result.error is not None
    # ProviderExhausted.last_exception carries the last ApiError; the formatted
    # message (or its substring) must appear in result.error. The mixin
    # composes ``"Match failed: {detail}"`` where detail is the exception.
    assert "Match failed" in result.error, f"expected 'Match failed' prefix; got {result.error!r}"
    # The 503 message from the LAST provider (tmdb) is the one that wins
    # — preserving the ACC-13 contract.
    assert "503" in result.error or "service unavailable" in result.error.lower(), (
        f"expected last provider's 503/service unavailable in result.error; got {result.error!r}"
    )

    # --- ProviderExhaustedEvent emitted exactly once ---
    exhausted_events = [e for e in bus.emitted if isinstance(e, ProviderExhaustedEvent)]
    assert len(exhausted_events) == 1, f"expected exactly one ProviderExhaustedEvent; got {len(exhausted_events)}"
    event = exhausted_events[0]
    assert event.capability == "MovieDetailsProvider"
    # Both providers attempted (one row per chain iteration).
    attempted_providers = {a.provider for a in event.attempted}
    assert attempted_providers == {"tvdb", "tmdb"}
    # Every attempt classified as "network" (ApiError → network branch).
    assert {a.reason for a in event.attempted} == {"network"}

    # --- ProviderFallbackTriggered emitted once per provider ---
    fallback_events = [e for e in bus.emitted if isinstance(e, ProviderFallbackTriggered)]
    assert len(fallback_events) == 2, f"expected one fallback per provider; got {len(fallback_events)}"
    assert {e.from_provider for e in fallback_events} == {"tvdb", "tmdb"}
    assert all(e.reason == "network" for e in fallback_events)
    assert all(e.exc_type == "ApiError" for e in fallback_events)
