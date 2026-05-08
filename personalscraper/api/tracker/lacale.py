"""LaCale tracker client.

Implements TrackerClient Protocol against the LaCale tracker JSON API.
See ``docs/reference/lacale-api.md`` for endpoint and field reference.

Field shapes are validated against live samples captured 2026-05-07 in
``docs/reference/_samples/lacale/``.

LaCale particularities (live-confirmed):
- API key sent as ``X-Api-Key`` header (preferred) or ``apikey=`` query.
- Search returns at most 20 items, sorted by pubDate desc, server-cached ~30s.
- Quality fields (codec/source/audio/resolution/format) are NOT in the JSON;
  they are encoded in the torrent ``title`` and regex-extracted.
- **No** freeleech / silverleech indicator exists — neither title prefix
  nor JSON flag. ``is_freeleech`` and ``is_silverleech`` are always ``False``.
- ``size`` is raw bytes (int). ``leechers`` is a direct int field.
- ``guid`` is a short opaque ID (~20 chars), distinct from ``infoHash``.
- ``downloadLink`` is ``/api/download/<infoHash>?token=<JWT>``; the JWT is
  per-request and time-bound — treat as sensitive.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, cast

from personalscraper.api._contracts import MediaType, ProviderName
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult, wrap_parser_drift
from personalscraper.api.transport._auth import ApiKeyAuth
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport

log = get_logger("api.tracker.lacale")


_TITLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "resolution": re.compile(r"\b(2160p|1080p|720p|480p|4k|uhd)\b", re.IGNORECASE),
    "codec": re.compile(r"\b(x265|x264|h\.?265|h\.?264|hevc|av1|xvid|divx)\b", re.IGNORECASE),
    "source": re.compile(
        r"\b(uhd[. ]bluray|bluray|brrip|web[- ]?dl|webrip|hdtv|dvdrip)\b",
        re.IGNORECASE,
    ),
    "audio": re.compile(
        r"\b(truehd|atmos|dts[- ]?hd|dts|ddp?5\.1|aac|ac3|flac|mp3)\b",
        re.IGNORECASE,
    ),
    "format": re.compile(r"\.(mkv|mp4|avi|m4v|wmv|mov)$", re.IGNORECASE),
}


class LaCaleClient:
    """LaCale tracker API client.

    Wraps an HttpTransport pre-configured with the LaCale ``TransportPolicy``.
    Implements the TrackerClient Protocol from ``api/tracker/_base.py``.
    """

    provider_name: str = ProviderName.LACALE.value
    REQUIRED_CREDS: ClassVar[list[str]] = ["LACALE_API_KEY"]

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy:
        """Build a TransportPolicy for LaCale.

        Args:
            api_key: LaCale API key (``LACALE_API_KEY`` env var) — distinct
                from the BitTorrent announce passkey.

        Returns:
            TransportPolicy with header-based ApiKeyAuth, defensive rate limit,
            and the standard 5-fail / 5-min circuit settings.
        """
        return TransportPolicy(
            provider_name=ProviderName.LACALE,
            base_url="https://la-cale.space",
            auth=ApiKeyAuth(api_key, param="X-Api-Key", location="header"),
            timeout_seconds=15,
            retry=RetryPolicy(max_attempts=3),
            circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0),
            rate_limit=RateLimitPolicy(requests_per_second=0.5),
        )

    def __init__(self, transport: HttpTransport) -> None:
        """Initialize the client.

        Args:
            transport: HttpTransport pre-configured with the LaCale policy.
        """
        self._transport = transport

    # -- TrackerClient Protocol ---------------------------------------------

    def search(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[TrackerResult]:
        """Search the LaCale tracker.

        Args:
            query: Free-text search query (max 200 chars enforced server-side).
            media_type: Reserved for registry-level category routing — not
                forwarded as ``cat`` here (callers narrow via the registry).
            year: Optional release year. LaCale's search has no dedicated year
                parameter, so this is appended to the query string when given.

        Returns:
            List of TrackerResult ordered as returned by the API (pubDate desc).
        """
        del media_type  # Unused — narrowing happens at registry level.

        q = f"{query} {year}" if year is not None else query
        params: dict[str, Any] = {"q": q}

        raw = self._transport.get(path="/api/external", params=params)

        def _parse() -> list[TrackerResult]:
            items = cast("list[dict[str, Any]]", raw)
            return [self._parse_item(item) for item in items]

        return wrap_parser_drift(self.provider_name, _parse)

    def get_categories(self) -> dict[str, str]:
        """Fetch the LaCale category taxonomy as a flat slug → human label map.

        Walks ``categories[].children[]`` recursively. ``children`` is ``null``
        on leaf nodes — treated as empty.

        Returns:
            Mapping of category slug → display name (e.g. ``"films": "Films"``).
        """
        raw = self._transport.get(path="/api/external/meta")
        data = cast("dict[str, Any]", raw)

        result: dict[str, str] = {}
        for cat in data.get("categories", []) or []:
            self._collect_category(cat, result)
        return result

    # -- Internal helpers ---------------------------------------------------

    @staticmethod
    def _collect_category(node: dict[str, Any], out: dict[str, str]) -> None:
        slug = node.get("slug")
        name = node.get("name")
        if isinstance(slug, str) and isinstance(name, str):
            out[slug] = name
        for child in node.get("children") or []:
            LaCaleClient._collect_category(child, out)

    def _parse_item(self, item: dict[str, Any]) -> TrackerResult:
        """Map one LaCale JSON item to a TrackerResult."""
        title = str(item.get("title", ""))
        parsed = self._parse_title(title)

        size_raw = item.get("size", 0)
        size = ByteSize.parse(int(size_raw)) if isinstance(size_raw, int | float | str) else ByteSize.parse(0)

        upload_date = _parse_iso(item.get("pubDate"))

        return TrackerResult(
            provider=self.provider_name,
            tracker_id=str(item.get("guid", "")),
            title=title,
            size=size,
            seeders=int(item.get("seeders", 0)),
            leechers=int(item.get("leechers", 0)),
            category=item.get("category"),
            download_url=item.get("downloadLink"),
            info_hash=item.get("infoHash"),
            source_url=item.get("link"),
            is_freeleech=False,
            is_silverleech=False,
            upload_date=upload_date,
            format=parsed.get("format"),
            codec=parsed.get("codec"),
            source=parsed.get("source"),
            resolution=parsed.get("resolution"),
            audio=parsed.get("audio"),
        )

    @staticmethod
    def _parse_title(title: str) -> dict[str, str | None]:
        """Extract quality fields from a torrent title.

        Args:
            title: Raw torrent title.

        Returns:
            Dict with keys: resolution, codec, source, audio, format. Values
            are None when no pattern matches. Freeleech/silverleech flags are
            NOT included — LaCale exposes no signal for them in search responses.
        """
        out: dict[str, str | None] = {}
        for field, pattern in _TITLE_PATTERNS.items():
            match = pattern.search(title)
            out[field] = match.group(1) if match else None
        return out


def _parse_iso(value: Any) -> datetime | None:
    """Parse an ISO 8601 string with optional milliseconds and ``Z`` suffix."""
    if not isinstance(value, str):
        return None
    s = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
