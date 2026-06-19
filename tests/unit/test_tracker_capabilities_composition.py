"""Tracker client capability composition tests (phase 11).

The historical monolithic ``TrackerClient`` Protocol was retired in
sub-phase 11.1 ; each concrete client now satisfies only the atomic
capabilities it actually implements (DESIGN §4). These tests pin the
``isinstance`` contract for ``LaCaleClient``, ``C411Client``, and
``Torr9Client``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api.tracker._contracts import (
    CategoryListable,
    FreeleechAware,
    TorrentSearchable,
)
from personalscraper.api.tracker.c411 import C411Client
from personalscraper.api.tracker.lacale import LaCaleClient
from personalscraper.api.tracker.torr9 import Torr9Client


def _lacale() -> LaCaleClient:
    transport = MagicMock()
    return LaCaleClient(transport=transport)


def _c411() -> C411Client:
    transport = MagicMock()
    return C411Client(transport=transport)


def _torr9() -> Torr9Client:
    return Torr9Client(username="u", password="p", event_bus=MagicMock())


def test_lacale_client_is_torrent_searchable_isinstance() -> None:
    """``LaCaleClient`` satisfies the ``TorrentSearchable`` capability."""
    assert isinstance(_lacale(), TorrentSearchable)


def test_lacale_client_is_category_listable_isinstance() -> None:
    """``LaCaleClient`` satisfies the ``CategoryListable`` capability."""
    assert isinstance(_lacale(), CategoryListable)


def test_c411_client_is_torrent_searchable_isinstance() -> None:
    """``C411Client`` satisfies the ``TorrentSearchable`` capability."""
    assert isinstance(_c411(), TorrentSearchable)


def test_c411_client_is_category_listable_isinstance() -> None:
    """``C411Client`` satisfies the ``CategoryListable`` capability."""
    assert isinstance(_c411(), CategoryListable)


def test_c411_client_not_freeleech_aware_isinstance() -> None:
    """``C411Client`` deliberately does not implement ``FreeleechAware``.

    The Torznab schema C411 exposes carries no freeleech flag, so the
    client refuses to advertise the capability — DESIGN §4 expects an
    accurate composition rather than a stub returning a constant.
    """
    assert not isinstance(_c411(), FreeleechAware)


def test_torr9_client_is_torrent_searchable_isinstance() -> None:
    """``Torr9Client`` satisfies the ``TorrentSearchable`` capability."""
    assert isinstance(_torr9(), TorrentSearchable)


def test_torr9_client_is_category_listable_isinstance() -> None:
    """``Torr9Client`` satisfies the ``CategoryListable`` capability."""
    assert isinstance(_torr9(), CategoryListable)


def test_torr9_client_is_freeleech_aware_isinstance() -> None:
    """``Torr9Client`` satisfies ``FreeleechAware``.

    torr9 exposes a real per-torrent detail endpoint (``GET /torrents/{id}``)
    so ``is_freeleech`` is a genuine pre-download re-check (DESIGN §Approach §1;
    user decision 2026-06-19).
    """
    assert isinstance(_torr9(), FreeleechAware)
    assert hasattr(_torr9(), "is_freeleech")


def test_monolithic_tracker_client_protocol_dropped() -> None:
    """The legacy ``TrackerClient`` Protocol no longer exists.

    Importing it from ``personalscraper.api.tracker._base`` must fail
    so old call sites trip the loader rather than silently mis-typing
    the registry.
    """
    import personalscraper.api.tracker._base as base_mod

    assert not hasattr(base_mod, "TrackerClient"), (
        "TrackerClient(Protocol) was supposed to be dropped in sub-phase 11.1"
    )
