"""Behavioural tests for TrackerRegistry except-clause scope (both search paths).

PR #19 review finding C4: the previous bare ``except Exception`` swallowed
*everything*, including programming errors that should crash a developer's
test rather than silently degrade the search. The narrowed tuple
``(ApiError, CircuitOpenError, requests.RequestException, ValueError,
TypeError, ExpatError)`` must:

1. **Swallow operational errors** — network failure, malformed payload,
   schema drift, XML parsing, an OPEN circuit breaker — and still return
   ranked results from the surviving trackers.
2. **Propagate programming errors** — ``KeyError``, ``AttributeError``,
   ``RuntimeError`` — so they surface during development instead of
   degrading silently in production.

These tests pin both halves of the contract.

``CircuitOpenError`` joined that tuple with the torznab feature (PR #322
review). It is a plain :exc:`Exception`, NOT an :exc:`ApiError`, so it used to
escape the per-tracker loop: an OPEN breaker on a LOW-priority tracker
discarded the results the HIGH-priority trackers had already returned in the
same call. That is the inverse of this class's documented contract, and it is
not theoretical — the operator's ``tracker.json5`` once carried the note that
a since-removed tracker was disabled outright "to stop CircuitOpenError
crashing grab".
:class:`TestOpenCircuitNeverDiscardsOtherTrackers` pins the ordering that
exposes it (healthy tracker FIRST, open breaker SECOND) on BOTH search paths.
"""

from __future__ import annotations

import xml.parsers.expat

import pytest
import requests

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry


def _result(provider: str, title: str, *, seeders: int = 10) -> TrackerResult:
    return TrackerResult(
        provider=provider,
        tracker_id=f"{provider}-{title}",
        title=title,
        size=ByteSize(bytes=1_000_000_000),
        seeders=seeders,
        leechers=1,
    )


class _RaisingTracker:
    """Stub tracker whose ``search()`` raises a configurable exception."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def search(self, query: str, media_type: str = "movie", year: int | None = None) -> list[TrackerResult]:
        raise self._exc

    def get_categories(self) -> dict[str, str]:
        return {}


class _OkTracker:
    """Stub tracker that returns one result so we can verify others survive."""

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def search(self, query: str, media_type: str = "movie", year: int | None = None) -> list[TrackerResult]:
        return [_result(self.provider, "Inception")]

    def get_categories(self) -> dict[str, str]:
        return {}


# -- Operational errors are swallowed; surviving trackers still yield ranked results --


@pytest.mark.parametrize(
    "exc",
    [
        ApiError(provider="tr4ker", http_status=503, message="upstream down"),
        CircuitOpenError("tr4ker", 287.4),
        requests.ConnectionError("dns failure"),
        requests.Timeout("read timeout"),
        ValueError("bad json"),
        TypeError("response shape drift"),
        xml.parsers.expat.ExpatError("malformed xml"),
    ],
)
def test_operational_failure_is_swallowed(exc: BaseException) -> None:
    """Operational failures must not abort the multi-tracker search."""
    registry = TrackerRegistry(
        trackers={"tr4ker": _RaisingTracker(exc), "c411": _OkTracker("c411")},  # type: ignore[dict-item]
        priority=["tr4ker", "c411"],
        ranking=RankingConfig(min_seeders=0),
    )

    ranked = registry.search_all("Inception")

    assert len(ranked) == 1, f"Expected the surviving tracker's result; got {ranked!r}"
    assert ranked[0][0].provider == "c411"


# -- Programming errors must propagate -----------------------------------------------


@pytest.mark.parametrize(
    "exc_type, exc_args",
    [
        (KeyError, ("missing-config-key",)),
        (AttributeError, ("'NoneType' object has no attribute 'foo'",)),
        (RuntimeError, ("invariant violated",)),
        (ZeroDivisionError, ("/ by zero",)),
    ],
)
def test_programming_error_propagates(exc_type: type[BaseException], exc_args: tuple[object, ...]) -> None:
    """Programming bugs (KeyError, AttributeError, RuntimeError…) must NOT be swallowed."""
    registry = TrackerRegistry(
        trackers={"tr4ker": _RaisingTracker(exc_type(*exc_args))},  # type: ignore[dict-item]
        priority=["tr4ker"],
        ranking=RankingConfig(min_seeders=0),
    )

    with pytest.raises(exc_type):
        registry.search_all("Inception")


# -- An OPEN circuit on one tracker never discards the others' results ---------------


class TestOpenCircuitNeverDiscardsOtherTrackers:
    """Regression — PR #322 review.

    Ordering is the whole point: the healthy tracker is queried FIRST and the
    circuit-open one SECOND, mirroring the production
    ``priority: ["c411", "tr4ker"]``. Before the fix, the second tracker's
    ``CircuitOpenError`` escaped the loop and took the first tracker's
    already-collected results with it, so both search paths returned nothing at
    all while c411 was perfectly healthy.
    """

    @staticmethod
    def _registry() -> TrackerRegistry:
        """Healthy tracker first, circuit-open tracker second (prod priority order)."""
        return TrackerRegistry(
            trackers={
                "c411": _OkTracker("c411"),  # type: ignore[dict-item]
                "tr4ker": _RaisingTracker(CircuitOpenError("tr4ker", 287.4)),  # type: ignore[dict-item]
            },
            priority=["c411", "tr4ker"],
            ranking=RankingConfig(min_seeders=0),
        )

    def test_search_all_keeps_the_healthy_trackers_results(self) -> None:
        """``search_all`` still ranks c411's result when tr4ker's breaker is OPEN."""
        ranked = self._registry().search_all("Inception")

        assert [r.provider for r, _ in ranked] == ["c411"]

    def test_search_candidates_keeps_results_and_names_the_open_tracker(self) -> None:
        """``search_candidates`` keeps the results AND reports the open tracker as errored."""
        outcome = self._registry().search_candidates("Inception")

        assert [r.provider for r in outcome.results] == ["c411"]
        assert outcome.trackers_queried == 2
        assert outcome.trackers_errored == 1
        assert outcome.errored_names == ["tr4ker"]
        # One tracker survived, so this is NOT an outage — the caller must not
        # read it as retryable-everything.
        assert outcome.all_errored is False

    def test_all_circuits_open_is_reported_as_a_full_outage(self) -> None:
        """When EVERY tracker is circuit-open, the outcome is still a clean outage.

        Swallowing the error must not disguise a total outage as a clean
        zero-hit search: ``all_errored`` stays True so the caller keeps the
        retryable ``trackers_unavailable`` verdict instead of abandoning the
        item as ``no_candidates``.
        """
        registry = TrackerRegistry(
            trackers={
                "c411": _RaisingTracker(CircuitOpenError("c411", 12.0)),  # type: ignore[dict-item]
                "tr4ker": _RaisingTracker(CircuitOpenError("tr4ker", 287.4)),  # type: ignore[dict-item]
            },
            priority=["c411", "tr4ker"],
            ranking=RankingConfig(min_seeders=0),
        )

        outcome = registry.search_candidates("Inception")

        assert outcome.results == []
        assert outcome.all_errored is True
        assert outcome.errored_names == ["c411", "tr4ker"]
