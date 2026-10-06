"""``category_refusal``: a scoped add needs its category, filed under the scope's download root."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import qbittorrentapi

from personalscraper.api.torrent._base import category_refusal, is_under_download_root
from personalscraper.api.torrent._contracts import CategoryReader
from personalscraper.api.torrent._errors import TorrentUnreachableError
from personalscraper.api.torrent.qbittorrent import QBitClient
from personalscraper.conf.models.api_config import TorrentScope

_SCOPE = TorrentScope(category="tm-dev", download_root=Path("/srv/torrents/tm-dev"))


class _CategoryClient:
    """A client answering ``get_categories`` from a fixed map, counting the calls.

    Attributes:
        calls: How many times the categories were read.
    """

    def __init__(self, categories: dict[str, str]) -> None:
        """Hold the categories the client defines.

        Args:
            categories: Category name → save path.
        """
        self._categories = categories
        self.calls = 0

    def get_categories(self) -> dict[str, str]:
        """Count the call and return the categories."""
        self.calls += 1
        return dict(self._categories)


def test_missing_category_is_refused() -> None:
    """The client defines no ``tm-dev``: an add would land in its default save path."""
    client = _CategoryClient({"prod": "/srv/torrents/complete"})

    assert category_refusal(client, _SCOPE) == "category_missing"


def test_save_path_outside_the_download_root_is_refused() -> None:
    """The category exists but files its torrents outside the scope's root."""
    client = _CategoryClient({"tm-dev": "/srv/torrents/complete"})

    assert category_refusal(client, _SCOPE) == "category_save_path"


def test_a_sibling_sharing_the_root_prefix_is_not_under_it() -> None:
    """``/srv/torrents/tm-dev-old`` starts with the root's text but is not inside it."""
    client = _CategoryClient({"tm-dev": "/srv/torrents/tm-dev-old/complete"})

    assert category_refusal(client, _SCOPE) == "category_save_path"


def test_a_category_without_save_path_is_refused() -> None:
    """An empty save path means the client's default one."""
    client = _CategoryClient({"tm-dev": ""})

    assert category_refusal(client, _SCOPE) == "category_save_path"


@pytest.mark.parametrize(
    "save_path",
    [
        "/srv/torrents/tm-dev/complete",
        "/srv/torrents/tm-dev/complete/",
        "/srv/torrents/tm-dev",
        "/srv/torrents/tm-dev/",
    ],
)
def test_save_path_under_the_download_root_is_accepted(save_path: str) -> None:
    """The root itself and anything below it, trailing slash or not."""
    client = _CategoryClient({"tm-dev": save_path})

    assert category_refusal(client, _SCOPE) is None


def test_dot_dot_cannot_climb_out_of_the_root() -> None:
    """A save path that textually starts under the root but climbs out of it is refused."""
    client = _CategoryClient({"tm-dev": "/srv/torrents/tm-dev/../complete"})

    assert category_refusal(client, _SCOPE) == "category_save_path"


def test_existence_only_check_ignores_the_category_save_path() -> None:
    """With ``check_save_path=False`` only the category's existence is checked."""
    client = _CategoryClient({"tm-dev": "/elsewhere/complete"})

    assert category_refusal(client, _SCOPE, check_save_path=False) is None
    assert category_refusal(_CategoryClient({}), _SCOPE, check_save_path=False) == "category_missing"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/srv/torrents/tm-dev", True),
        ("/srv/torrents/tm-dev/Movie/", True),
        ("/srv/torrents/tm-dev/../prod", False),
        ("/data/torrents/Movie", False),
        ("", False),
    ],
)
def test_is_under_download_root(path: str, expected: bool) -> None:
    """The scope's root test, with the normalisation of the category check."""
    assert is_under_download_root(path, _SCOPE) is expected


def test_without_a_scope_the_client_is_not_asked() -> None:
    """Unscoped: no categories call, no refusal."""
    client = _CategoryClient({})

    assert category_refusal(client, None) is None
    assert client.calls == 0


def test_a_client_without_categories_keeps_its_path() -> None:
    """A client that does not compose the capability is not asked and not refused."""
    client = MagicMock(spec=["get_all_hashes"])

    assert not isinstance(client, CategoryReader)
    assert category_refusal(client, _SCOPE) is None


def test_qbit_client_composes_the_capability() -> None:
    """QBittorrent is the client the guard exists for."""
    assert issubclass(QBitClient, CategoryReader)


def _qbit_with(raw: object) -> QBitClient:
    """A QBitClient whose underlying client answers ``torrents_categories`` with *raw*."""
    client = QBitClient.__new__(QBitClient)
    client._client = MagicMock()
    client._client.torrents_categories.return_value = raw
    return client


def test_qbit_get_categories_maps_name_to_save_path() -> None:
    """The ``torrents/categories`` entries become name → ``savePath``; a missing path is empty."""
    raw = {"tm-dev": {"name": "tm-dev", "savePath": "/srv/torrents/tm-dev/complete"}, "bare": {"name": "bare"}}

    assert _qbit_with(raw).get_categories() == {"tm-dev": "/srv/torrents/tm-dev/complete", "bare": ""}


def test_qbit_get_categories_maps_a_connection_failure() -> None:
    """An unreachable client surfaces as the family-neutral error, so the add is not sent."""
    client = _qbit_with({})
    client._client.torrents_categories.side_effect = qbittorrentapi.APIConnectionError("down")

    with pytest.raises(TorrentUnreachableError):
        client.get_categories()
