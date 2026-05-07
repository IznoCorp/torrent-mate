"""LaCale tracker client.

Implements TrackerClient Protocol against the LaCale tracker JSON API.
See ``docs/reference/lacale-api.md`` for endpoint and field reference.

LaCale particularities:
- API key sent as ``X-Api-Key`` header (preferred) or ``apikey=`` query.
- Search returns at most 20 items, sorted by pubDate desc, server-cached ~30s.
- Quality fields (codec/source/audio/resolution/format) are NOT in the JSON;
  they are encoded in the torrent ``title`` and must be regex-extracted.
- Freeleech / silverleech indicators are encoded as ``[FreeLeech]`` /
  ``[SilverLeech]`` title prefixes — also extracted by the title parser.
- ``size`` is raw bytes (int).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, cast

from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
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
        r"\b(truehd|atmos|dts[- ]hd|dts|ddp?5\.1|aac|ac3|flac|mp3)\b",
        re.IGNORECASE,
    ),
    "format": re.compile(r"\.(mkv|mp4|avi|m4v|wmv|mov)$", re.IGNORECASE),
}

_FREELEECH_RE = re.compile(r"\[FreeLeech\]", re.IGNORECASE)
_SILVERLEECH_RE = re.compile(r"\[SilverLeech\]", re.IGNORECASE)


class LaCaleClient:
    """LaCale tracker API client.

    Wraps an HttpTransport pre-configured with the LaCale ``TransportPolicy``.
    Implements the TrackerClient Protocol from ``api/tracker/_base.py``.
    """

    provider_name: str = "lacale"
    REQUIRED_CREDS: ClassVar[list[str]] = ["LACALE_API_KEY"]

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy:
        """Build a TransportPolicy for LaCale.

        Args:
            api_key: LaCale API key (``LACALE_API_KEY`` env var).

        Returns:
            TransportPolicy with header-based ApiKeyAuth, defensive rate limit,
            and the standard 5-fail / 5-min circuit settings.
        """
        return TransportPolicy(
            provider_name="lacale",
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
        media_type: str = "movie",
        year: int | None = None,
    ) -> list[TrackerResult]:
        """Search the LaCale tracker.

        Args:
            query: Free-text search query (max 200 chars enforced server-side).
            media_type: Reserved for registry-level category routing — not
                forwarded as ``cat`` here (caller supplies category slugs via
                the registry layer if narrowing is required).
            year: Optional release year. LaCale's search has no year parameter,
                so this is appended to the query string when provided.

        Returns:
            List of TrackerResult ordered as returned by the API (pubDate desc).
        """
        del media_type  # Unused — category narrowing happens at registry level.

        q = f"{query} {year}" if year is not None else query
        params: dict[str, Any] = {"q": q}

        raw = self._transport.get(path="/api/external", params=params)
        items = cast("list[dict[str, Any]]", raw)
        return [self._parse_item(item) for item in items]

    def get_categories(self) -> dict[str, str]:
        """Fetch the LaCale category taxonomy as a flat slug → name map.

        Walks ``categories[].children[]`` recursively. ``tagGroups`` and
        ``ungroupedTags`` (upload-only) are ignored.

        Returns:
            Mapping of category slug → display name.
        """
        raw = self._transport.get(path="/api/external/meta")
        data = cast("dict[str, Any]", raw)

        result: dict[str, str] = {}
        for cat in data.get("categories", []):
            self._collect_category(cat, result)
        return result

    # -- Internal helpers ---------------------------------------------------

    @staticmethod
    def _collect_category(node: dict[str, Any], out: dict[str, str]) -> None:
        slug = node.get("slug")
        name = node.get("name")
        if isinstance(slug, str) and isinstance(name, str):
            out[slug] = name
        for child in node.get("children", []) or []:
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
            is_freeleech=bool(parsed.get("is_freeleech", False)),
            is_silverleech=bool(parsed.get("is_silverleech", False)),
            upload_date=upload_date,
            format=cast("str | None", parsed.get("format")),
            codec=cast("str | None", parsed.get("codec")),
            source=cast("str | None", parsed.get("source")),
            resolution=cast("str | None", parsed.get("resolution")),
            audio=cast("str | None", parsed.get("audio")),
        )

    @staticmethod
    def _parse_title(title: str) -> dict[str, str | bool | None]:
        """Extract quality fields and freeleech flags from a torrent title.

        Args:
            title: Raw torrent title (may include ``[FreeLeech]`` / ``[SilverLeech]`` prefix).

        Returns:
            Dict with keys: resolution, codec, source, audio, format,
            is_freeleech, is_silverleech. Quality fields are None when no
            pattern matches.
        """
        is_freeleech = bool(_FREELEECH_RE.search(title))
        is_silverleech = bool(_SILVERLEECH_RE.search(title))

        cleaned = _FREELEECH_RE.sub("", title)
        cleaned = _SILVERLEECH_RE.sub("", cleaned)

        out: dict[str, str | bool | None] = {
            "is_freeleech": is_freeleech,
            "is_silverleech": is_silverleech,
        }
        for field, pattern in _TITLE_PATTERNS.items():
            match = pattern.search(cleaned)
            out[field] = match.group(1) if match else None
        return out


def _parse_iso(value: Any) -> datetime | None:
    """Parse an ISO 8601 string. Returns None for missing/invalid input."""
    if not isinstance(value, str):
        return None
    s = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
