"""Generic Torznab/Newznab tracker client — one engine, many named configs.

Torznab is the de-facto search protocol of private trackers: a single XML/RSS
endpoint narrowed by a ``t=`` operation (``search`` / ``movie`` / ``tvsearch``
/ ``caps``), authenticated by an ``apikey=`` query parameter. Nine trackers out
of ten speak it, so the protocol logic lives here **once** and each tracker
contributes only a :class:`TorznabDescriptor` — base URL, endpoint names,
transport tuning and the handful of dialect quirks that genuinely differ.

The implementation is the one battle-tested in production against C411
(extracted verbatim from ``api/tracker/c411.py``); :class:`C411Client
<personalscraper.api.tracker.c411.C411Client>` is now its first named config,
with byte-identical behaviour.

Protocol-level invariants — true for every Torznab indexer, hence deliberately
**not** descriptor knobs:

- responses are XML; ``HttpTransport`` decodes them with xmltodict via
  ``response_format='xml'``;
- per-item metadata rides on repeated ``<torznab:attr name=… value=…/>``
  elements, flattened here into a ``{name: value}`` mapping;
- the ``tmdbid`` attr, when the indexer publishes it, feeds
  :attr:`TrackerResult.tmdb_id` and therefore the TMDB identity hard-filter;
- there is no per-torrent detail endpoint — hence no
  :class:`~personalscraper.api.tracker._contracts.TorrentDetailsProvider`, and
  no :class:`~personalscraper.api.tracker._contracts.FreeleechAware` either:
  the freeleech state is captured at search time from ``downloadvolumefactor``;
- errors arrive as a root ``<error code=… description=…/>`` document.

Title parsing uses the shared ``api.tracker._quality.parse_title_quality`` —
every tracker encodes quality markers in the title identically, so they all
extract the same tokens through one regex table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

from personalscraper.api._contracts import ApiError, MediaType, ProviderName
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult, wrap_parser_drift
from personalscraper.api.tracker._contracts import (
    CategoryListable,
    TorrentSearchable,
)
from personalscraper.api.tracker._errors import AUTH_HTTP_STATUSES, TrackerAuthError
from personalscraper.api.tracker._quality import parse_title_quality
from personalscraper.api.transport._auth import ApiKeyAuth, ApiKeyLocation
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from personalscraper.conf.models.api_config import TrackerProviderConfig
    from personalscraper.core.event_bus import EventBus


#: Torznab/Newznab error codes that mean « your credential is not valid »:
#: 100 incorrect user credentials, 101 account suspended, 102 insufficient
#: privileges. Permanent until an operator acts, hence :exc:`TrackerAuthError`.
#: Deliberately NOT the 103-107 registration codes (this client never registers)
#: nor the 200-range request errors (those are OUR bug, not the key's).
_AUTH_ERROR_CODES: frozenset[int] = frozenset({100, 101, 102})


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


def _text_of(value: Any) -> str:
    """Return the text of an xmltodict node that may carry XML attributes.

    ``<guid>abc</guid>`` decodes to the plain string ``"abc"``, but
    ``<guid isPermaLink="true">https://…</guid>`` decodes to
    ``{"@isPermaLink": "true", "#text": "https://…"}``. Without this, the second
    shape would stringify into a Python dict repr and land in
    :attr:`TrackerResult.tracker_id` (live-observed on Tr4ker, 2026-07-28).

    Args:
        value: The decoded node — a string, an attribute dict, or ``None``.

    Returns:
        The node's text, or ``""`` when absent.
    """
    if isinstance(value, dict):
        text = value.get("#text")
        return str(text) if text is not None else ""
    return str(value) if value is not None else ""


def _parse_optional_int(value: str | None) -> int | None:
    """Parse a Torznab attr value as an int, tolerating absence and garbage.

    Indexers publish ids as free-form strings: the attr may be missing entirely,
    empty, or carry a non-numeric id (an ``imdbid``-style ``tt1375666`` landing
    in the wrong attr). None of that may raise — the field is optional metadata.

    Args:
        value: Raw attr value, or ``None`` when the attr is absent.

    Returns:
        The parsed int, or ``None`` when absent / not an integer.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_rfc2822(value: Any) -> datetime | None:
    """Parse an RFC 2822 timestamp (``<pubDate>``)."""
    if not isinstance(value, str):
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class TorznabDescriptor:
    """Everything that makes one named Torznab tracker differ from another.

    A descriptor is pure data: no I/O, no branching logic. Adding a Torznab
    tracker is meant to be "one descriptor + one thin class", never a new
    parser.

    Attributes:
        provider: Canonical lowercase provider identifier (the wire name used
            in ``TrackerResult.provider``, the registry keys and ``ApiError``).
        display_name: Human label, used only in the fallback message of a root
            ``<error/>`` document (``"<display_name> error"``).
        base_url: Scheme + host of the indexer, no trailing path.
        api_path: Path of the Torznab endpoint on ``base_url``.
        apikey_param: Query/header parameter carrying the API key.
        apikey_location: Where the API key travels — Torznab says ``"query"``.
        movie_endpoint: ``t=`` value for a movie-scoped search.
        tv_endpoint: ``t=`` value for a TV-scoped search.
        default_endpoint: ``t=`` value for any other media type.
        caps_endpoint: ``t=`` value of the capabilities document.
        search_categories: Optional ``{media_type: cat}`` map. When it holds an
            entry for the searched media type, that value is sent as ``cat=``.
            Empty for indexers whose caps do not advertise ``cat`` support
            (C411) — nothing is then added to the query.
        item_category_element: Dialect quirk — ``True`` when the indexer emits
            a per-item ``<category>`` element and it is authoritative; ``False``
            when the category only exists as a ``torznab:attr`` (C411). The
            choice is exclusive on purpose: a wrong descriptor surfaces as a
            missing category instead of silently working through a fallback.
        guid_is_infohash: Dialect quirk — ``True`` when ``<guid>`` is the raw
            infohash and may back the ``infohash`` attr when it is absent
            (C411); ``False`` when ``<guid>`` is a URL or an opaque id.
        timeout_seconds: Per-request transport timeout.
        retry: Retry policy for transient failures.
        circuit: Circuit-breaker policy for durable outages.
        rate_limit: Defensive throttle applied to the indexer.
    """

    provider: ProviderName
    display_name: str
    base_url: str
    api_path: str = "/api"
    apikey_param: str = "apikey"
    apikey_location: ApiKeyLocation = "query"
    movie_endpoint: str = "movie"
    tv_endpoint: str = "tvsearch"
    default_endpoint: str = "search"
    caps_endpoint: str = "caps"
    search_categories: Mapping[str, str] = field(default_factory=dict)
    item_category_element: bool = False
    guid_is_infohash: bool = True
    timeout_seconds: float = 15
    retry: RetryPolicy = field(default_factory=lambda: RetryPolicy(max_attempts=3))
    circuit: CircuitPolicy = field(default_factory=lambda: CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0))
    rate_limit: RateLimitPolicy = field(default_factory=lambda: RateLimitPolicy(requests_per_second=0.5))

    @property
    def provider_name(self) -> str:
        """The lowercase wire name of this tracker (``provider`` as a plain str)."""
        return self.provider.value


class TorznabClient(TorrentSearchable, CategoryListable):
    """Torznab XML client, parameterized by a :class:`TorznabDescriptor`.

    Composes
    :class:`~personalscraper.api.tracker._contracts.TorrentSearchable`
    and
    :class:`~personalscraper.api.tracker._contracts.CategoryListable`
    (sub-phase 11.3 — DESIGN §4). Notably *does not* implement
    :class:`~personalscraper.api.tracker._contracts.FreeleechAware`
    because the Torznab schema carries no per-torrent re-check endpoint
    (the freeleech state is captured at search time on
    :class:`TrackerResult.is_freeleech`). It also does not implement
    :class:`~personalscraper.api.tracker._contracts.TorrentDetailsProvider`
    because Torznab has no per-torrent detail endpoint.

    A **named** tracker subclasses this client and sets the ``DESCRIPTOR``
    ClassVar (plus its ``REQUIRED_CREDS`` for activation) — that subclass
    carries no logic. The descriptor can also be passed per instance, which
    the generic tests use to exercise several dialects.
    """

    #: Descriptor of the named tracker — set by every concrete subclass.
    DESCRIPTOR: ClassVar[TorznabDescriptor]

    provider_name: str

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy:
        """Build a TransportPolicy from the class descriptor.

        Args:
            api_key: Tracker API key (resolved from the environment by the
                activation layer).

        Returns:
            TransportPolicy with query-based ApiKeyAuth, XML response format,
            and the descriptor's timeout / retry / circuit / rate-limit tuning.
        """
        descriptor = cls.DESCRIPTOR
        return TransportPolicy(
            provider_name=descriptor.provider,
            base_url=descriptor.base_url,
            auth=ApiKeyAuth(api_key, param=descriptor.apikey_param, location=descriptor.apikey_location),
            timeout_seconds=descriptor.timeout_seconds,
            retry=descriptor.retry,
            circuit=descriptor.circuit,
            rate_limit=descriptor.rate_limit,
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
    ) -> Self:
        """Build the client from its single API key (the uniform factory contract).

        Implements the :class:`~personalscraper.api.tracker._contracts.TrackerConstructible`
        contract: the factory dispatches construction uniformly through
        ``from_env`` for every tracker. A Torznab tracker is an api-key tracker,
        so it builds an HttpTransport from ``policy(env[required[0]])`` and
        ignores ``provider_cfg`` (no extra construction options).

        Args:
            env: Resolved credential source (registry passes the env mapping).
            event_bus: Event bus propagated to the HTTP transport.
            required: Ordered credential env-var names (e.g. ``[C411_API_KEY]``).
            provider_cfg: Per-tracker config — unused for api-key trackers.

        Returns:
            A network-ready client wrapping the authed transport.
        """
        del provider_cfg  # api-key tracker: no extra construction options
        api_key = env.get(required[0], "") if required else ""
        transport = HttpTransport(cls.policy(api_key), event_bus=event_bus)
        return cls(transport)

    def __init__(self, transport: HttpTransport, descriptor: TorznabDescriptor | None = None) -> None:
        """Initialize the client.

        Args:
            transport: HttpTransport pre-configured with this tracker's policy.
            descriptor: Dialect descriptor. Defaults to the class ``DESCRIPTOR``,
                which every named tracker sets; passing one explicitly is how the
                generic is exercised without a named subclass.
        """
        if descriptor is None:
            descriptor = type(self).DESCRIPTOR
        self._descriptor = descriptor
        self._transport = transport
        self.provider_name = descriptor.provider_name

    @property
    def _open_transport(self) -> HttpTransport:
        """The HTTP transport (always materialized for an api-key client).

        Uniform peek for the registry seams: api-key trackers build their
        transport at construction, so this simply returns ``self._transport``
        with no laziness.
        """
        return self._transport

    # -- TrackerClient Protocol ---------------------------------------------

    def search(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[TrackerResult]:
        """Search the indexer via the Torznab API.

        Routes to the specialized movie / TV endpoints when ``media_type`` is
        ``"movie"`` / ``"tv"``, falling back to the descriptor's default
        endpoint otherwise. A ``cat=`` filter is sent only when the descriptor
        declares one for that media type (C411's caps advertises no ``cat``
        support, so nothing is sent).

        Args:
            query: Free-text search query.
            media_type: ``"movie"``, ``"tv"``, or any other value (→ default endpoint).
            year: Optional release year — appended to ``q`` when given.

        Returns:
            List of TrackerResult ordered as the indexer returned them.
        """
        descriptor = self._descriptor
        endpoint = {
            "movie": descriptor.movie_endpoint,
            "tv": descriptor.tv_endpoint,
        }.get(media_type, descriptor.default_endpoint)

        q = f"{query} {year}" if year is not None else query
        params: dict[str, Any] = {"t": endpoint, "q": q}
        category = descriptor.search_categories.get(str(media_type))
        if category:
            params["cat"] = category

        raw = self._request(params)
        return wrap_parser_drift(
            self.provider_name,
            lambda: self._parse_rss(cast("dict[str, Any]", raw)),
        )

    def get_categories(self) -> dict[str, str]:
        """Fetch the caps document and flatten the categories tree.

        Newznab subcat IDs collide across parents (e.g. multiple `4050`),
        so we key the dict by the unique ``description`` (per parent label,
        which is the actual native subcategory name) → ``id`` of the
        Newznab class. The shape keeps the tracker family's historical
        ``slug → human`` contract modulo "id is a numeric Newznab class,
        not a slug".

        Returns:
            Mapping ``description → newznab_id`` (e.g. ``"Animation": "2060"``).
            Top-level categories included as ``@description → @id``.
        """
        raw = self._request({"t": self._descriptor.caps_endpoint})
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

    def _request(self, params: dict[str, Any]) -> Any:  # noqa: ANN401 — transport's own return type
        """Call the indexer, classifying an HTTP auth failure as such (D4).

        The transport reports every non-2xx as a flat :exc:`ApiError`, which
        cannot distinguish a broken passkey from a bad afternoon. 401/403 is the
        one case where it can: those mean the CREDENTIAL is wrong, and no amount
        of retrying fixes it. Re-raising them as :exc:`TrackerAuthError` is what
        gives the registry the ``auth`` taxon and, when every tracker agrees, the
        terminal ``tracker_auth`` verdict instead of a perpetual retry.

        Shared by :meth:`search` and :meth:`get_categories` so the classification
        cannot depend on which endpoint happened to notice. Every other status
        propagates verbatim.

        Args:
            params: Query parameters for the indexer's single API path.

        Returns:
            The decoded response body, as the transport returned it.

        Raises:
            TrackerAuthError: The indexer answered 401 or 403.
            ApiError: Any other transport failure, unchanged.
        """
        try:
            return self._transport.get(path=self._descriptor.api_path, params=params)
        except ApiError as exc:
            if exc.http_status in AUTH_HTTP_STATUSES:
                raise TrackerAuthError(
                    provider=self.provider_name,
                    http_status=exc.http_status,
                    message=exc.message,
                ) from exc
            raise

    def _parse_rss(self, data: dict[str, Any]) -> list[TrackerResult]:
        """Parse the xmltodict-decoded Torznab RSS response."""
        # Auth/syntax errors arrive as <error code='100' description='...' />
        # at the document root (HTTP status already non-200 in this case).
        #
        # The CODE decides the type (D4). Torznab reserves 100-102 for
        # credential failures ("Incorrect user credentials" / "Account
        # suspended" / "Insufficient privileges"), and those are permanent until
        # an operator acts — the registry books them as the ``auth`` taxon so a
        # unanimously-broken key can reach a terminal verdict instead of being
        # retried forever. Everything else (the 200-range request errors, an
        # unrecognised code) stays a generic operational ApiError.
        if "error" in data:
            err = data["error"]
            code = int(err.get("@code", 0) or 0)
            message = str(err.get("@description", f"{self._descriptor.display_name} error"))
            error_cls = TrackerAuthError if code in _AUTH_ERROR_CODES else ApiError
            raise error_cls(
                provider=self.provider_name,
                http_status=code,
                message=message,
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

        info_hash = attrs.get("infohash")
        if not info_hash and self._descriptor.guid_is_infohash:
            info_hash = _text_of(item.get("guid"))
        download_url = _enclosure_url(item)
        source_url = item.get("comments") or item.get("link")

        title_parsed = parse_title_quality(title)

        return TrackerResult(
            provider=self.provider_name,
            tracker_id=_text_of(item.get("guid")),
            title=title,
            size=size,
            seeders=seeders,
            leechers=leechers,
            category=self._item_category(item, attrs),
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
            language=title_parsed.get("language"),
            # Torznab indexers publish the TMDB id as a ``tmdbid`` attr. It feeds
            # the TMDB identity hard-filter (the anti-remake guard: a 1984 result
            # can never be grabbed for a 2021 wanted item). Absent or non-numeric
            # → None, which makes the filter a no-op rather than a wrong drop.
            tmdb_id=_parse_optional_int(attrs.get("tmdbid")),
        )

    def _item_category(self, item: dict[str, Any], attrs: dict[str, str]) -> str | None:
        """Return the item category, from the source the descriptor declares.

        Exclusive by design (see ``TorznabDescriptor.item_category_element``):
        an indexer either publishes ``<category>`` elements or only the
        ``torznab:attr`` — reading both would hide a wrong descriptor.
        """
        if not self._descriptor.item_category_element:
            return attrs.get("category")
        for value in _as_list(item.get("category")):
            if isinstance(value, str):
                return value
        return None


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


__all__ = ["TorznabClient", "TorznabDescriptor"]
