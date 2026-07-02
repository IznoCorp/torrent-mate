"""TrackerRegistry — query trackers in priority order and rank merged results.

Implements DESIGN §6.4: a multi-tracker orchestrator that calls each
configured TorrentSearchable in priority order, collects all TrackerResult
instances, and returns them ranked via ``rank()``. Failures of individual
trackers are logged and do not abort the search.
"""

from __future__ import annotations

import xml.parsers.expat
from typing import TYPE_CHECKING

import requests

from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._contracts import TorrentSearchable
from personalscraper.api.tracker._ranking import RankingConfig, rank
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._dedup import SearchOutcome
    from personalscraper.api.transport._http import HttpTransport

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

    def search_candidates(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> "SearchOutcome":
        """Search every tracker and return a raw, un-ranked :class:`SearchOutcome`.

        Unlike :meth:`search_all`, this method:

        - returns the merged result list **un-ranked** (no ``rank()`` call) —
          the grab orchestrator applies hard-filters + dedup + ranking itself;
        - counts how many trackers were queried vs how many errored, so the
          caller can tell a transient outage (``all_errored`` → retryable) from
          a clean zero-hit search (→ terminal ``no_candidates``). See DESIGN §6.2.

        The per-tracker loop mirrors :meth:`search_all` exactly — same priority
        order, same narrowed ``except`` (operational failures swallowed and
        logged; programming errors propagate).

        Args:
            query: Search query string.
            media_type: ``MediaType.MOVIE`` or ``MediaType.TV``. Also the lookup
                key for the optional ``priority_by_media_type`` override map.
            year: Optional release year to scope the search.

        Returns:
            A :class:`~personalscraper.acquire._dedup.SearchOutcome` carrying the
            raw result list plus ``trackers_queried`` / ``trackers_errored``.
        """
        from personalscraper.acquire._dedup import (
            SearchOutcome,  # noqa: PLC0415 — lazy: avoids api→acquire import cycle
        )

        all_results: list[TrackerResult] = []
        queried = 0
        errored = 0
        errored_names: list[str] = []
        queried_names: list[str] = []
        for name in self._priority_for(str(media_type)):
            client = self._trackers.get(name)
            if client is None:
                log.warning("tracker_unavailable", tracker=name)
                continue
            queried += 1
            queried_names.append(name)
            try:
                all_results.extend(client.search(query, media_type, year))
            except (
                ApiError,
                requests.RequestException,
                ValueError,  # JSON decode, payload validation
                TypeError,  # response-shape drift (wrong type returned)
                xml.parsers.expat.ExpatError,  # malformed XML from c411 / Torznab
            ):
                # Same fail-soft contract as ``search_all``: operational failures
                # are logged and counted; the surviving trackers' results stand.
                log.warning("tracker_search_failed", tracker=name, exc_info=True)
                errored += 1
                errored_names.append(name)
        return SearchOutcome(
            results=all_results,
            trackers_queried=queried,
            trackers_errored=errored,
            errored_names=errored_names,
            queried_names=queried_names,
        )

    def transports(self) -> "dict[str, HttpTransport]":
        """Return a ``{tracker name → HttpTransport}`` map for the grab seam.

        The grab orchestrator passes these transports to ``resolve_source`` /
        ``fetch_torrent_source`` (DESIGN §6.1). Only clients exposing a non-None
        ``_open_transport`` are included — a non-triggering PEEK at the
        already-materialized transport. No new public surface is added.

        Crucially, this peeks ``_open_transport`` (NOT the login-triggering lazy
        ``_transport`` property): a lazy tracker (torr9's TVDB pattern) therefore
        appears here ONLY when it logged in during a prior search — exactly when
        ``resolve_source`` needs its transport. No spurious bootstrap login is
        ever fired by building this map.

        Returns:
            Dict mapping each tracker's lowercase wire name to its (materialized)
            transport.
        """
        result: dict[str, HttpTransport] = {}
        for name, client in self._trackers.items():
            transport = getattr(client, "_open_transport", None)
            if transport is not None:
                result[name] = transport
        return result

    def close(self) -> None:
        """Release the HttpTransport owned by each tracker client.

        Iterates ``self._trackers`` and calls ``close()`` on each client's
        already-materialized transport (peeked via ``_open_transport``) when
        present. Unlike ``ProviderRegistry.close()`` — which delegates to each
        provider's own ``close()`` — tracker clients expose no ``close()`` of
        their own, so the transport is closed directly. The parity with
        ``ProviderRegistry.close()`` is the fail-soft *shape*: iterate a
        copied list, swallow per-client exceptions at DEBUG level, and close
        as a no-op when the registry is empty — not the close target.

        Per-client exceptions are caught, logged at DEBUG level, and do not
        propagate — a failing close on one tracker must not prevent the others
        from releasing their sessions.

        Peeks ``_open_transport`` (NOT the login-triggering lazy ``_transport``
        property): a read-only command may tear the registry down without ever
        materializing a lazy tracker's transport (torr9's TVDB pattern). The peek
        returns None in that case, so close() closes ONLY materialized transports
        and never fires a spurious bootstrap login at teardown — which would
        otherwise hit the network and break the network-free-until-first-use
        guarantee.
        """
        for name, client in list(self._trackers.items()):
            transport = getattr(client, "_open_transport", None)
            if transport is None:
                continue
            close_fn = getattr(transport, "close", None)
            if not callable(close_fn):
                continue
            try:
                close_fn()
            except Exception as exc:  # noqa: BLE001
                log.debug(
                    "tracker_transport_close_failed",
                    tracker=name,
                    exc_type=type(exc).__name__,
                )
