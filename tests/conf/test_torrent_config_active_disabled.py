"""``TorrentConfig.active_client_disabled``: only a configured, switched-off active client is « disabled »."""

import pytest

from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig


@pytest.mark.parametrize(
    ("active", "clients", "expected"),
    [
        pytest.param("", {"qbittorrent": TorrentClientEntry(enabled=False)}, False, id="empty-active"),
        pytest.param("ghost", {"qbittorrent": TorrentClientEntry(enabled=False)}, False, id="unknown-active"),
        pytest.param("qbittorrent", {"qbittorrent": TorrentClientEntry(enabled=False)}, True, id="disabled-active"),
        pytest.param("qbittorrent", {"qbittorrent": TorrentClientEntry(enabled=True)}, False, id="enabled-active"),
    ],
)
def test_active_client_disabled(active: str, clients: dict[str, TorrentClientEntry], expected: bool) -> None:
    """Empty and unknown ``active`` are not « disabled »; a configured disabled one is; an enabled one is not.

    Args:
        active: The ``torrent.active`` value.
        clients: The configured clients.
        expected: What the predicate must answer.
    """
    assert TorrentConfig(active=active, clients=clients).active_client_disabled() is expected
