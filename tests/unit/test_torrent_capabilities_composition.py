"""Torrent client capability composition tests (phase 13).

The monolithic ``TorrentClient`` Protocol was retired in sub-phase
13.1 ; ``QBitClient`` now satisfies all 5 atomic capabilities while
``TransmissionClient`` deliberately omits :class:`AuthenticatedClient`.
"""

from __future__ import annotations

from personalscraper.api.torrent._contracts import (
    AuthenticatedClient,
    TorrentController,
    TorrentInspector,
    TorrentLister,
    TorrentStateInspector,
)
from personalscraper.api.torrent.qbittorrent import QBitClient
from personalscraper.api.torrent.transmission import TransmissionClient


def _qbit() -> QBitClient:
    return QBitClient(host="http://localhost", port=8080, username="u", password="p")


def _transmission() -> TransmissionClient:
    """Build a TransmissionClient — pre-check is skipped, library client is mocked."""
    from unittest.mock import patch

    with patch("transmission_rpc.Client"):
        return TransmissionClient(host="localhost", port=9091, username="u", password="p")


def test_qbit_client_is_torrent_lister() -> None:
    """``QBitClient`` satisfies :class:`TorrentLister`."""
    assert isinstance(_qbit(), TorrentLister)


def test_qbit_client_is_torrent_inspector() -> None:
    """``QBitClient`` satisfies :class:`TorrentInspector`."""
    assert isinstance(_qbit(), TorrentInspector)


def test_qbit_client_is_authenticated_client() -> None:
    """QBittorrent requires an explicit login → satisfies AuthenticatedClient."""
    assert isinstance(_qbit(), AuthenticatedClient)


def test_qbit_client_is_torrent_state_inspector() -> None:
    """``QBitClient`` satisfies :class:`TorrentStateInspector`."""
    assert isinstance(_qbit(), TorrentStateInspector)


def test_qbit_client_is_torrent_controller() -> None:
    """``QBitClient`` satisfies :class:`TorrentController`."""
    assert isinstance(_qbit(), TorrentController)


def test_monolithic_torrent_client_protocol_dropped() -> None:
    """The legacy ``TorrentClient`` Protocol no longer exists in ``_base.py``."""
    import personalscraper.api.torrent._base as base_mod

    assert not hasattr(base_mod, "TorrentClient"), (
        "TorrentClient(Protocol) was supposed to be dropped in sub-phase 13.1"
    )


# ---------------------------------------------------------------------------
# TransmissionClient — composes 4 capabilities and deliberately omits
# AuthenticatedClient (transmission-rpc uses per-request HTTP Basic Auth).
# ---------------------------------------------------------------------------


def test_transmission_client_is_torrent_lister() -> None:
    """``TransmissionClient`` satisfies :class:`TorrentLister`."""
    assert isinstance(_transmission(), TorrentLister)


def test_transmission_client_is_torrent_inspector() -> None:
    """``TransmissionClient`` satisfies :class:`TorrentInspector`."""
    assert isinstance(_transmission(), TorrentInspector)


def test_transmission_client_is_torrent_state_inspector() -> None:
    """``TransmissionClient`` satisfies :class:`TorrentStateInspector`."""
    assert isinstance(_transmission(), TorrentStateInspector)


def test_transmission_client_is_torrent_controller() -> None:
    """``TransmissionClient`` satisfies :class:`TorrentController`."""
    assert isinstance(_transmission(), TorrentController)


def test_transmission_client_not_authenticated_client() -> None:
    """Transmission deliberately omits :class:`AuthenticatedClient` (no explicit login)."""
    assert not isinstance(_transmission(), AuthenticatedClient)
