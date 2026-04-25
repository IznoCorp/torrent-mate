"""Two-tier YouTube search for trailer discovery.

Primary: YouTube Data API v3 ``search.list`` (requires ``YOUTUBE_API_KEY``).
Fallback: yt-dlp ``ytsearch1`` (no key, no quota, slower).

Returns the first video URL or ``None`` on failure. The fallback is invoked
transparently when the primary is unavailable (no key, quota exceeded, or
HTTP error) — callers do not need to know which tier produced the result.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import requests

from personalscraper.logger import get_logger
from personalscraper.scraper.circuit_breaker import CircuitBreaker
from personalscraper.scraper.json_ttl_cache import JsonTTLCache

log = get_logger(__name__)

_YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"

# Timeout for the primary HTTP call (seconds).
_SEARCH_TIMEOUT_SEC = 10

# Default quota accounting. Caller (orchestrator) overrides these from config.
_DEFAULT_DAILY_QUOTA_UNITS = 10_000
_DEFAULT_SEARCH_LIST_COST = 100


def _redact_url_key(url: str) -> str:
    """Strip the key= param from a URL for logging.

    Args:
        url: Original URL string that may contain ``key=<value>``.

    Returns:
        URL with the ``key`` query parameter value replaced by
        ``***REDACTED***``.
    """
    return re.sub(r"([?&])key=[^&]*", r"\1key=***REDACTED***", url)


class YoutubeSearch:
    """Two-tier YouTube searcher — v3 API primary + yt-dlp ytsearch fallback.

    All instance state is private (single-underscore prefix) — see ``__init__``
    for the per-attribute documentation. Public API: ``search()``.
    """

    def __init__(
        self,
        query_format: str,
        *,
        api_key: str,
        quota_cache: JsonTTLCache,
        breaker: CircuitBreaker,
        daily_quota_units: int = _DEFAULT_DAILY_QUOTA_UNITS,
        search_list_cost_units: int = _DEFAULT_SEARCH_LIST_COST,
    ) -> None:
        """Initialize with a query format string and auth material.

        Args:
            query_format: Template with ``{title}`` and ``{year}`` placeholders.
            api_key: YouTube Data API v3 key. Empty string forces fallback.
            quota_cache: Sidecar cache for today's quota units consumed.
            breaker: Circuit breaker dedicated to YouTube (NOT the TMDB one).
            daily_quota_units: Total units per day (default ``10_000``).
            search_list_cost_units: Units per ``search.list`` call (default ``100``).
        """
        self._query_format = query_format
        self._api_key = api_key
        self._quota = quota_cache
        self._breaker = breaker
        self._daily_quota_units = daily_quota_units
        self._search_list_cost_units = search_list_cost_units

    def search(self, title: str, year: int | None) -> str | None:
        """Search YouTube for a trailer and return the first video URL.

        Never raises: transport, schema, and quota failures all return ``None``
        and are recorded against the circuit breaker / quota counter.

        Args:
            title: Media title to search for.
            year: Release year (substituted into the query format, may be None).

        Returns:
            YouTube watch URL string, or ``None`` on failure / no results.
        """
        year_str = str(year) if year else ""
        query = self._query_format.format(title=title, year=year_str).strip()

        if self._api_key and self._breaker.can_proceed() and self._has_quota_left():
            url = self._primary_search(query)
            if url is not None:
                return url
            # Primary returned None (transport, HTTP, schema, or quota error). Log the
            # transition so JSON logs link the primary failure to the fallback attempt.
            log.info("youtube_fallback_invoked", reason="primary_returned_none", query=query)
        elif not self._api_key:
            log.debug("youtube_fallback_invoked", reason="no_api_key", query=query)
        elif not self._breaker.can_proceed():
            log.info("youtube_fallback_invoked", reason="breaker_open", query=query)
        else:
            log.info("youtube_fallback_invoked", reason="quota_exhausted", query=query)

        return self._fallback_search(query)

    # ------------------------------------------------------------------
    # Primary: YouTube Data API v3
    # ------------------------------------------------------------------

    def _primary_search(self, query: str) -> str | None:
        """Call YouTube Data API v3 ``search.list``. Returns URL or None.

        Args:
            query: URL-encoded search query string.

        Returns:
            YouTube watch URL for the first result, or ``None`` on any failure.
        """
        encoded_query = urllib.parse.quote_plus(query)
        url = f"{_YOUTUBE_SEARCH_URL}?part=snippet&type=video&maxResults=5&q={encoded_query}&key={self._api_key}"
        try:
            resp = requests.get(url, timeout=_SEARCH_TIMEOUT_SEC)
        except requests.RequestException as exc:
            log.warning(
                "youtube_primary_transport_error",
                query=query,
                url=_redact_url_key(url),
                error=str(exc),
            )
            self._breaker.record_failure(exc)
            return None

        # Charge quota once the call reaches the server, even on error paths
        # (Google bills quota even for 403/404 responses on some endpoints).
        self._consume_quota(self._search_list_cost_units)

        if resp.status_code == 403:
            log.info(
                "youtube_primary_quota_or_key_error",
                query=query,
                url=_redact_url_key(url),
            )
            # Freeze quota for the day to short-circuit future calls.
            self._mark_quota_exhausted()
            return None

        if not resp.ok:
            log.warning(
                "youtube_search_http_error",
                status_code=resp.status_code,
                query=query,
                url=_redact_url_key(url),
            )
            # Build a real requests.HTTPError (which the breaker counts on
            # status >= 500) so a sustained outage trips the circuit.
            http_err = requests.exceptions.HTTPError(f"YouTube primary HTTP {resp.status_code}")
            http_err.response = resp
            self._breaker.record_failure(http_err)
            return None

        try:
            data = resp.json()
        except ValueError as exc:
            log.warning("youtube_primary_non_json_response", query=query, error=str(exc))
            # Schema drift / HTML error page from a proxy: synthesize a
            # ConnectionError (which the breaker counts) so a sustained outage
            # eventually opens the circuit instead of being retried forever.
            self._breaker.record_failure(requests.exceptions.ConnectionError("YouTube primary returned non-JSON"))
            return None

        items = data.get("items") or []
        if not items:
            return None

        try:
            video_id = items[0]["id"]["videoId"]
        except (KeyError, TypeError) as exc:
            log.warning("youtube_primary_missing_video_id", query=query, error=str(exc))
            self._breaker.record_failure(requests.exceptions.ConnectionError("YouTube primary missing videoId"))
            return None

        self._breaker.record_success()
        return _WATCH_URL.format(video_id=video_id)

    # ------------------------------------------------------------------
    # Fallback: yt-dlp ytsearch1
    # ------------------------------------------------------------------

    def _fallback_search(self, query: str) -> str | None:
        """Use yt-dlp's ``ytsearch1`` pseudo-URL. No quota, no API key.

        Args:
            query: Plain-text search query.

        Returns:
            YouTube watch URL for the first result, or ``None`` on failure.
        """
        # Import lazily so test environments without yt-dlp still import the module.
        try:
            import yt_dlp
        except ImportError:
            log.error(
                "youtube_fallback_missing_yt_dlp",
                query=query,
            )
            return None

        opts: dict[str, Any] = {
            "default_search": "ytsearch1",
            "noplaylist": True,
            "quiet": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info: dict[str, Any] | None = ydl.extract_info(query, download=False)
        except yt_dlp.utils.DownloadError as exc:
            log.warning(
                "youtube_fallback_download_error",
                query=query,
                error=str(exc),
            )
            self._breaker.record_failure(exc)
            return None
        except Exception as exc:  # noqa: BLE001 — yt-dlp emits ExtractorError + KeyError variants
            # Sustained non-DownloadError yt-dlp failures (ExtractorError, KeyError
            # on malformed entries, network-glue exceptions) must trip the breaker
            # too — otherwise a yt-dlp upgrade with a regressed code path keeps
            # being retried forever. Synthesise a ConnectionError so the breaker
            # actually counts the failure (RuntimeError would be ignored).
            log.warning(
                "youtube_fallback_unexpected_error",
                query=query,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            self._breaker.record_failure(
                requests.exceptions.ConnectionError(f"yt-dlp fallback failed: {type(exc).__name__}")
            )
            return None

        entries = (info or {}).get("entries") or []
        if not entries:
            return None

        first = entries[0]
        video_id = first.get("id")
        if not video_id:
            log.warning(
                "youtube_fallback_missing_video_id",
                query=query,
                entry_keys=list(first.keys()),
            )
            return None

        self._breaker.record_success()
        return _WATCH_URL.format(video_id=video_id)

    # ------------------------------------------------------------------
    # Quota accounting
    # ------------------------------------------------------------------

    def _quota_key(self) -> str:
        """Return today's quota cache key, anchored to the UTC calendar date.

        Anchoring to UTC (not local time) keeps the rollover boundary aligned
        with Google's quota reset and avoids DST transitions silently
        re-using yesterday's bucket on local-tz machines.

        Returns:
            Cache key string in the form ``quota:YYYY-MM-DD``.
        """
        return f"quota:{datetime.now(timezone.utc).date().isoformat()}"

    def _has_quota_left(self) -> bool:
        """Return True when today's consumed units leave room for one more call.

        Returns:
            True if ``consumed + search_list_cost_units <= daily_quota_units``.
        """
        consumed = int(self._quota.get(self._quota_key()) or 0)
        return (consumed + self._search_list_cost_units) <= self._daily_quota_units

    def _consume_quota(self, units: int) -> None:
        """Record ``units`` consumed against today's budget.

        Args:
            units: Number of quota units to add to today's tally.
        """
        key = self._quota_key()
        consumed = int(self._quota.get(key) or 0)
        # TTL = 36 hours so yesterday's entry can be inspected if needed.
        self._quota.set(key, consumed + units, ttl_seconds=36 * 3600)

    def _mark_quota_exhausted(self) -> None:
        """Pin today's counter to the daily limit to force fallback immediately."""
        self._quota.set(
            self._quota_key(),
            self._daily_quota_units,
            ttl_seconds=36 * 3600,
        )


def youtube_api_key_from_env() -> str:
    """Read ``YOUTUBE_API_KEY`` from the environment.

    Returns an empty string when the key is unset — the caller treats that as
    "skip primary and go straight to fallback".

    Returns:
        API key string, or ``""`` if the environment variable is absent.
    """
    return os.environ.get("YOUTUBE_API_KEY", "").strip()
