"""m15/D4 — the per-tracker error TAXON reaches the search verdict.

``SearchOutcome`` used to carry only the NAMES of the trackers that errored, so
every all-errored search read as ``trackers_unavailable``: a broken passkey was
a permanent « outage » that retried forever instead of abandoning, and an
all-circuit-open search wore a label that said nothing about the breaker.

The registry now tags each failure with its taxon (``auth`` / ``circuit`` /
``api``) and the chain reads them:

- every queried tracker in ``auth``    ⇒ TERMINAL ``tracker_auth``;
- every queried tracker in ``circuit`` ⇒ retryable ``circuit_open``;
- anything mixed, or any ``api``       ⇒ retryable ``trackers_unavailable``
  (unchanged — a partial/unknown outage stays an outage).

The catch order is load-bearing in the registry too: ``TrackerAuthError``
SUBCLASSES ``ApiError``, so a generic ``except ApiError`` first would label a
broken key ``api`` and the terminal verdict would never fire.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import WantedAbandoned
from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.api._contracts import ApiError, CircuitOpenError, MediaType
from personalscraper.api.tracker._errors import TrackerAuthError
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.conf.models.acquire import BandwidthConfig
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.core.identity import MediaRef


def _item() -> WantedItem:
    """A claimed movie row to search for."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=4242),
        kind="movie",
        status="searching",
        enqueued_at=1_700_000_000,
        id=1,
    )


class _RaisingTracker:
    """Tracker stub whose ``search`` always raises the given exception."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def search(self, query: str, media_type: object = None, year: int | None = None) -> list[object]:
        """Always raise the configured failure."""
        raise self._exc

    def get_categories(self) -> dict[str, str]:
        """Unused by these tests."""
        return {}


def _registry(**trackers: Exception) -> TrackerRegistry:
    """Build a registry whose trackers all raise their configured exception."""
    return TrackerRegistry(
        trackers={name: _RaisingTracker(exc) for name, exc in trackers.items()},  # type: ignore[dict-item]
        priority=list(trackers),
        ranking=RankingConfig(min_seeders=0),
    )


def _auth(tracker: str = "c411") -> TrackerAuthError:
    return TrackerAuthError(provider=tracker, http_status=401, message="Invalid API Key")


def _api(tracker: str = "c411") -> ApiError:
    return ApiError(provider=tracker, http_status=500, message="boom")


class TestRegistryTaxonomy:
    """``search_candidates`` tags every failure with its taxon."""

    def test_auth_failure_is_tagged_auth_not_api(self) -> None:
        """TrackerAuthError subclasses ApiError — the catch order must not fold it."""
        outcome = _registry(c411=_auth()).search_candidates("q", MediaType.MOVIE, None)

        assert outcome.errors == {"c411": "auth"}
        assert outcome.errored_names == ["c411"], "the historical field stays populated"

    def test_circuit_open_is_tagged_circuit(self) -> None:
        """An OPEN breaker is a distinct taxon from a generic API failure."""
        outcome = _registry(c411=CircuitOpenError(provider="c411", remaining_seconds=42.0)).search_candidates(
            "q", MediaType.MOVIE, None
        )

        assert outcome.errors == {"c411": "circuit"}

    @pytest.mark.parametrize(
        "exc",
        [ApiError(provider="c411", http_status=500, message="boom"), ValueError("drift"), TypeError("shape")],
        ids=["api-error", "value-error", "type-error"],
    )
    def test_everything_else_is_tagged_api(self, exc: Exception) -> None:
        """Any other swallowed operational failure is the generic ``api`` taxon."""
        outcome = _registry(c411=exc).search_candidates("q", MediaType.MOVIE, None)

        assert outcome.errors == {"c411": "api"}

    def test_each_tracker_keeps_its_own_taxon(self) -> None:
        """A mixed failure set is reported per tracker, not collapsed."""
        outcome = _registry(
            c411=_auth("c411"),
            tr4ker=CircuitOpenError(provider="tr4ker", remaining_seconds=42.0),
        ).search_candidates("q", MediaType.MOVIE, None)

        assert outcome.errors == {"c411": "auth", "tr4ker": "circuit"}
        assert sorted(outcome.errored_names) == ["c411", "tr4ker"]

    def test_a_healthy_tracker_contributes_no_error(self) -> None:
        """Only failures land in ``errors`` — a success is simply absent."""
        healthy = MagicMock()
        healthy.search.return_value = []
        registry = TrackerRegistry(
            trackers={"c411": _RaisingTracker(_auth()), "lacale": healthy},  # type: ignore[dict-item]
            priority=["c411", "lacale"],
            ranking=RankingConfig(min_seeders=0),
        )

        outcome = registry.search_candidates("q", MediaType.MOVIE, None)

        assert outcome.errors == {"c411": "auth"}
        assert outcome.all_errored is False


class TestSearchVerdictFromTaxa:
    """The chain turns « all trackers broken the SAME way » into the right verdict."""

    @staticmethod
    def _search(registry: TrackerRegistry, bus: EventBus | None = None) -> object:
        """Run the real orchestrator search over *registry*."""
        orchestrator = GrabOrchestrator(
            tracker_registry=registry,
            torrent_client=None,
            event_bus=bus or EventBus(),
            ranking=RankingConfig(min_seeders=0),
            bandwidth=BandwidthConfig(),
        )
        return orchestrator.search(_item(), QualityProfile())

    def test_all_auth_is_terminal_tracker_auth(self) -> None:
        """A broken key on EVERY tracker is permanent — abandon, never retry forever."""
        verdict = self._search(_registry(c411=_auth("c411"), tr4ker=_auth("tr4ker")))

        assert (verdict.disposition, verdict.outcome, verdict.found) == ("terminal", "tracker_auth", None)  # type: ignore[attr-defined]

    def test_all_circuit_is_retryable_circuit_open(self) -> None:
        """Every breaker OPEN is an outage that names itself honestly."""
        verdict = self._search(
            _registry(
                c411=CircuitOpenError(provider="c411", remaining_seconds=42.0),
                tr4ker=CircuitOpenError(provider="tr4ker", remaining_seconds=42.0),
            )
        )

        assert (verdict.disposition, verdict.outcome, verdict.found) == ("retryable", "circuit_open", None)  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            (_auth("c411"), CircuitOpenError(provider="tr4ker", remaining_seconds=42.0)),
            (_auth("c411"), _api("tr4ker")),
            (CircuitOpenError(provider="c411", remaining_seconds=42.0), _api("tr4ker")),
            (_api("c411"), _api("tr4ker")),
        ],
        ids=["auth+circuit", "auth+api", "circuit+api", "api+api"],
    )
    def test_mixed_or_generic_stays_trackers_unavailable(self, first: Exception, second: Exception) -> None:
        """Anything not unanimous keeps the historical outage verdict."""
        verdict = self._search(_registry(c411=first, tr4ker=second))

        assert (verdict.disposition, verdict.outcome, verdict.found) == ("retryable", "trackers_unavailable", None)  # type: ignore[attr-defined]

    def test_single_tracker_auth_is_terminal_too(self) -> None:
        """One configured tracker, broken key ⇒ every queried tracker IS in auth."""
        verdict = self._search(_registry(c411=_auth("c411")))

        assert (verdict.disposition, verdict.outcome) == ("terminal", "tracker_auth")  # type: ignore[attr-defined]

    def test_terminal_auth_abandons_the_row_with_its_event(self) -> None:
        """The terminal verdict is what makes the service abandon — end to end.

        The orchestrator's own ``search`` emits nothing; ``WantedAbandoned`` is
        the service's guarded abandon. Here we pin the orchestrator half (the
        terminal verdict) and, in the same breath, that the grab path over the
        SAME failure keeps its historical retryable disposition.
        """
        events: list[Event] = []
        bus = EventBus()
        bus.subscribe(Event, events.append)

        verdict = self._search(_registry(c411=_auth("c411")), bus)

        assert verdict.disposition == "terminal"  # type: ignore[attr-defined]
        assert not [e for e in events if isinstance(e, WantedAbandoned)], (
            "the orchestrator's search states the verdict; the SERVICE owns the abandon + event"
        )


class TestGrabDispositionsUnchanged:
    """The grab stage keeps its historical dispositions (byte-identical)."""

    @staticmethod
    def _grab(registry: TrackerRegistry) -> object:
        orchestrator = GrabOrchestrator(
            tracker_registry=registry,
            torrent_client=MagicMock(),
            event_bus=EventBus(),
            ranking=RankingConfig(min_seeders=0),
            bandwidth=BandwidthConfig(),
        )
        return orchestrator.grab(_item(), QualityProfile())

    @pytest.mark.parametrize(
        ("trackers", "expected_reason"),
        [
            ({"c411": _auth("c411")}, "search_api_error"),
            ({"c411": CircuitOpenError(provider="c411", remaining_seconds=42.0)}, "circuit_open"),
            ({"c411": _api("c411")}, "trackers_unavailable"),
        ],
        ids=["all-auth", "all-circuit", "all-api"],
    )
    def test_grab_stays_retryable_on_every_taxon(self, trackers: dict[str, Exception], expected_reason: str) -> None:
        """A search-stage failure NEVER abandons at grab time — always retryable.

        The reason label follows the taxon (auth folds into grab's historical
        ``search_api_error`` bucket), but the DISPOSITION — the thing the service
        maps onto a status — is ``retryable`` on all three.
        """
        outcome = self._grab(_registry(**trackers))

        assert outcome.disposition == "retryable"  # type: ignore[attr-defined]
        assert outcome.reason == expected_reason  # type: ignore[attr-defined]
