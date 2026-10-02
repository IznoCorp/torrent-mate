"""Tracker client capability composition tests (phase 11).

The historical monolithic ``TrackerClient`` Protocol was retired in
sub-phase 11.1 ; each concrete client now satisfies only the atomic
capabilities it actually implements (DESIGN §4). These tests pin the
``isinstance`` contract for ``C411Client`` and
``Tr4kerClient``. Since the login-style tracker was removed, NO client
implements ``FreeleechAware`` or ``TorrentDetailsProvider`` — the negative
assertions below are what keeps that honest. Likewise for
``AccountStatsReadable`` (the ratio AS THE TRACKER RECOGNISES IT,
NE-DOIT-PAS-1): a client claims it only on a documented endpoint, and none
has one today — a stub would be a locally invented figure.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest

from personalscraper.api.tracker._base import TrackerAccountStats
from personalscraper.api.tracker._contracts import (
    AccountStatsReadable,
    CategoryListable,
    FreeleechAware,
    TorrentDetailsProvider,
    TorrentSearchable,
)
from personalscraper.api.tracker.c411 import C411Client
from personalscraper.api.tracker.tr4ker import Tr4kerClient
from personalscraper.core.units import ByteSize


def _c411() -> C411Client:
    transport = MagicMock()
    return C411Client(transport=transport)


def _tr4ker() -> Tr4kerClient:
    transport = MagicMock()
    return Tr4kerClient(transport=transport)


def test_tr4ker_client_is_torrent_searchable_isinstance() -> None:
    """``Tr4kerClient`` satisfies the ``TorrentSearchable`` capability."""
    assert isinstance(_tr4ker(), TorrentSearchable)


def test_tr4ker_client_is_category_listable_isinstance() -> None:
    """``Tr4kerClient`` satisfies the ``CategoryListable`` capability."""
    assert isinstance(_tr4ker(), CategoryListable)


def test_tr4ker_client_not_freeleech_aware_isinstance() -> None:
    """``Tr4kerClient`` deliberately does not implement ``FreeleechAware``.

    Same accurate composition as C411: Torznab exposes no per-torrent
    freeleech re-check, so the capability is not advertised — the state is
    captured at search time on ``TrackerResult.is_freeleech``.
    """
    assert not isinstance(_tr4ker(), FreeleechAware)


def test_tr4ker_client_not_details_provider_isinstance() -> None:
    """``Tr4kerClient`` deliberately does not implement ``TorrentDetailsProvider``."""
    assert not isinstance(_tr4ker(), TorrentDetailsProvider)


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


@pytest.mark.parametrize("make", [_c411, _tr4ker], ids=["c411", "tr4ker"])
def test_no_existing_client_claims_account_stats(make) -> None:
    """Neither c411 nor tr4ker publishes the account's ratio: neither claims the capability."""
    assert not isinstance(make(), AccountStatsReadable)


def test_a_client_with_account_stats_satisfies_the_capability() -> None:
    """The protocol is structural: a client exposing ``account_stats()`` claims it."""

    class _Reading:
        def account_stats(self) -> TrackerAccountStats:
            return TrackerAccountStats(
                provider="x", uploaded=ByteSize(2), downloaded=ByteSize(1), ratio=2.0, bonus=None, observed_at=0.0
            )

    assert isinstance(_Reading(), AccountStatsReadable)


def test_account_stats_carry_the_trackers_figure_unchanged() -> None:
    """The ratio is the tracker's own figure — absent stays absent, nothing derives it from the volumes."""
    stats = TrackerAccountStats(
        provider="x", uploaded=ByteSize(300), downloaded=ByteSize(100), ratio=None, bonus=None, observed_at=1.0
    )
    assert stats.ratio is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        stats.ratio = 3.0  # type: ignore[misc]
