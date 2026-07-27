"""C411 tracker client — Torznab/Newznab XML API.

Implements TrackerClient Protocol against C411's Torznab indexer endpoint.
See ``docs/reference/c411-api.md`` for endpoint and field reference.

Field shapes are validated against live samples captured 2026-05-07 in
``docs/reference/_samples/c411/``.

C411 particularities (live-confirmed):
- Torznab/Newznab XML protocol; HttpTransport handles parsing via
  ``response_format='xml'`` (xmltodict).
- API key sent as ``apikey=`` query param (Torznab convention).
- ``<guid>`` is the 40-char infohash (not a URL).
- No item-level ``<category>`` element — only ``torznab:attr name="category"``.
- ``<size>`` is duplicated across ``<size>`` element, ``enclosure[@length]``,
  and ``torznab:attr[size]`` — pick any (we use the dedicated element).
- ``peers`` and ``seeders`` may be equal when no leechers; clamp leechers
  to ``max(0, peers - seeders)``.
- ``downloadvolumefactor`` flags freeleech (=0) / silver-leech (=0.5).
- Caps does NOT advertise ``cat`` in supportedParams — narrowing is via
  ``t=movie`` / ``t=tvsearch`` only.
- Categories use Newznab class as ``@name`` and human label as ``@description``.
- ``enclosure[@url]`` embeds the apikey inline (sensitive — redact in logs).
- Auth failure: HTTP 401 + ``<error code="100" description="..."/>``.

Title parsing uses the shared ``api.tracker._quality.parse_title_quality`` —
every tracker (lacale/c411/torr9) encodes quality markers in the title
identically, so they all extract the same tokens through one regex table.
"""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, ClassVar, cast

from personalscraper.api._contracts import ApiError, MediaType, ProviderName
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult, wrap_parser_drift
from personalscraper.api.tracker._contracts import (
    CategoryListable,
    TorrentSearchable,
)
from personalscraper.api.tracker._quality import parse_title_quality
from personalscraper.api.transport._auth import ApiKeyAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from personalscraper.conf.models.api_config import TrackerProviderConfig
    from personalscraper.core.event_bus import EventBus


log = get_logger("api.tracker.c411")


def _as_list(value: Any) -> list[Any]:
    """Coerce xmltodict's "single-or-list" output to always-list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _attrs_to_dict(attrs: list[dict[str, Any]] | dict[str, Any] | None) -> dict[str, str]:
    """Flatten a Torznab attr list (or single dict) into ``{name: value}``."""
    out: dict[str, str] = {}
    for attr in _as_list(attrs):
        name = attr.get("@name")
        value = attr.get("@value")
        if isinstance(name, str) and isinstance(value, str):
            out[name] = value
    return out


def _parse_rfc2822(value: Any) -> datetime | None:
    """Parse an RFC 2822 timestamp (``<pubDate>``)."""
    if not isinstance(value, str):
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


class C411Client(TorrentSearchable, CategoryListable):
    """C411 tracker API client over Torznab XML.

    Composes
    :class:`~personalscraper.api.tracker._contracts.TorrentSearchable`
    and
    :class:`~personalscraper.api.tracker._contracts.CategoryListable`
    (sub-phase 11.3 — DESIGN §4). Notably *does not* implement
    :class:`~personalscraper.api.tracker._contracts.FreeleechAware`
    because the Torznab schema C411 exposes carries no per-torrent
    re-check endpoint (the freeleech state is captured at search time
    on :class:`TrackerResult.is_freeleech`). It also does not implement
    :class:`~personalscraper.api.tracker._contracts.TorrentDetailsProvider`
    because Torznab has no per-torrent detail endpoint.
    """

    provider_name: str = ProviderName.C411.value
    REQUIRED_CREDS: ClassVar[list[str]] = ["C411_API_KEY"]

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy:
        """Build a TransportPolicy for C411.

        Args:
            api_key: C411 API key (``C411_API_KEY`` env var).

        Returns:
            TransportPolicy with query-based ApiKeyAuth, XML response format,
            defensive rate limit, and the standard 5-fail / 5-min circuit.
        """
        return TransportPolicy(
            provider_name=ProviderName.C411,
            base_url="https://c411.org",
            auth=ApiKeyAuth(api_key, param="apikey", location="query"),
            timeout_seconds=15,
            retry=RetryPolicy(max_attempts=3),
            circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0),
            rate_limit=RateLimitPolicy(requests_per_second=0.5),
            response_format="xml",
        )

    @classmethod
    def from_env(
        cls,
        *,
        env: Mapping[str, str],
        event_bus: EventBus,
        required: list[str],
        provider_cfg: TrackerProviderConfig,
    ) -> C411Client:
        """Build C411Client from its single API key (the uniform factory contract).

        Implements the :class:`~personalscraper.api.tracker._contracts.TrackerConstructible`
        contract: the factory dispatches construction uniformly through
        ``from_env`` for every tracker. C411 is an api-key tracker, so it builds
        an HttpTransport from ``policy(env[required[0]])`` and ignores
        ``provider_cfg`` (no extra construction options).

        Args:
            env: Resolved credential source (registry passes the env mapping).
            event_bus: Event bus propagated to the HTTP transport.
            required: Ordered credential env-var names (``[C411_API_KEY]``).
            provider_cfg: Per-tracker config — unused for api-key trackers.

        Returns:
            A network-ready C411Client wrapping the authed transport.
        """
        del provider_cfg  # api-key tracker: no extra construction options
        api_key = env.get(required[0], "") if required else ""
        transport = HttpTransport(cls.policy(api_key), event_bus=event_bus)
        return cls(transport)

    def __init__(self, transport: HttpTransport) -> None:
        """Initialize the client.

        Args:
            transport: HttpTransport pre-configured with the C411 policy.
        """
        self._transport = transport

    @property
    def _open_transport(self) -> HttpTransport:
        """The HTTP transport (always materialized for an api-key client).

        Uniform peek for the registry seams (see Torr9Client._open_transport):
        api-key trackers build their transport at construction, so this simply
        returns ``self._transport`` with no laziness.
        """
        return self._transport

    # -- TrackerClient Protocol ---------------------------------------------

    def search(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[TrackerResult]:
        """Search C411 via the Torznab API.

        Routes to the specialized ``t=movie`` / ``t=tvsearch`` endpoints when
        ``media_type`` is ``"movie"`` / ``"tv"``, falling back to ``t=search``
        otherwise. Caps does not advertise ``cat`` so no category filter is
        sent.

        Args:
            query: Free-text search query.
            media_type: ``"movie"``, ``"tv"``, or any other value (→ ``t=search``).
            year: Optional release year — appended to ``q`` when given.

        Returns:
            List of TrackerResult ordered as the indexer returned them.
        """
        endpoint = {
            "movie": "movie",
            "tv": "tvsearch",
        }.get(media_type, "search")

        q = f"{query} {year}" if year is not None else query
        params: dict[str, Any] = {"t": endpoint, "q": q}

        raw = self._transport.get(path="/api", params=params)
        return wrap_parser_drift(
            self.provider_name,
            lambda: self._parse_rss(cast("dict[str, Any]", raw)),
        )

    def get_categories(self) -> dict[str, str]:
        """Fetch the C411 caps document and flatten the categories tree.

        Newznab subcat IDs collide across parents (e.g. multiple `4050`),
        so we key the dict by the unique ``description`` (per parent label,
        which is the actual French native subcategory name) → ``id`` of the
        Newznab class. The shape follows LaCale's ``slug → human`` contract
        modulo "id is a numeric Newznab class, not a slug".

        Returns:
            Mapping ``description → newznab_id`` (e.g. ``"Animation": "2060"``).
            Top-level categories included as ``@description → @id``.
        """
        raw = self._transport.get(path="/api", params={"t": "caps"})
        data = cast("dict[str, Any]", raw)

        caps = data.get("caps") or data
        cats_node = caps.get("categories") or {}
        out: dict[str, str] = {}
        for cat in _as_list(cats_node.get("category")):
            cat_desc = cat.get("@description") or cat.get("@name")
            cat_id = cat.get("@id")
            if isinstance(cat_desc, str) and isinstance(cat_id, str):
                out[cat_desc] = cat_id
            for sub in _as_list(cat.get("subcat")):
                sub_desc = sub.get("@description") or sub.get("@name")
                sub_id = sub.get("@id")
                if isinstance(sub_desc, str) and isinstance(sub_id, str):
                    out[sub_desc] = sub_id
        return out

    # -- Internal helpers ---------------------------------------------------

    def _parse_rss(self, data: dict[str, Any]) -> list[TrackerResult]:
        """Parse the xmltodict-decoded Torznab RSS response."""
        # Auth/syntax errors arrive as <error code='100' description='...' />
        # at the document root (HTTP status already non-200 in this case).
        if "error" in data:
            err = data["error"]
            raise ApiError(
                provider=self.provider_name,
                http_status=int(err.get("@code", 0) or 0),
                message=str(err.get("@description", "C411 error")),
            )

        rss = data.get("rss") or {}
        channel = rss.get("channel") or {}
        items = _as_list(channel.get("item"))
        return [self._parse_item(item) for item in items]

    def _parse_item(self, item: dict[str, Any]) -> TrackerResult:
        """Map one Torznab `<item>` to a TrackerResult."""
        title = str(item.get("title", ""))
        attrs = _attrs_to_dict(item.get("torznab:attr"))

        size_raw = item.get("size") or attrs.get("size") or _enclosure_length(item) or 0
        size = ByteSize.parse(int(size_raw)) if str(size_raw).isdigit() else ByteSize.parse(0)

        seeders = int(attrs.get("seeders", "0") or 0)
        peers = int(attrs.get("peers", str(seeders)) or 0)
        leechers = max(0, peers - seeders)

        dvf = attrs.get("downloadvolumefactor", "1")
        is_freeleech = dvf == "0"
        is_silverleech = dvf == "0.5"

        info_hash = attrs.get("infohash") or str(item.get("guid", ""))
        download_url = _enclosure_url(item)
        source_url = item.get("comments") or item.get("link")

        title_parsed = parse_title_quality(title)

        return TrackerResult(
            provider=self.provider_name,
            tracker_id=str(item.get("guid", "")),
            title=title,
            size=size,
            seeders=seeders,
            leechers=leechers,
            category=attrs.get("category"),
            download_url=download_url,
            info_hash=info_hash,
            source_url=source_url,
            is_freeleech=is_freeleech,
            is_silverleech=is_silverleech,
            upload_date=_parse_rfc2822(item.get("pubDate")),
            format=title_parsed.get("format"),
            codec=title_parsed.get("codec"),
            source=title_parsed.get("source"),
            resolution=title_parsed.get("resolution"),
            audio=title_parsed.get("audio"),
        )


def _enclosure_url(item: dict[str, Any]) -> str | None:
    enc = item.get("enclosure")
    if isinstance(enc, dict):
        url = enc.get("@url")
        return url if isinstance(url, str) else None
    return None


def _enclosure_length(item: dict[str, Any]) -> str | None:
    enc = item.get("enclosure")
    if isinstance(enc, dict):
        length = enc.get("@length")
        return length if isinstance(length, str) else None
    return None
