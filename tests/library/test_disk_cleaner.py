"""Tests for personalscraper.library.disk_cleaner — library cleanup."""

from pathlib import Path

from personalscraper.conf.models import CategoryConfig, Config, DiskConfig, PathConfig
from personalscraper.library.disk_cleaner import clean_library
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _make_v15_config(
    disk_path: Path,
    disk_id: str,
    folder_name: str,
    category_id: str,
    tmp_path: Path,
) -> Config:
    """Create a minimal V15 Config for a single disk/category."""
    disk_cfg = DiskConfig(id=disk_id, path=disk_path, categories=[category_id])
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={category_id: CategoryConfig(folder_name=folder_name)},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


class TestCleanActors:
    """Tests for .actors/ directory removal."""

    def test_actors_removed_on_apply(self, tmp_path: Path) -> None:
        """--apply should delete .actors/ directories."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        actors = movie / ".actors"
        actors.mkdir(parents=True)
        (actors / "Actor.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="actors")

        assert not actors.exists()
        assert result.deleted_count > 0

    def test_actors_kept_on_dry_run(self, tmp_path: Path) -> None:
        """Dry-run should NOT delete .actors/ directories."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        actors = movie / ".actors"
        actors.mkdir(parents=True)
        (actors / "Actor.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=False, only="actors")

        assert actors.exists()
        assert result.deleted_count > 0  # counted but not deleted
        assert result.dry_run is True

    def test_ntfs_error_continues(self, tmp_path: Path, monkeypatch) -> None:
        """NTFS deletion failure should log error and continue."""
        import shutil

        disk = tmp_path / "medias"
        movie1 = disk / "films" / "Movie1 (2024)" / ".actors"
        movie2 = disk / "films" / "Movie2 (2024)" / ".actors"
        movie1.mkdir(parents=True)
        movie2.mkdir(parents=True)
        (movie1 / "a.jpg").write_bytes(b"\x00")
        (movie2 / "b.jpg").write_bytes(b"\x00")

        call_count = 0
        original_rmtree = shutil.rmtree

        def flaky_rmtree(path, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("NTFS permission denied")
            original_rmtree(path, *args, **kwargs)

        monkeypatch.setattr(shutil, "rmtree", flaky_rmtree)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="actors")

        # First deletion failed, second succeeded
        assert result.error_count == 1
        assert result.deleted_count == 1


class TestCleanEmpty:
    """Tests for empty directory removal."""

    def test_empty_dirs_removed(self, tmp_path: Path) -> None:
        """Empty directories should be removed on apply."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.mkv").write_bytes(b"\x00" * 1000)
        empty = movie / "Subs"
        empty.mkdir()

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        clean_library(config, apply=True, only="empty")

        assert not empty.exists()
        assert movie.exists()  # parent not deleted

    def test_release_group_empty_dirs_removed(self, tmp_path: Path) -> None:
        """Empty release-group artifact directories should be removed."""
        disk = tmp_path / "medias"
        show = disk / "series" / "Show (2024)"
        show.mkdir(parents=True)
        (show / "tvshow.nfo").write_text("<tvshow/>")
        artifact = show / "Show.S01E01.1080p.WEB-DL.H264-GROUP"
        artifact.mkdir()  # empty

        config = _make_v15_config(disk, "disk1", "series", "tv_shows", tmp_path)
        clean_library(config, apply=True, only="release")

        assert not artifact.exists()


class TestCleanJunk:
    """Tests for junk file removal."""

    def test_ds_store_removed(self, tmp_path: Path) -> None:
        """.DS_Store should be removed on apply."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.mkv").write_bytes(b"\x00" * 1000)
        ds = movie / ".DS_Store"
        ds.write_bytes(b"\x00")

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="junk")

        assert not ds.exists()
        assert result.deleted_count == 1

    def test_thumbs_db_and_desktop_ini(self, tmp_path: Path) -> None:
        """Thumbs.db and desktop.ini should be removed."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.mkv").write_bytes(b"\x00")
        (movie / "Thumbs.db").write_bytes(b"\x00")
        (movie / "desktop.ini").write_text("[ViewState]")

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="junk")

        assert not (movie / "Thumbs.db").exists()
        assert not (movie / "desktop.ini").exists()
        assert result.deleted_count == 2


class TestCleanAll:
    """Tests for full cleanup (no --only filter)."""

    def test_all_targets_cleaned(self, tmp_path: Path) -> None:
        """Without --only, all cleanup targets should be processed."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / ".actors").mkdir()
        (movie / ".actors" / "a.jpg").write_bytes(b"\x00")
        (movie / ".DS_Store").write_bytes(b"\x00")
        (movie / "empty_dir").mkdir()

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only=None)

        assert not (movie / ".actors").exists()
        assert not (movie / ".DS_Store").exists()
        assert not (movie / "empty_dir").exists()
        assert result.deleted_count == 3

    def test_disk_filter(self, tmp_path: Path) -> None:
        """Disk filter should limit cleanup to one disk."""
        disk1 = tmp_path / "d1" / "medias"
        disk2 = tmp_path / "d2" / "medias"
        m1 = disk1 / "films" / "M1 (2024)"
        m2 = disk2 / "films" / "M2 (2024)"
        m1.mkdir(parents=True)
        m2.mkdir(parents=True)
        (m1 / ".actors").mkdir()
        (m2 / ".actors").mkdir()

        config = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "torrents",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[
                DiskConfig(id="disk1", path=disk1, categories=["movies"]),
                DiskConfig(id="disk2", path=disk2, categories=["movies"]),
            ],
            categories={"movies": CategoryConfig(folder_name="films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        clean_library(config, apply=True, only="actors", disk_filter="disk1")

        assert not (m1 / ".actors").exists()
        assert (m2 / ".actors").exists()  # untouched
