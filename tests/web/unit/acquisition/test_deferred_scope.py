"""The status panel's deferred listing keeps to the instance's scope in a shared client.

``_list_deferred_torrents`` reads the client's completed torrents: under a scope a
torrent filed in another category belongs to another instance and is never listed
as one of ours waiting for ingest.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.web.acquisition.service import _list_deferred_torrents
from tests.fixtures.torrent_scope import (
    OTHER_CATEGORY,
    OTHER_CATEGORY_HASH,
    PREPROD_HASH,
    PROD_HASH,
    SCOPE,
    shared_client,
)

_SESSION = "personalscraper.app.torrent_session"


def _config(tmp_path: Path, scope: object) -> MagicMock:
    """A config under which every completed torrent is below ``min_ratio`` (so deferred)."""
    config = MagicMock()
    config.torrent.active_scope.return_value = scope
    config.ingest.min_ratio = 5.0  # the fixture torrents sit at ratio 2.0
    config.paths.data_dir = tmp_path
    return config


def _listed(tmp_path: Path, scope: object) -> list[str]:
    """Names listed as deferred over the shared client under *scope*."""
    with (
        patch(f"{_SESSION}.build_active_torrent_client", return_value=shared_client()),
        patch("personalscraper.ingest.deferral.deferral_probe_dirs", return_value=[tmp_path]),
    ):
        return [d.name for d in _list_deferred_torrents(_config(tmp_path, scope))]


def test_scoped_listing_leaves_out_another_categorys_completed_torrent(tmp_path: Path) -> None:
    """Under a scope only the scope's own completed torrent is listed (red before the scope)."""
    assert OTHER_CATEGORY  # the fixture files one torrent under another non-empty category
    assert _listed(tmp_path, SCOPE) == [f"Movie.{PREPROD_HASH[:4]}"]


def test_unscoped_listing_keeps_every_completed_torrent(tmp_path: Path) -> None:
    """Without a scope the listing is unchanged: every completed torrent."""
    assert sorted(_listed(tmp_path, None)) == sorted(
        f"Movie.{h[:4]}" for h in (PROD_HASH, OTHER_CATEGORY_HASH, PREPROD_HASH)
    )
