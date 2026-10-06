"""Tests for the sandbox mount-point guard: a sandbox writes only inside its own marked, mounted roots.

``tmp_path`` is never a mount point, so ``is_mounted`` is patched. The Config is built
before the environment is switched to ``staging`` (a staging Config needs an isolated
data directory, which is not what these tests are about).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf import sandbox_guard
from personalscraper.conf.environment import Environment
from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig, TorrentScope
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.sandbox_guard import (
    SandboxGuardError,
    assert_sandbox_root,
    assert_within_sandbox,
    sandbox_roots,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS

PREPROD_ROOT_MARKER = sandbox_guard.root_marker(Environment.STAGING)


def _root(tmp_path: Path, name: str, *, marked: bool = True) -> Path:
    """Create a root folder, with or without the preprod (staging) marker."""
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
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)


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
    assert_within_sandbox(config, disk / "movies" / "Film (2024)")
    assert_within_sandbox(config, stage / "x")
    with pytest.raises(SandboxGuardError):
        assert_within_sandbox(config, tmp_path / "elsewhere" / "Film (2024)")


def test_unmarked_root_is_refused(tmp_path: Path, mounted: None, staging: Callable[[], None]) -> None:
    """A root without its marker refuses everything under it."""
    disk = _root(tmp_path, "disk", marked=False)
    config = _config(tmp_path, disk, _root(tmp_path, "stage"))
    staging()
    with pytest.raises(SandboxGuardError, match=PREPROD_ROOT_MARKER):
        assert_within_sandbox(config, disk / "Film")
    with pytest.raises(SandboxGuardError):
        assert_sandbox_root(disk, Environment.STAGING)


def test_marker_that_is_a_symlink_is_refused(tmp_path: Path, mounted: None) -> None:
    """A symlink named like the marker, even onto a real file, does not make a root preprod's."""
    disk = _root(tmp_path, "disk", marked=False)
    real_file = tmp_path / "elsewhere.txt"
    real_file.write_text("", encoding="utf-8")
    (disk / PREPROD_ROOT_MARKER).symlink_to(real_file)
    with pytest.raises(SandboxGuardError, match=PREPROD_ROOT_MARKER):
        assert_sandbox_root(disk, Environment.STAGING)


def test_unmounted_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, staging: Callable[[], None]
) -> None:
    """A marked root on a volume that is not mounted is refused."""
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: False)
    disk = _root(tmp_path, "disk")
    config = _config(tmp_path, disk, _root(tmp_path, "stage"))
    staging()
    with pytest.raises(SandboxGuardError, match="mounted"):
        assert_within_sandbox(config, disk / "Film")


def test_symlink_out_of_the_root_is_refused(tmp_path: Path, mounted: None, staging: Callable[[], None]) -> None:
    """A symlink inside a root that points outside is judged by its real path."""
    disk = _root(tmp_path, "disk")
    outside = tmp_path / "prod-media"
    outside.mkdir()
    (disk / "link").symlink_to(outside)
    config = _config(tmp_path, disk, _root(tmp_path, "stage"))
    staging()
    with pytest.raises(SandboxGuardError):
        assert_within_sandbox(config, disk / "link" / "Film")


def test_in_prod_the_guard_is_a_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """In prod any path passes, unmarked or not."""
    config = _config(tmp_path, tmp_path / "disk", tmp_path / "stage")
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "prod")
    assert_within_sandbox(config, tmp_path / "anywhere")


def test_explicit_env_overrides_the_process_environment(tmp_path: Path, mounted: None) -> None:
    """``env=`` decides, whatever the process says."""
    config = _config(tmp_path, tmp_path / "disk", tmp_path / "stage")
    with pytest.raises(SandboxGuardError):
        assert_within_sandbox(config, tmp_path / "anywhere", Environment.STAGING)
    assert_within_sandbox(config, tmp_path / "anywhere", Environment.PROD)


def test_roots_are_disks_staging_and_the_client_download_root(tmp_path: Path) -> None:
    """The roots are every disk path, the staging dir and the client scope's download root."""
    disk, stage, downloads = tmp_path / "disk", tmp_path / "stage", tmp_path / "downloads"
    config = _config(tmp_path, disk, stage, scope_root=downloads)
    assert sandbox_roots(config) == (disk, stage, downloads)


def test_roots_without_a_client_scope(tmp_path: Path) -> None:
    """With no scope set, the download root is not a root."""
    disk, stage = tmp_path / "disk", tmp_path / "stage"
    assert sandbox_roots(_config(tmp_path, disk, stage)) == (disk, stage)


def test_download_root_is_guarded_like_any_root(tmp_path: Path, mounted: None, staging: Callable[[], None]) -> None:
    """A path under the scope's download root passes once that root is marked."""
    disk, stage, downloads = _root(tmp_path, "disk"), _root(tmp_path, "stage"), _root(tmp_path, "dl")
    config = _config(tmp_path, disk, stage, scope_root=downloads)
    staging()
    assert_within_sandbox(config, downloads / "Film.mkv")


# ---------------------------------------------------------------------------
# Every sandboxed environment: dev is guarded like staging, each with its own marker
# ---------------------------------------------------------------------------

_DEV_ROOT_MARKER = ".tm-dev-root"
_PREPROD_ROOT_MARKER = ".tm-preprod-root"


@pytest.fixture
def dev(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Return the switch that puts the process in ``dev`` (called once the Config is built)."""
    return lambda: monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")


def _marked(tmp_path: Path, name: str, marker: str) -> Path:
    """Create a root folder holding *marker* only."""
    root = tmp_path / name
    root.mkdir()
    (root / marker).write_text("", encoding="utf-8")
    return root


def test_dev_refuses_a_path_under_an_unmarked_mounted_root(
    tmp_path: Path, mounted: None, dev: Callable[[], None]
) -> None:
    """Under dev a path under a mounted root with no marker is refused, naming the dev marker."""
    disk = tmp_path / "disk"
    disk.mkdir()
    config = _config(tmp_path, disk, _marked(tmp_path, "stage", _DEV_ROOT_MARKER))
    dev()
    with pytest.raises(SandboxGuardError, match=_DEV_ROOT_MARKER):
        assert_within_sandbox(config, disk / "Film (2024)")


def test_dev_refuses_a_preprod_root_and_staging_refuses_a_dev_root(
    tmp_path: Path, mounted: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each sandbox's root is its own: a preprod marker does not admit dev, nor a dev marker staging."""
    preprod_disk = _marked(tmp_path, "preprod-disk", _PREPROD_ROOT_MARKER)
    preprod = _config(tmp_path, preprod_disk, _marked(tmp_path, "preprod-stage", _PREPROD_ROOT_MARKER))
    dev_disk = _marked(tmp_path, "dev-disk", _DEV_ROOT_MARKER)
    dev_config = _config(tmp_path, dev_disk, _marked(tmp_path, "dev-stage", _DEV_ROOT_MARKER))
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
    with pytest.raises(SandboxGuardError, match=_DEV_ROOT_MARKER):
        assert_within_sandbox(preprod, preprod_disk / "Film (2024)")
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    with pytest.raises(SandboxGuardError, match=_PREPROD_ROOT_MARKER):
        assert_within_sandbox(dev_config, dev_disk / "Film (2024)")


def test_dev_passes_a_path_under_a_dev_root(tmp_path: Path, mounted: None, dev: Callable[[], None]) -> None:
    """Under dev a path under a mounted root holding ``.tm-dev-root`` passes; one outside is refused."""
    disk = _marked(tmp_path, "disk", _DEV_ROOT_MARKER)
    config = _config(tmp_path, disk, _marked(tmp_path, "stage", _DEV_ROOT_MARKER))
    dev()
    assert_within_sandbox(config, disk / "movies" / "Film (2024)")
    with pytest.raises(SandboxGuardError, match="outside every sandbox root"):
        assert_within_sandbox(config, tmp_path / "elsewhere" / "Film (2024)")


def test_root_markers_name_one_marker_per_sandbox() -> None:
    """Staging keeps preprod's marker, dev has its own, and prod has none."""
    assert sandbox_guard.ROOT_MARKERS == {Environment.STAGING: _PREPROD_ROOT_MARKER, Environment.DEV: _DEV_ROOT_MARKER}
    assert sandbox_guard.root_marker(Environment.DEV) == _DEV_ROOT_MARKER
    with pytest.raises(SandboxGuardError, match="prod"):
        sandbox_guard.root_marker(Environment.PROD)


def test_prod_unchanged_the_guard_ignores_every_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """In prod, an unmounted, unmarked root and any path pass, as before."""
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: False)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "prod")
    config = _config(tmp_path, tmp_path / "disk", tmp_path / "stage")
    assert_within_sandbox(config, tmp_path / "disk" / "Film (2024)")
    assert_within_sandbox(config, tmp_path / "anywhere")
