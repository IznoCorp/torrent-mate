"""Integration tests for dispatch crash-recovery behaviour.

Catalogue #14 — crash-recovery invariant.

Tests that run_dispatch detects an existing media folder via filesystem scan
when the DB index is empty (simulating a post-crash state where the
index was not persisted), and performs the correct action (replace for movies)
rather than treating the item as new.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

from personalscraper.conf import ids as CID
from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.dispatch.run import run_dispatch
from personalscraper.sorter.file_type import FileType

# Minimum video size (bytes) to pass the verify "sample" size check (100 MB).
_MIN_VIDEO_BYTES = 100 * 1024 * 1024 + 1


def _make_settings() -> Settings:
    """Return Settings with disk-space guards disabled for integration tests.

    Returns:
        Settings instance with zero thresholds so the tests are not gated
        by real filesystem free-space requirements.
    """
    return Settings()


def _build_verified_movie_dir(parent: Path, title: str, year: int) -> Path:
    """Create a minimal verified movie folder that passes the verify gate.

    Creates the directory with a large-enough video file, an NFO with all
    required fields (title, year, tmdb+imdb uniqueids, genre, streamdetails),
    a poster, and a landscape artwork file.

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

    # NFO with mandatory fields checked by the verifier.
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    uid_tmdb = ET.SubElement(root, "uniqueid")
    uid_tmdb.set("type", "tmdb")
    uid_tmdb.text = "99999"
    uid_imdb = ET.SubElement(root, "uniqueid")
    uid_imdb.set("type", "imdb")
    uid_imdb.text = "tt7777777"
    ET.SubElement(root, "genre").text = "Action"
    fi = ET.SubElement(root, "fileinfo")
    sd = ET.SubElement(fi, "streamdetails")
    ET.SubElement(sd, "video")
    ET.ElementTree(root).write(movie_dir / f"{title}.nfo", encoding="unicode")

    # Artwork — poster and landscape are blocking requirements in checker.py.
    (movie_dir / f"{title}-poster.jpg").write_bytes(b"\xff\xd8\xff")
    (movie_dir / f"{title}-landscape.jpg").write_bytes(b"\xff\xd8\xff")

    return movie_dir


def test_crash_recovery_uses_filesystem_scan(
    staging_tree: Path,
    fake_disks: list[Path],
    integration_config: Config,
    rsync_available: None,
) -> None:
    """Dispatcher detects an existing folder via filesystem scan when index is empty.

    Catalogue #14 — crash-recovery invariant.

    Simulates a post-crash state where the previous run transferred the movie
    to Disk1 before the index was updated. A new version of the same movie is
    placed in staging.

    When ``run_dispatch`` is called:
    1. It loads the index and finds it empty (``count == 0``).
    2. It triggers an automatic rebuild by scanning all configured disks.
    3. The rebuild finds ``SomeMovie (2023)`` on Disk1 and populates the index.
    4. Dispatch detects the existing entry and performs a **replace** action
       (correct behaviour for movies) rather than moving to a new disk.
    5. The old file is removed; the new file is present on Disk1.
    6. The DB-backed MediaIndex contains an entry for ``SomeMovie (2023)``.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        fake_disks: List of four fake disk root paths.
        integration_config: Fully composed integration Config fixture.
        rsync_available: Skips test when rsync is absent from PATH.
    """
    config = integration_config
    title = "SomeMovie"
    year = 2023
    folder = f"{title} ({year})"

    # integration_config: disk1 (fake_disks[0]) accepts MOVIES.
    disk1_root = fake_disks[0]
    movies_folder_name = config.category(CID.MOVIES).folder_name

    # Pre-create the existing movie folder on Disk1 (simulating a previous run
    # that transferred the movie but crashed before saving the index).
    existing_movie_dir = disk1_root / movies_folder_name / folder
    existing_movie_dir.mkdir(parents=True, exist_ok=True)
    old_file = existing_movie_dir / "file.mkv"
    old_file.write_bytes(b"old_content" * 10)

    # Ensure the indexer DB parent directory exists — MediaIndex needs it.
    index_path = config.indexer.db_path
    index_path.parent.mkdir(parents=True, exist_ok=True)

    # The DB starts empty (no prior entries) to simulate a crashed prior run.
    # run_dispatch detects count == 0 and triggers a filesystem rebuild.
    # No JSON file is involved; the DB lifecycle is fully automatic.

    # Place a new version of the movie in the staging 001-MOVIES subdirectory.
    movies_staging = staging_tree / folder_name(find_by_file_type(config, FileType.MOVIE))
    new_movie_dir = _build_verified_movie_dir(movies_staging, title=title, year=year)

    # Add a distinctively-named non-video marker so we can confirm the new
    # version landed. A .txt extension keeps the movie's single root video
    # ({title}.mkv); a second root video would trip the no_duplicate_videos check.
    new_marker = new_movie_dir / "file_new.txt"
    new_marker.write_bytes(b"new_content" * 10)

    report = run_dispatch(_make_settings(), config, dry_run=False, verified=None, event_bus=EventBus())

    # Dispatch must succeed with no errors.
    assert report.error_count == 0, f"Expected no dispatch errors. Got: {report.details}"
    assert report.success_count >= 1, f"Expected at least 1 success. Got: {report.details}"

    dest_dir = disk1_root / movies_folder_name / folder

    # Old file must be gone — the dispatcher should have replaced the folder,
    # not moved a second copy elsewhere.
    assert not old_file.exists(), (
        f"Old file should have been replaced. Still at: {old_file}. Dispatch details: {report.details}"
    )

    # The new marker file must be present on Disk1 — confirms correct placement.
    assert (dest_dir / "file_new.txt").exists(), (
        f"New marker file should be on Disk1 after replace. Expected: {dest_dir / 'file_new.txt'}. "
        f"Dispatch details: {report.details}"
    )

    # The DB-backed index must have an entry for the movie after dispatch.
    post_index = MediaIndex(index_path, event_bus=EventBus())
    entry = post_index.find(folder, "movie")
    assert entry is not None, (
        f"MediaIndex should have an entry for '{folder}' after dispatch. Total entries in index: {post_index.count}"
    )
