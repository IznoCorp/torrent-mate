"""C411 tracker client — the first named config of the generic Torznab client.

All the protocol logic (HTTP, XML parsing, ``torznab:attr`` flattening, error
taxonomy) lives in ``api/tracker/torznab.py``; this module only declares what
is C411-specific — its :class:`~personalscraper.api.tracker.torznab.TorznabDescriptor`
and its activation credentials.

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
"""

from __future__ import annotations

from typing import ClassVar

from personalscraper.api._contracts import ProviderName
from personalscraper.api.tracker.torznab import TorznabClient, TorznabDescriptor
from personalscraper.logger import get_logger

log = get_logger("api.tracker.c411")

#: C411's dialect of Torznab — the quirks listed in the module docstring,
#: expressed as data. ``item_category_element=False`` (the category exists only
#: as a ``torznab:attr``), ``guid_is_infohash=True`` (``<guid>`` is the raw
#: infohash), no ``search_categories`` (caps advertises no ``cat`` support).
C411_DESCRIPTOR = TorznabDescriptor(
    provider=ProviderName.C411,
    display_name="C411",
    base_url="https://c411.org",
    item_category_element=False,
    guid_is_infohash=True,
)


class C411Client(TorznabClient):
    """C411 tracker API client over Torznab XML.

    Carries no logic of its own: :class:`~personalscraper.api.tracker.torznab.TorznabClient`
    implements the protocol and :data:`C411_DESCRIPTOR` supplies the dialect.
    Composes
    :class:`~personalscraper.api.tracker._contracts.TorrentSearchable`
    and
    :class:`~personalscraper.api.tracker._contracts.CategoryListable`
    (sub-phase 11.3 — DESIGN §4), and deliberately not
    :class:`~personalscraper.api.tracker._contracts.FreeleechAware` nor
    :class:`~personalscraper.api.tracker._contracts.TorrentDetailsProvider`
    (Torznab exposes neither a freeleech re-check nor a per-torrent detail
    endpoint).
    """

    DESCRIPTOR: ClassVar[TorznabDescriptor] = C411_DESCRIPTOR
    # Mirrors ``DESCRIPTOR.provider`` for class-level access (``Named`` protocol);
    # instances get the same value from the descriptor at construction.
    provider_name: str = ProviderName.C411.value
    REQUIRED_CREDS: ClassVar[list[str]] = ["C411_API_KEY"]
