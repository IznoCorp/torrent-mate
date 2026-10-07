"""The status panel's deferred listing keeps to the instance's scope in a shared client.

``_list_deferred_torrents`` reads the client's completed torrents: under a scope a
torrent filed in another category belongs to another instance and is never listed
as one of ours waiting for ingest.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.core.tags import SEED_ONLY, SEED_PURE
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


def _listed(tmp_path: Path, scope: object, tags: dict[str, list[str]] | None = None) -> list[str]:
    """Names listed as deferred over the shared client under *scope*, *tags* overriding a torrent's tags by hash."""
    client = shared_client()
    for item in client.get_completed.return_value:
        item.tags = (tags or {}).get(item.hash, item.tags)
    with (
        patch(f"{_SESSION}.build_active_torrent_client", return_value=client),
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


def test_scoped_listing_keeps_own_grab_carrying_seed_pure(tmp_path: Path) -> None:
    """Under a scope an own grab tagged seed-pure for v0 is still listed as waiting for ingest."""
    assert _listed(tmp_path, SCOPE, {PREPROD_HASH: ["c411", *SCOPE.grab_tags]}) == [f"Movie.{PREPROD_HASH[:4]}"]


def test_scoped_listing_leaves_out_own_seed_only_and_untagged(tmp_path: Path) -> None:
    """Under a scope an own seed-only cross-seed, or a torrent without the instance tag, is never listed."""
    assert _listed(tmp_path, SCOPE, {PREPROD_HASH: [*SCOPE.instance_tags, SEED_ONLY]}) == []
    assert _listed(tmp_path, SCOPE, {PREPROD_HASH: ["c411"]}) == []


def test_unscoped_listing_leaves_out_seed_pure(tmp_path: Path) -> None:
    """Characterisation: without a scope a seed-pure torrent is left out, an untagged one listed."""
    names = _listed(tmp_path, None, {PROD_HASH: [SEED_PURE]})
    assert sorted(names) == sorted(f"Movie.{h[:4]}" for h in (OTHER_CATEGORY_HASH, PREPROD_HASH))
