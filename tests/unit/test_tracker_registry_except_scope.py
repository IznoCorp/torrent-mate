"""Behavioural tests for TrackerRegistry.search_all except-clause scope.

PR #19 review finding C4: the previous bare ``except Exception`` swallowed
*everything*, including programming errors that should crash a developer's
test rather than silently degrade the search. The narrowed tuple
``(ApiError, requests.RequestException, ValueError, TypeError, ExpatError)``
must:

1. **Swallow operational errors** — network failure, malformed payload,
   schema drift, XML parsing — and still return ranked results from the
   surviving trackers.
2. **Propagate programming errors** — ``KeyError``, ``AttributeError``,
   ``RuntimeError`` — so they surface during development instead of
   degrading silently in production.

These tests pin both halves of the contract.
"""

from __future__ import annotations

import xml.parsers.expat

import pytest
import requests

from personalscraper.api._contracts import ApiError
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
        ApiError(provider="lacale", http_status=503, message="upstream down"),
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
        trackers={"lacale": _RaisingTracker(exc), "c411": _OkTracker("c411")},  # type: ignore[dict-item]
        priority=["lacale", "c411"],
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
        trackers={"lacale": _RaisingTracker(exc_type(*exc_args))},  # type: ignore[dict-item]
        priority=["lacale"],
        ranking=RankingConfig(min_seeders=0),
    )

    with pytest.raises(exc_type):
        registry.search_all("Inception")
