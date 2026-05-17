"""Integration tests for dispatch new-placement behaviour.

Catalogue #11 — disk-selection invariant.

Tests that run_dispatch routes a new media item to the disk with the most
free space among eligible disks.
"""

import shutil
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch.run import run_dispatch
from personalscraper.sorter.file_type import FileType

# Minimum video size (bytes) to pass the verify "sample" size check (100 MB).
_MIN_VIDEO_BYTES = 100 * 1024 * 1024 + 1

_GB = 1024**3


def _make_settings() -> Settings:
    """Return Settings with disk-space guards disabled for integration tests.

    Returns:
        Settings instance with zero thresholds so the tests are not skipped
        due to real filesystem constraints.
    """
    return Settings()


def _build_verified_movie_dir(parent: Path, title: str = "Oppenheimer", year: int = 2023) -> Path:
    """Create a minimal verified movie folder that passes the verify gate.

    Creates the directory with a large-enough video file, an NFO with all
    required fields, a poster, and a landscape artwork file.

    Args:
        parent: Directory under which the movie folder is created.
        title: Movie title used for the folder and file names.
        year: Release year used in the folder name and NFO.

    Returns:
        Path to the created movie directory.
    """
    movie_dir = parent / f"{title} ({year})"
    movie_dir.mkdir(parents=True, exist_ok=True)

    # Video file — must exceed 100 MB to avoid the "sample" warning check.
    (movie_dir / f"{title}.mkv").write_bytes(b"\x00" * _MIN_VIDEO_BYTES)

    # NFO with mandatory fields: title, year, tmdb+imdb uniqueids, genre,
    # and a streamdetails block (verifier checks for its presence).
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    uid_tmdb = ET.SubElement(root, "uniqueid")
    uid_tmdb.set("type", "tmdb")
    uid_tmdb.text = "12345"
    uid_imdb = ET.SubElement(root, "uniqueid")
    uid_imdb.set("type", "imdb")
    uid_imdb.text = "tt9999999"
    ET.SubElement(root, "genre").text = "Drama"
    fi = ET.SubElement(root, "fileinfo")
    sd = ET.SubElement(fi, "streamdetails")
    ET.SubElement(sd, "video")
    ET.ElementTree(root).write(movie_dir / f"{title}.nfo", encoding="unicode")

    # Artwork — poster and landscape are both blocking requirements in checker.py.
    (movie_dir / f"{title}-poster.jpg").write_bytes(b"\xff\xd8\xff")
    (movie_dir / f"{title}-landscape.jpg").write_bytes(b"\xff\xd8\xff")

    return movie_dir


def _build_multi_disk_config(base_config: Config, fake_disks: list[Path]) -> Config:
    """Return a Config variant where three disks all accept MOVIES.

    Redistributes the four fake disks so that disk1, disk2, and disk3 each
    have MOVIES in their category lists, making them all eligible targets.
    disk4 retains non-movie categories.  All 11 builtin category IDs remain
    covered so Config validators pass.

    Args:
        base_config: The integration_config to derive from (provides paths,
            staging_dirs, categories, and other settings).
        fake_disks: List of four fake disk root paths.

    Returns:
        Config copy with adjusted disk category assignments.
    """
    new_disks = [
        DiskConfig(
            id="disk1",
            path=fake_disks[0],
            categories=[CID.MOVIES, CID.TV_SHOWS],
        ),
        DiskConfig(
            id="disk2",
            path=fake_disks[1],
            categories=[CID.MOVIES, CID.ANIME, CID.MOVIES_ANIMATION],
        ),
        DiskConfig(
            id="disk3",
            path=fake_disks[2],
            categories=[CID.MOVIES, CID.MOVIES_DOCUMENTARY, CID.TV_SHOWS_ANIMATION],
        ),
        DiskConfig(
            id="disk4",
            path=fake_disks[3],
            categories=[CID.TV_SHOWS_DOCUMENTARY, CID.AUDIOBOOKS, CID.STANDUP, CID.THEATER, CID.TV_PROGRAMS],
        ),
    ]
    return base_config.model_copy(update={"disks": new_disks})


def test_dispatch_picks_disk_with_most_space(
    staging_tree: Path,
    fake_disks: list[Path],
    integration_config: Config,
    rsync_available: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch routes a new movie to the eligible disk with the most free space.

    Catalogue #11 — new-placement disk-selection invariant.

    Monkeypatches ``shutil.disk_usage`` so each disk reports a distinct free-
    space value: Disk1=100 GB, Disk2=500 GB, Disk3=200 GB, Disk4=50 GB.
    All three first disks accept MOVIES (custom config variant), so Disk2
    must win because it has the most free space.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        fake_disks: List of four fake disk root paths.
        integration_config: Fully composed integration Config fixture.
        rsync_available: Skips test when rsync is absent from PATH.
        monkeypatch: Pytest monkeypatch fixture.
    """
    # Build a config where disk1, disk2, and disk3 all accept MOVIES so that
    # free-space selection among multiple eligible disks is exercised.
    config = _build_multi_disk_config(integration_config, fake_disks)

    # Ensure data_dir exists for indexer state.
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    # Fake free-space values per disk path:
    # disk1 → 100 GB, disk2 → 500 GB (most), disk3 → 200 GB, disk4 → 50 GB.
    _free_by_path: dict[str, int] = {
        str(fake_disks[0]): 100 * _GB,
        str(fake_disks[1]): 500 * _GB,
        str(fake_disks[2]): 200 * _GB,
        str(fake_disks[3]): 50 * _GB,
    }
    _real_disk_usage = shutil.disk_usage

    def _fake_disk_usage(path: Any) -> Any:
        """Return synthetic free-space stats for fake disk paths.

        Falls through to the real shutil.disk_usage for any path that does
        not match one of the four fake disk roots (e.g. staging area).

        Args:
            path: Filesystem path passed to shutil.disk_usage.

        Returns:
            Object with ``.free`` attribute (and ``.total``/``.used``) for
            fake disks; real disk-usage result for all other paths.
        """
        path_str = str(path)
        for disk_path, free_bytes in _free_by_path.items():
            if path_str == disk_path or path_str.startswith(disk_path + "/"):

                class _FakeUsage:
                    total = 1000 * _GB
                    free = free_bytes
                    used = total - free

                return _FakeUsage()
        return _real_disk_usage(path)

    # Patch at the call-site in disk_scanner (the only module calling disk_usage).
    monkeypatch.setattr("personalscraper.dispatch.disk_scanner.shutil.disk_usage", _fake_disk_usage)

    # Place a verified movie folder in the 001-MOVIES staging subdirectory.
    movies_staging = staging_tree / folder_name(find_by_file_type(config, FileType.MOVIE))
    movie_title = "Oppenheimer"
    movie_year = 2023
    _build_verified_movie_dir(movies_staging, title=movie_title, year=movie_year)

    report = run_dispatch(_make_settings(), config, dry_run=False, verified=None, event_bus=EventBus())

    # No dispatch errors expected.
    assert report.error_count == 0, f"Expected no dispatch errors. Got: {report.details}"
    assert report.success_count >= 1, f"Expected at least 1 success. Got: {report.details}"

    # Disk2 (fake_disks[1]) must hold the movie — highest free space among all
    # three MOVIES-eligible disks (500 GB > 200 GB > 100 GB).
    movies_folder_name = config.category(CID.MOVIES).folder_name
    expected_dest = fake_disks[1] / movies_folder_name / f"{movie_title} ({movie_year})"
    assert expected_dest.exists(), (
        f"Movie should be on Disk2 (most free space). Expected: {expected_dest}. Dispatch details: {report.details}"
    )

    # Source folder must be gone after a successful real move.
    source = movies_staging / f"{movie_title} ({movie_year})"
    assert not source.exists(), f"Source folder should be removed after dispatch. Still at: {source}"
