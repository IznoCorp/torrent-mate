"""Integration tests for dispatch replace behaviour.

Catalogue #12 — replace invariant.

Tests that run_dispatch replaces an existing movie folder on disk atomically:
old files are removed, new files are present, no _tmp_dispatch_* residue
remains, and the DB-backed MediaIndex entry is updated.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

from personalscraper.conf import ids as CID
from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.core.media_types import FileType
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex
from personalscraper.dispatch.run import run_dispatch

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
    uid_tmdb.text = "54321"
    uid_imdb = ET.SubElement(root, "uniqueid")
    uid_imdb.set("type", "imdb")
    uid_imdb.text = "tt8888888"
    ET.SubElement(root, "genre").text = "Comedy"
    fi = ET.SubElement(root, "fileinfo")
    sd = ET.SubElement(fi, "streamdetails")
    ET.SubElement(sd, "video")
    ET.ElementTree(root).write(movie_dir / f"{title}.nfo", encoding="unicode")

    # Artwork — poster and landscape are blocking requirements in checker.py.
    (movie_dir / f"{title}-poster.jpg").write_bytes(b"\xff\xd8\xff")
    (movie_dir / f"{title}-landscape.jpg").write_bytes(b"\xff\xd8\xff")

    return movie_dir


def test_dispatch_replaces_existing_movie(
    staging_tree: Path,
    fake_disks: list[Path],
    integration_config: Config,
    rsync_available: None,
) -> None:
    """Dispatch atomically replaces an existing movie folder on a disk.

    Catalogue #12 — replace invariant.

    Pre-creates a small "old" movie folder on Disk1 to simulate an existing
    copy already on disk.  Places a new larger version in staging and runs
    dispatch.  After dispatch:
    - The old file must be gone.
    - The new file must be present on Disk1.
    - No ``_tmp_dispatch_*`` residue must remain on Disk1.
    - The DB-backed MediaIndex must contain an updated entry for the movie.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        fake_disks: List of four fake disk root paths.
        integration_config: Fully composed integration Config fixture.
        rsync_available: Skips test when rsync is absent from PATH.
    """
    config = integration_config
    title = "Shrinking"
    year = 2023
    folder = f"{title} ({year})"

    # Resolve the category folder name for movies on disk
    # (e.g. "cat_movies" in the test fixture config).
    movies_folder_name = config.category(CID.MOVIES).folder_name

    # Disk1 accepts MOVIES in integration_config.
    disk1_root = fake_disks[0]
    existing_movie_dir = disk1_root / movies_folder_name / folder
    existing_movie_dir.mkdir(parents=True, exist_ok=True)

    # Seed an "old" small file to be replaced.
    old_file = existing_movie_dir / "old_small_file.mkv"
    old_file.write_bytes(b"x" * 5)

    # Ensure data_dir exists for indexer state.
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    # Build and seed the DB-backed media index so dispatch knows an existing copy is on disk1.
    # Without this the dispatcher would treat the movie as "new" and try to move it
    # to the disk with most free space instead of replacing the existing folder.
    index_path = config.paths.data_dir / "library.db"
    seed_index = MediaIndex(index_path, event_bus=EventBus())
    seed_index.add(
        IndexEntry(
            name=folder,
            disk="disk1",
            category=CID.MOVIES,
            path=str(existing_movie_dir),
            media_type="movie",
        )
    )

    # Place the new (larger) version in the staging 001-MOVIES subdirectory.
    movies_staging = staging_tree / folder_name(find_by_file_type(config, FileType.MOVIE))
    new_movie_dir = _build_verified_movie_dir(movies_staging, title=title, year=year)

    # A non-video marker proves the replacement folder moved (the single root
    # video is {title}.mkv; a second root video would trip the no_duplicate_videos
    # verify check, so the marker uses a .txt extension).
    (new_movie_dir / "new_big_file.txt").write_bytes(b"y" * 50)

    report, _ = run_dispatch(_make_settings(), config, dry_run=False, verified=None, event_bus=EventBus())

    # Dispatch must report at least one success (the replace action).
    assert report.error_count == 0, f"Expected no dispatch errors. Got: {report.details}"
    assert report.success_count >= 1, f"Expected at least 1 success. Got: {report.details}"

    dest_dir = disk1_root / movies_folder_name / folder

    # Old file must be gone — replaced by the new version.
    assert not old_file.exists(), f"Old file should have been removed by replace. Still at: {old_file}"

    # New marker file must be present on Disk1.
    new_file = dest_dir / "new_big_file.txt"
    assert new_file.exists(), (
        f"New file should be present on Disk1 after replace. Expected: {new_file}. Dispatch details: {report.details}"
    )

    # No _tmp_dispatch_* residue must remain anywhere on Disk1.
    tmp_residue = list(disk1_root.rglob("_tmp_dispatch_*"))
    assert not tmp_residue, f"Unexpected _tmp_dispatch_* residue on Disk1: {tmp_residue}"

    # The DB-backed index must have an updated entry for the movie after dispatch.
    post_index = MediaIndex(index_path, event_bus=EventBus())
    entry = post_index.find(folder, "movie")
    assert entry is not None, (
        f"MediaIndex should have an entry for '{folder}' after replace. Total entries in index: {post_index.count}"
    )

    # §7 / Star City — the overwrite left an append-only journal row.
    from personalscraper.indexer.destructive_journal import list_recent

    journal = list_recent(index_path)
    overwrite_rows = [r for r in journal if r["op"] == "overwrite" and str(r["path"]) == str(dest_dir)]
    assert overwrite_rows, f"REPLACE must record a destructive-op journal row; got {journal}"
    assert overwrite_rows[0]["actor"] == "dispatch"


def test_dispatch_blocks_replace_on_provider_id_mismatch(
    staging_tree: Path,
    fake_disks: list[Path],
    integration_config: Config,
    rsync_available: None,
) -> None:
    """§7: a REPLACE whose on-disk target is a DIFFERENT media (by ID) is blocked.

    Red-on-old: dispatch resolved the target by NAME and overwrote it with no
    identity check — a same-named different film would be destroyed. Here the
    existing on-disk "Ferrari (2023)" carries TMDB 111 while the staging
    "Ferrari (2023)" carries TMDB 54321 (from ``_build_verified_movie_dir``).
    The old content must SURVIVE and the item must be reported skipped.
    """
    config = integration_config
    title = "Ferrari"
    year = 2023
    folder = f"{title} ({year})"
    movies_folder_name = config.category(CID.MOVIES).folder_name

    disk1_root = fake_disks[0]
    existing_movie_dir = disk1_root / movies_folder_name / folder
    existing_movie_dir.mkdir(parents=True, exist_ok=True)

    # The existing on-disk copy is a DIFFERENT Ferrari — its NFO carries a
    # different TMDB id, and a sentinel file proves it survives.
    sentinel = existing_movie_dir / "the_other_ferrari.mkv"
    sentinel.write_bytes(b"x" * 5)
    other_root = ET.Element("movie")
    ET.SubElement(other_root, "title").text = title
    ET.SubElement(other_root, "year").text = str(year)
    other_uid = ET.SubElement(other_root, "uniqueid")
    other_uid.set("type", "tmdb")
    other_uid.text = "111"  # ≠ staging's 54321
    ET.ElementTree(other_root).write(existing_movie_dir / f"{title}.nfo", encoding="unicode")

    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    index_path = config.paths.data_dir / "library.db"
    seed_index = MediaIndex(index_path, event_bus=EventBus())
    seed_index.add(
        IndexEntry(
            name=folder,
            disk="disk1",
            category=CID.MOVIES,
            path=str(existing_movie_dir),
            media_type="movie",
        )
    )

    # Staging Ferrari (TMDB 54321 via the helper).
    movies_staging = staging_tree / folder_name(find_by_file_type(config, FileType.MOVIE))
    _build_verified_movie_dir(movies_staging, title=title, year=year)

    report, results = run_dispatch(_make_settings(), config, dry_run=False, verified=None, event_bus=EventBus())

    # The old (different) media MUST survive — no overwrite.
    assert sentinel.exists(), "The different-ID target was overwritten — §7 identity guard failed"

    # The item is reported skipped with the identity reason, not dispatched.
    skipped = [r for r in results if r.action == "skipped" and r.reason and "Remplacement bloqué" in r.reason]
    assert skipped, f"Expected a §7 identity block; got results: {[(r.action, r.reason) for r in results]}"
