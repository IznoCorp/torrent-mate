"""Integration tests for dispatch merge behaviour.

Catalogue #13 — TV show merge invariant.

Tests that run_dispatch merges new episodes into an existing TV show folder
on disk: existing episodes are preserved, new episodes are added, the staging
folder is removed, and no _tmp_dispatch_* or .merge_backup residue remains.
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

# Small but non-zero bytes for episode files in this test.
# The TV show checker warns about sample-sized files (< 100 MB) but does NOT
# block dispatch on a warning — only ERRORs block.  Episode files are checked
# via video_present (recursive), and small bytes are fine here.
_SMALL_BYTES = b"\x00" * 1024

# Minimum video size to avoid the "sample" WARNING from the checker.
# Not strictly required (WARNINGs don't block), but used to keep the
# verified TV show free of noise in the report details.
_MIN_VIDEO_BYTES = 100 * 1024 * 1024 + 1


def _make_settings() -> Settings:
    """Return Settings with disk-space guards disabled for integration tests.

    Returns:
        Settings instance with zero thresholds so the tests are not gated
        by real filesystem free-space requirements.
    """
    return Settings()


def _build_verified_tvshow_dir(
    parent: Path,
    title: str,
    year: int,
    episodes: list[str],
) -> Path:
    """Create a minimal verified TV show folder that passes the verify gate.

    Creates the show directory with:
    - ``tvshow.nfo`` (title + TVDB uniqueid + Drama genre)
    - ``poster.jpg`` and ``landscape.jpg`` at the show root
    - ``Saison 01/`` containing the provided episode files, each large enough
      to avoid the sample warning, plus one NFO per episode

    Args:
        parent: Directory under which the show folder is created.
        title: Show title used for the folder name.
        year: Release year used in the folder name.
        episodes: List of episode file basenames (e.g. ``["S01E01 - Pilot.mkv"]``).

    Returns:
        Path to the created show directory.
    """
    show_dir = parent / f"{title} ({year})"
    show_dir.mkdir(parents=True, exist_ok=True)

    # tvshow.nfo — requires <title> and a TVDB or TMDB uniqueid.
    # "Drama" genre does not match any special rule → default_tv_category = tv_shows.
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    uid = ET.SubElement(root, "uniqueid")
    uid.set("type", "tvdb")
    uid.text = "327417"
    ET.SubElement(root, "genre").text = "Drama"
    ET.ElementTree(root).write(show_dir / "tvshow.nfo", encoding="unicode")

    # Artwork — poster and landscape are mandatory checks in checker.py.
    (show_dir / "poster.jpg").write_bytes(b"\xff\xd8\xff")
    (show_dir / "landscape.jpg").write_bytes(b"\xff\xd8\xff")

    # Season directory with the requested episodes.
    season_dir = show_dir / "Saison 01"
    season_dir.mkdir(parents=True, exist_ok=True)
    for ep_name in episodes:
        # Write a large-enough video file so the not_sample check passes.
        (season_dir / ep_name).write_bytes(b"\x00" * _MIN_VIDEO_BYTES)
        # Companion NFO so episode_nfo check passes.
        nfo_name = Path(ep_name).with_suffix(".nfo").name
        ep_nfo = ET.Element("episodedetails")
        ET.SubElement(ep_nfo, "title").text = ep_name.split(" - ", 1)[-1].rsplit(".", 1)[0]
        # Phase 9 verify hardening requires canonical uniqueid on each
        # episode NFO (tvdb here, matching tvshow.nfo).
        ep_uid = ET.SubElement(ep_nfo, "uniqueid")
        ep_uid.set("type", "tvdb")
        ep_uid.set("default", "true")
        ep_uid.text = "9001"
        ET.ElementTree(ep_nfo).write(season_dir / nfo_name, encoding="unicode")

    return show_dir


def test_dispatch_merges_tvshow_new_episodes(
    staging_tree: Path,
    fake_disks: list[Path],
    integration_config: Config,
    rsync_available: None,
) -> None:
    """Dispatch merges new episodes into an existing TV show folder on disk.

    Catalogue #13 — merge invariant.

    Pre-creates ``episode1.mkv`` in the Fallout (2024) folder on Disk2
    (which accepts TV shows in integration_config).  Places a staging
    directory containing only ``episode2.mkv`` and runs dispatch.

    Post-conditions:
    - Both ``episode1.mkv`` (pre-existing) and ``episode2.mkv`` (new)
      exist on Disk2 under the show folder.
    - The staging folder is gone.
    - No ``_tmp_dispatch_*`` residue remains anywhere on Disk2.
    - No ``.merge_backup`` residue remains anywhere on Disk2.
    - The DB-backed MediaIndex contains an entry for ``Fallout (2024)``.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        fake_disks: List of four fake disk root paths.
        integration_config: Fully composed integration Config fixture.
        rsync_available: Skips test when rsync is absent from PATH.
    """
    config = integration_config
    title = "Fallout"
    year = 2024
    folder = f"{title} ({year})"

    # integration_config assigns ANIME + TV_SHOWS_ANIMATION to disk2 (fake_disks[1]).
    # TV_SHOWS is on disk1 (fake_disks[0]) — use disk1.
    disk1_root = fake_disks[0]
    tv_shows_folder_name = config.category(CID.TV_SHOWS).folder_name

    # Pre-create the existing show folder with episode1 on Disk1.
    existing_show_dir = disk1_root / tv_shows_folder_name / folder
    (existing_show_dir / "Saison 01").mkdir(parents=True, exist_ok=True)
    existing_ep = existing_show_dir / "Saison 01" / "episode1.mkv"
    existing_ep.write_bytes(_SMALL_BYTES)

    # Ensure data_dir exists — MediaIndex requires the parent directory.
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    # Pre-seed the DB-backed media index so dispatch knows the show is already on disk1.
    # Without this the dispatcher treats the show as "new" and picks the disk
    # with most free space instead of merging into the existing folder.
    index_path = config.paths.data_dir / "library.db"
    seed_index = MediaIndex(index_path, event_bus=EventBus())
    seed_index.add(
        IndexEntry(
            name=folder,
            disk="disk1",
            category=CID.TV_SHOWS,
            path=str(existing_show_dir),
            media_type="tvshow",
        )
    )

    # Build a fully-verified staging TV show folder containing only episode2.
    tvshows_staging = staging_tree / folder_name(find_by_file_type(config, FileType.TVSHOW))
    _build_verified_tvshow_dir(
        tvshows_staging,
        title=title,
        year=year,
        episodes=["S01E02 - The Target.mkv"],
    )

    report = run_dispatch(_make_settings(), config, dry_run=False, verified=None, event_bus=EventBus())

    # Dispatch must report at least one success (the merge action).
    assert report.error_count == 0, f"Expected no dispatch errors. Got: {report.details}"
    assert report.success_count >= 1, f"Expected at least 1 success. Got: {report.details}"

    dest_dir = disk1_root / tv_shows_folder_name / folder

    # episode1.mkv must still exist (preserved by merge).
    assert existing_ep.exists(), f"episode1.mkv should be preserved after merge. Missing: {existing_ep}"

    # episode2.mkv (the new episode) must now be present.
    new_ep = dest_dir / "Saison 01" / "S01E02 - The Target.mkv"
    assert new_ep.exists(), (
        f"New episode should be present on Disk1 after merge. Expected: {new_ep}. Dispatch details: {report.details}"
    )

    # Staging folder must be gone after a successful dispatch.
    source = tvshows_staging / folder
    assert not source.exists(), f"Staging folder should be removed after dispatch. Still at: {source}"

    # No _tmp_dispatch_* residue must remain on Disk1.
    tmp_residue = list(disk1_root.rglob("_tmp_dispatch_*"))
    assert not tmp_residue, f"Unexpected _tmp_dispatch_* residue on Disk1: {tmp_residue}"

    # No .merge_backup residue must remain on Disk1.
    backup_residue = list(disk1_root.rglob(".merge_backup"))
    assert not backup_residue, f"Unexpected .merge_backup residue on Disk1: {backup_residue}"

    # The DB-backed index must have an entry for the show after dispatch.
    post_index = MediaIndex(index_path, event_bus=EventBus())
    entry = post_index.find(folder, "tvshow")
    assert entry is not None, (
        f"MediaIndex should have an entry for '{folder}' after dispatch. Total entries in index: {post_index.count}"
    )
    assert entry.disk == "disk1", f"Index entry for '{folder}' should point to disk1. Got: {entry.disk!r}"
    assert entry.path == str(dest_dir), f"Index entry path for '{folder}' should be '{dest_dir}'. Got: {entry.path!r}"
