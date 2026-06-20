"""Atomic capability protocols for the tracker family (DESIGN §4).

Decomposes the historical monolithic ``TrackerClient`` Protocol
(``api/tracker/_base.py``) into 4 single-purpose,
``@runtime_checkable`` protocols. Each concrete tracker composes only
the capabilities it actually implements (DESIGN §4 "Composition par
client") :

- ``LaCaleClient(TorrentSearchable, CategoryListable, FreeleechAware)``
- ``C411Client(TorrentSearchable, CategoryListable)``

Two of the four capabilities derive from the existing ``TrackerClient``
methods (``search`` → :class:`TorrentSearchable`, ``get_categories`` →
:class:`CategoryListable`). The remaining two —
:class:`FreeleechAware` and :class:`TorrentDetailsProvider` — are new
contracts for tracker-side features that today live as fields on
:class:`TrackerResult` rather than as queries (``is_freeleech``) or
are not implemented at all (per-torrent detail page fetch). Trackers
that grow these capabilities will declare them explicitly without
forcing the others to follow.

The detail-provider returns the existing :class:`TrackerResult`
dataclass rather than introducing a sibling ``TorrentDetails`` type :
:class:`TrackerResult` already carries the rich fields a detail page
would surface (codec, source, resolution, audio, …), so a parallel
type would duplicate without value. If a future tracker needs to
distinguish a search result from a detail-page payload, the split can
happen at that point.

Phase 1.3 ships only the contracts. ``LaCaleClient`` and ``C411Client``
keep their current shape (extending the monolithic ``TrackerClient``
Protocol) ; phase 11 refactors them to compose the atomic capabilities
declared here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from personalscraper.api._contracts import MediaType
from personalscraper.api.tracker._base import TrackerResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from personalscraper.conf.models.api_config import TrackerProviderConfig
    from personalscraper.core.event_bus import EventBus


@runtime_checkable
class TorrentSearchable(Protocol):
    """Capability — search a tracker by free-form query + optional filters.

    Signature mirrors the legacy ``TrackerClient.search`` so any tracker
    that already implements the monolithic protocol satisfies this
    capability without code changes.
    """

    def search(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[TrackerResult]: ...


@runtime_checkable
class CategoryListable(Protocol):
    """Capability — enumerate the tracker's category catalog.

    Returns ``{category_id: category_label}`` — the keys are the
    tracker-side identifiers used in :class:`TrackerResult.category`,
    the values are display labels.
    """

    def get_categories(self) -> dict[str, str]: ...


@runtime_checkable
class FreeleechAware(Protocol):
    """Capability — query whether a torrent is currently freeleech.

    Distinct from the ``is_freeleech`` field on :class:`TrackerResult`,
    which captures the state at search time. This method allows a
    pre-download re-check, surfacing trackers that flip the flag
    asynchronously.
    """

    def is_freeleech(self, torrent_id: str) -> bool: ...


@runtime_checkable
class TorrentDetailsProvider(Protocol):
    """Capability — fetch the per-torrent detail-page payload.

    Returns a :class:`TrackerResult` representing the detail page
    rather than a sibling ``TorrentDetails`` type — the existing
    dataclass already covers the rich detail fields.
    """

    def get_details(self, torrent_id: str) -> TrackerResult: ...


@runtime_checkable
class TrackerConstructible(Protocol):
    """Capability — construct a tracker client from resolved env credentials.

    The factory dispatches construction UNIFORMLY through ``from_env`` (no
    provider-name literal, no cred-style branch). api-key trackers build an
    HttpTransport from ``policy(env[required[0]])``; login-style trackers
    (torr9) self-build their authed transport lazily and read extra options
    off ``provider_cfg``.
    """

    @classmethod
    def from_env(
        cls,
        *,
        env: "Mapping[str, str]",
        event_bus: "EventBus",
        required: list[str],
        provider_cfg: "TrackerProviderConfig",
    ) -> "TorrentSearchable": ...


__all__ = [
    "TorrentSearchable",
    "CategoryListable",
    "FreeleechAware",
    "TorrentDetailsProvider",
    "TrackerConstructible",
]
