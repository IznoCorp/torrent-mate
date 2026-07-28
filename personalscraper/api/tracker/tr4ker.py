"""Tr4ker tracker client — a named config of the generic Torznab client.

Like ``c411.py``, this module holds no protocol logic: everything lives in
``api/tracker/torznab.py`` and Tr4ker contributes only its
:class:`~personalscraper.api.tracker.torznab.TorznabDescriptor` plus its
activation credentials.

It is the proof of DESIGN §3 D1, whose actual claim is narrower than "zero
code": a new Torznab tracker is a **thin named class** — this descriptor, a
``ProviderName`` member, a ``PROVIDER_CREDS`` entry and one line in
``_TRACKER_CLASSES`` — with **zero protocol logic**. D1 explicitly rejected a
pure-JSON5 tracker registry because activation, the provider enums and the
registry typing all want static names.

See ``docs/reference/tr4ker-api.md`` for the endpoint reference.

Tr4ker particularities (from the tracker's own Prowlarr/Torznab documentation):
- Natively Torznab; the indexer is added to Prowlarr as "Generic Torznab" with
  base URL ``https://tr4ker.net``.
- Auth is a single secret sent as the ``apikey=`` query param, read from the
  ``TR4KER_PASSKEY`` env var (the operator's tracker-naming convention: one
  passkey variable per tracker, which will also authenticate the RSS feed of
  the freeleech radar R1). Legacy ``TR4KER_USERNAME`` / ``TR4KER_PASSWORD``
  entries in the operator ``.env`` are leftovers from a decommissioned
  login-style tracker and are deliberately not wired.
  **Factual note**: the tracker's own documentation distinguishes the *profile
  API key* (Mon compte → Paramètres) from the *announce passkey* and states that
  Torznab search wants the API key. This codebase follows the operator's
  single-variable convention instead, so if a live search ever answers
  ``<error code="100" description="Invalid API Key"/>``, the fix is to put the
  profile API key into ``TR4KER_PASSKEY`` — not to add a second env var.
- API paths: ``/api/torznab`` (used here) and ``/api`` (zero-config alias, same
  Torznab document). ``/api/torznab/all`` is the full catalog including
  0-seeder torrents — reserved for a future cross-seed, deliberately NOT wired
  (DESIGN §6 Hors périmètre).
- Usage limits are qualitative ("stay reasonable on concurrent requests, a
  temporary error is returned if you push too hard"), so the transport reuses
  C411's defensive tuning: 15 s timeout, 3 attempts, 5-failure/300 s circuit and
  0.5 rps (NE-DOIT-PAS-8 — never abuse a dependency).
- Category slugs (``films``, ``series``, …) documented by the tracker belong to
  the **RSS** endpoint, not to Torznab search. No caps document has been
  captured yet, so ``search_categories`` stays empty (no ``cat=`` is sent) —
  inventing Newznab ids without a capture is exactly the kind of guess that
  silently returns nothing.
- The two dialect quirks (``item_category_element`` / ``guid_is_infohash``)
  carry the Torznab norm, which C411 also follows; both are re-verified by the
  real controlled search of the feature's acceptance criterion ACC-03.
"""

from __future__ import annotations

from typing import ClassVar

from personalscraper.api._contracts import ProviderName
from personalscraper.api.tracker.torznab import TorznabClient, TorznabDescriptor

#: Tr4ker's dialect of Torznab. ``search_categories`` is intentionally empty
#: (no capture of the caps document → no invented category ids), and the two
#: quirk flags carry the Torznab norm shared with C411: the category is read
#: from the flattened ``torznab:attr``, and ``<guid>`` may back the infohash
#: when the ``infohash`` attr is absent.
TR4KER_DESCRIPTOR = TorznabDescriptor(
    provider=ProviderName.TR4KER,
    display_name="Tr4ker",
    base_url="https://tr4ker.net",
    api_path="/api/torznab",
    item_category_element=False,
    guid_is_infohash=True,
)


class Tr4kerClient(TorznabClient):
    """Tr4ker tracker API client over Torznab XML.

    Carries no logic of its own: :class:`~personalscraper.api.tracker.torznab.TorznabClient`
    implements the protocol and :data:`TR4KER_DESCRIPTOR` supplies the dialect.
    Composes
    :class:`~personalscraper.api.tracker._contracts.TorrentSearchable`
    and
    :class:`~personalscraper.api.tracker._contracts.CategoryListable`, and
    deliberately not
    :class:`~personalscraper.api.tracker._contracts.FreeleechAware` nor
    :class:`~personalscraper.api.tracker._contracts.TorrentDetailsProvider`
    (Torznab exposes neither a freeleech re-check nor a per-torrent detail
    endpoint).

    ``REQUIRED_CREDS`` lists the single ``TR4KER_PASSKEY`` secret, whose value
    the transport sends as the ``apikey=`` query param.
    """

    DESCRIPTOR: ClassVar[TorznabDescriptor] = TR4KER_DESCRIPTOR
    # Mirrors ``DESCRIPTOR.provider`` for class-level access (``Named`` protocol);
    # instances get the same value from the descriptor at construction.
    provider_name: str = ProviderName.TR4KER.value
    REQUIRED_CREDS: ClassVar[list[str]] = ["TR4KER_PASSKEY"]
