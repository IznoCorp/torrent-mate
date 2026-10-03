"""Tests for the preprod mount-point guard: preprod writes only inside its own marked, mounted roots.

``tmp_path`` is never a mount point, so ``is_mounted`` is patched. The Config is built
before the environment is switched to ``staging`` (a staging Config needs an isolated
data directory, which is not what these tests are about).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf import preprod_guard
from personalscraper.conf.environment import Environment
from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig, TorrentScope
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.preprod_guard import (
    PREPROD_ROOT_MARKER,
    PreprodGuardError,
    assert_preprod_root,
    assert_within_preprod,
    preprod_roots,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _root(tmp_path: Path, name: str, *, marked: bool = True) -> Path:
    """Create a root folder, with or without the preprod marker."""
    root = tmp_path / name
    root.mkdir()
    if marked:
        (root / PREPROD_ROOT_MARKER).write_text("", encoding="utf-8")
    return root


def _config(tmp_path: Path, disk: Path, staging: Path, scope_root: Path | None = None) -> Config:
    """Build the minimal Config over *disk* and *staging* (built in prod, before the env switch)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    torrent = TorrentConfig()
    if scope_root is not None:
        scope = TorrentScope(category="tm-preprod", download_root=scope_root)
        torrent = TorrentConfig(active="qbittorrent", clients={"qbittorrent": TorrentClientEntry(scope=scope)})
    return Config(
        paths=PathConfig(torrent_complete_dir=tmp_path / "complete", staging_dir=staging, data_dir=data_dir),
        disks=[DiskConfig(id="disk_a", path=disk, categories=list(CID.BUILTIN_CATEGORY_IDS))],
        staging_dirs=CANONICAL_STAGING_DIRS,
        torrent=torrent,
    )


@pytest.fixture
def mounted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every path reads as mounted."""
    monkeypatch.setattr(preprod_guard, "is_mounted", lambda path: True)


@pytest.fixture
def staging(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Return the switch that puts the process in ``staging`` (called once the Config is built)."""
    return lambda: monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")


def test_path_under_a_marked_mounted_root_passes(tmp_path: Path, mounted: None, staging: Callable[[], None]) -> None:
    """A path under a marked, mounted root passes; one outside every root is refused."""
    disk = _root(tmp_path, "disk")
    stage = _root(tmp_path, "stage")
    config = _config(tmp_path, disk, stage)
    staging()
    assert_within_preprod(config, disk / "movies" / "Film (2024)")
    assert_within_preprod(config, stage / "x")
    with pytest.raises(PreprodGuardError):
        assert_within_preprod(config, tmp_path / "elsewhere" / "Film (2024)")


def test_unmarked_root_is_refused(tmp_path: Path, mounted: None, staging: Callable[[], None]) -> None:
    """A root without its marker refuses everything under it."""
    disk = _root(tmp_path, "disk", marked=False)
    config = _config(tmp_path, disk, _root(tmp_path, "stage"))
    staging()
    with pytest.raises(PreprodGuardError, match=PREPROD_ROOT_MARKER):
        assert_within_preprod(config, disk / "Film")
    with pytest.raises(PreprodGuardError):
        assert_preprod_root(disk)


def test_unmounted_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, staging: Callable[[], None]
) -> None:
    """A marked root on a volume that is not mounted is refused."""
    monkeypatch.setattr(preprod_guard, "is_mounted", lambda path: False)
    disk = _root(tmp_path, "disk")
    config = _config(tmp_path, disk, _root(tmp_path, "stage"))
    staging()
    with pytest.raises(PreprodGuardError, match="mounted"):
        assert_within_preprod(config, disk / "Film")


def test_symlink_out_of_the_root_is_refused(tmp_path: Path, mounted: None, staging: Callable[[], None]) -> None:
    """A symlink inside a root that points outside is judged by its real path."""
    disk = _root(tmp_path, "disk")
    outside = tmp_path / "prod-media"
    outside.mkdir()
    (disk / "link").symlink_to(outside)
    config = _config(tmp_path, disk, _root(tmp_path, "stage"))
    staging()
    with pytest.raises(PreprodGuardError):
        assert_within_preprod(config, disk / "link" / "Film")


@pytest.mark.parametrize("env", [None, "dev", "prod"])
def test_outside_staging_the_guard_is_a_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env: str | None) -> None:
    """Unset (prod) or dev: any path passes, unmarked or not."""
    config = _config(tmp_path, tmp_path / "disk", tmp_path / "stage")
    if env is None:
        monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)
    else:
        monkeypatch.setenv("PERSONALSCRAPER_ENV", env)
    assert_within_preprod(config, tmp_path / "anywhere")


def test_explicit_env_overrides_the_process_environment(tmp_path: Path, mounted: None) -> None:
    """``env=`` decides, whatever the process says."""
    config = _config(tmp_path, tmp_path / "disk", tmp_path / "stage")
    with pytest.raises(PreprodGuardError):
        assert_within_preprod(config, tmp_path / "anywhere", Environment.STAGING)
    assert_within_preprod(config, tmp_path / "anywhere", Environment.PROD)


def test_roots_are_disks_staging_and_the_client_download_root(tmp_path: Path) -> None:
    """The roots are every disk path, the staging dir and the client scope's download root."""
    disk, stage, downloads = tmp_path / "disk", tmp_path / "stage", tmp_path / "downloads"
    config = _config(tmp_path, disk, stage, scope_root=downloads)
    assert preprod_roots(config) == (disk, stage, downloads)


def test_roots_without_a_client_scope(tmp_path: Path) -> None:
    """With no scope set, the download root is not a root."""
    disk, stage = tmp_path / "disk", tmp_path / "stage"
    assert preprod_roots(_config(tmp_path, disk, stage)) == (disk, stage)


def test_download_root_is_guarded_like_any_root(tmp_path: Path, mounted: None, staging: Callable[[], None]) -> None:
    """A path under the scope's download root passes once that root is marked."""
    disk, stage, downloads = _root(tmp_path, "disk"), _root(tmp_path, "stage"), _root(tmp_path, "dl")
    config = _config(tmp_path, disk, stage, scope_root=downloads)
    staging()
    assert_within_preprod(config, downloads / "Film.mkv")
