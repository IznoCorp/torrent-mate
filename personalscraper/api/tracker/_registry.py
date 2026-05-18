"""TrackerRegistry — query trackers in priority order and rank merged results.

Implements DESIGN §6.4: a multi-tracker orchestrator that calls each
configured TorrentSearchable in priority order, collects all TrackerResult
instances, and returns them ranked via ``rank()``. Failures of individual
trackers are logged and do not abort the search.
"""

import xml.parsers.expat

import requests

from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._contracts import TorrentSearchable
from personalscraper.api.tracker._ranking import RankingConfig, rank
from personalscraper.logger import get_logger

log = get_logger("api.tracker.registry")


class TrackerRegistry:
    """Coordinates searches across multiple TorrentSearchable providers.

    Trackers are queried in the order given by ``priority``. Trackers not
    present in ``trackers`` are silently skipped. Exceptions raised by a
    tracker's ``search()`` are logged at warning level and do not
    propagate — partial results from healthy trackers are still ranked
    and returned.

    Attributes:
        _trackers: Map of tracker name → TorrentSearchable instance.
        _priority: Ordered list of tracker names (highest priority first).
        _ranking: RankingConfig applied to merged results.
    """

    def __init__(
        self,
        trackers: dict[str, TorrentSearchable],
        priority: list[str],
        ranking: RankingConfig,
        priority_by_media_type: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize the registry.

        Args:
            trackers: Map of tracker name → TorrentSearchable instance.
            priority: Ordered list of tracker names (highest priority first)
                used as the fallback when no per-media-type override
                applies.
            ranking: Ranking configuration applied to merged results.
            priority_by_media_type: Optional ``{media_type: [tracker, …]}``
                overrides keyed by the value passed to
                :meth:`search_all`. Provider-ids feature, sub-phase 12.1
                — DESIGN §6.7. ``None`` or ``{}`` falls back to
                ``priority`` for every call.
        """
        self._trackers = trackers
        self._priority = priority
        self._priority_by_media_type: dict[str, list[str]] = priority_by_media_type or {}
        self._ranking = ranking

    def _priority_for(self, media_type: str | None) -> list[str]:
        """Return the tracker order to use for the given ``media_type``.

        Falls back to ``self._priority`` whenever the override map has
        no matching key — DESIGN §6.7 explicitly allows unlisted media
        types to use the global default.
        """
        if media_type is None:
            return self._priority
        return self._priority_by_media_type.get(media_type, self._priority)

    def search_all(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[tuple[TrackerResult, int]]:
        """Search all configured trackers and return ranked merged results.

        Args:
            query: Search query string.
            media_type: Either "movie" or "tv" (provider-specific dialects honored downstream).
                Also used as the lookup key for the optional
                ``priority_by_media_type`` override map — when present
                with a matching key, that order replaces the global
                ``priority`` for this call.
            year: Optional release year to scope the search.

        Returns:
            Ranked list of ``(result, score)`` pairs, highest score first.
        """
        results: list[TrackerResult] = []
        for name in self._priority_for(str(media_type)):
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
                # See ``TorrentSearchable`` Protocol docstring for the parse-drift
                # wrapping contract that tracker authors must satisfy.
                log.warning("tracker_search_failed", tracker=name, exc_info=True)
        return rank(results, self._ranking)
