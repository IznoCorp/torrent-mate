"""TrackerRegistry — query trackers in priority order and rank merged results.

Implements DESIGN §6.4: a multi-tracker orchestrator that calls each
configured TrackerClient in priority order, collects all TrackerResult
instances, and returns them ranked via ``rank()``. Failures of individual
trackers are logged and do not abort the search.
"""

import xml.parsers.expat

import requests

from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.tracker._base import TrackerClient, TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig, rank
from personalscraper.logger import get_logger

log = get_logger("api.tracker.registry")


class TrackerRegistry:
    """Coordinates searches across multiple TrackerClient providers.

    Trackers are queried in the order given by ``priority``. Trackers not
    present in ``trackers`` are silently skipped. Exceptions raised by a
    tracker's ``search()`` are logged at warning level and do not
    propagate — partial results from healthy trackers are still ranked
    and returned.

    Attributes:
        _trackers: Map of tracker name → TrackerClient instance.
        _priority: Ordered list of tracker names (highest priority first).
        _ranking: RankingConfig applied to merged results.
    """

    def __init__(
        self,
        trackers: dict[str, TrackerClient],
        priority: list[str],
        ranking: RankingConfig,
    ) -> None:
        """Initialize the registry.

        Args:
            trackers: Map of tracker name → TrackerClient instance.
            priority: Ordered list of tracker names (highest priority first).
            ranking: Ranking configuration applied to merged results.
        """
        self._trackers = trackers
        self._priority = priority
        self._ranking = ranking

    def search_all(
        self,
        query: str,
        media_type: MediaType = "movie",
        year: int | None = None,
    ) -> list[tuple[TrackerResult, int]]:
        """Search all configured trackers and return ranked merged results.

        Args:
            query: Search query string.
            media_type: Either "movie" or "tv" (provider-specific dialects honored downstream).
            year: Optional release year to scope the search.

        Returns:
            Ranked list of ``(result, score)`` pairs, highest score first.
        """
        results: list[TrackerResult] = []
        for name in self._priority:
            client = self._trackers.get(name)
            if client is None:
                continue
            try:
                results.extend(client.search(query, media_type, year))
            except (
                ApiError,
                requests.RequestException,
                ValueError,  # JSON decode, payload validation
                TypeError,  # response-shape drift (wrong type returned)
                xml.parsers.expat.ExpatError,  # malformed XML from c411 / Torznab
            ):
                # Operational failures (network, malformed payload, schema drift)
                # are logged and the surviving trackers' results are still ranked.
                # Programming errors (KeyError, AttributeError, …) are *not*
                # caught here — they indicate a code bug that must surface.
                # Trackers whose parsers may surface KeyError/IndexError on schema
                # drift must wrap their parse code and re-raise as ApiError so the
                # error stays operational rather than crashing every other tracker.
                log.warning("tracker_search_failed", tracker=name, exc_info=True)
        return rank(results, self._ranking)
