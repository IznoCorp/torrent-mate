"""Tests for personalscraper.maintenance.disk_cleaner — library cleanup."""

from pathlib import Path

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.maintenance.disk_cleaner import clean_library
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
        """NTFS deletion failure should log error and continue.

        Hooks the project's custom recursive remover (``_scandir_rmtree``)
        because the cleaner switched away from ``shutil.rmtree`` to handle
        NFC/NFD ghost dirents — see fix(library-clean) commit history.
        """
        from personalscraper.maintenance import disk_cleaner as _dc

        disk = tmp_path / "medias"
        movie1 = disk / "films" / "Movie1 (2024)" / ".actors"
        movie2 = disk / "films" / "Movie2 (2024)" / ".actors"
        movie1.mkdir(parents=True)
        movie2.mkdir(parents=True)
        (movie1 / "a.jpg").write_bytes(b"\x00")
        (movie2 / "b.jpg").write_bytes(b"\x00")

        call_count = 0
        original = _dc._scandir_rmtree

        def flaky(path, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("NTFS permission denied")
            original(path, *args, **kwargs)

        monkeypatch.setattr(_dc, "_scandir_rmtree", flaky)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="actors")

        # First deletion failed, second succeeded.
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


class TestCleanFilters:
    """Tests for filter handling and edge cases in ``clean_library``."""

    def test_disk_not_mounted_skipped(self, tmp_path: Path) -> None:
        """Non-existent disk path should be skipped with a warning, not raise."""
        missing_disk = tmp_path / "nonexistent_disk"
        config = _make_v15_config(missing_disk, "diskx", "films", "movies", tmp_path)

        result = clean_library(config, apply=False, only="actors")

        # No work to do but no failure either.
        assert result.deleted_count == 0
        assert result.error_count == 0

    def test_category_filter_skips_other_categories(self, tmp_path: Path) -> None:
        """``category_filter`` should restrict cleanup to the named category."""
        disk_path = tmp_path / "medias"
        # Two categories on the same disk: only ``movies`` should be cleaned.
        movies_actors = disk_path / "films" / "Movie (2024)" / ".actors"
        shows_actors = disk_path / "series" / "Show (2024)" / ".actors"
        movies_actors.mkdir(parents=True)
        shows_actors.mkdir(parents=True)
        (movies_actors / "a.jpg").write_bytes(b"\x00")
        (shows_actors / "b.jpg").write_bytes(b"\x00")

        disk_cfg = DiskConfig(id="disk1", path=disk_path, categories=["movies", "tv_shows"])
        config = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "torrents",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[disk_cfg],
            categories={
                "movies": CategoryConfig(folder_name="films"),
                "tv_shows": CategoryConfig(folder_name="series"),
            },
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        clean_library(config, apply=True, only="actors", category_filter="movies")

        assert not movies_actors.exists()
        assert shows_actors.exists()

    def test_category_dir_missing_skipped(self, tmp_path: Path) -> None:
        """If the category directory doesn't exist, cleanup skips it silently."""
        disk_path = tmp_path / "medias"
        disk_path.mkdir(parents=True)  # disk exists, but no ``films/`` inside.

        config = _make_v15_config(disk_path, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=False, only="actors")

        assert result.deleted_count == 0
        assert result.error_count == 0

    def test_hidden_dir_in_category_skipped(self, tmp_path: Path) -> None:
        """Media directories starting with '.' should be skipped (e.g. ``.Trash``)."""
        disk_path = tmp_path / "medias"
        category = disk_path / "films"
        category.mkdir(parents=True)
        # A hidden subdirectory like ``.Trash``: would otherwise look "empty"
        # but the loop skips anything starting with '.'.
        hidden = category / ".Trash"
        hidden.mkdir()

        config = _make_v15_config(disk_path, "disk1", "films", "movies", tmp_path)
        clean_library(config, apply=True, only="empty")

        assert hidden.exists()  # still there

    def test_unlistable_media_dir_records_error(self, tmp_path: Path, monkeypatch) -> None:
        """OSError when listing a media directory should be recorded as an error."""
        from personalscraper.maintenance import disk_cleaner as _dc

        disk_path = tmp_path / "medias"
        movie = disk_path / "films" / "Movie (2024)"
        movie.mkdir(parents=True)

        original_iterdir = Path.iterdir

        def flaky_iterdir(self):
            # Raise only for the media_dir itself, not the category listing.
            if self == movie:
                raise OSError("permission denied")
            return original_iterdir(self)

        monkeypatch.setattr(_dc.Path, "iterdir", flaky_iterdir)

        config = _make_v15_config(disk_path, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="actors")

        assert result.error_count == 1
        assert any("Cannot list directory" in e for e in result.errors)


class TestCleanOrphans:
    """Tests for ``--only orphans`` mode."""

    def test_orphan_dir_deleted(self, tmp_path: Path) -> None:
        """A non-empty release dir without any main video should be deleted."""
        disk_path = tmp_path / "medias"
        movie = disk_path / "films" / "Ghost Movie (2024)"
        movie.mkdir(parents=True)
        # Residue: NFO + actors but no main video file.
        (movie / "movie.nfo").write_text("<movie/>")
        (movie / ".actors").mkdir()
        (movie / ".actors" / "Actor.jpg").write_bytes(b"\x00")

        config = _make_v15_config(disk_path, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="orphans")

        assert not movie.exists()
        assert result.deleted_count == 1

    def test_orphan_dry_run_keeps_dir(self, tmp_path: Path) -> None:
        """Dry-run on orphans must not delete anything."""
        disk_path = tmp_path / "medias"
        movie = disk_path / "films" / "Ghost Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.nfo").write_text("<movie/>")

        config = _make_v15_config(disk_path, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=False, only="orphans")

        assert movie.exists()
        assert result.deleted_count == 1  # would-delete count
        assert result.dry_run is True

    def test_orphan_with_main_video_kept(self, tmp_path: Path) -> None:
        """A release dir that contains a substantial video must be preserved."""
        disk_path = tmp_path / "medias"
        movie = disk_path / "films" / "Real Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.mkv").write_bytes(b"\x00" * (51 * 1024 * 1024))  # >50 MB
        (movie / "movie.nfo").write_text("<movie/>")

        config = _make_v15_config(disk_path, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="orphans")

        assert movie.exists()
        assert result.deleted_count == 0

    def test_orphan_empty_dir_skipped(self, tmp_path: Path) -> None:
        """Truly empty dirs are out of scope for orphans (handled by ``empty`` mode)."""
        disk_path = tmp_path / "medias"
        movie = disk_path / "films" / "Empty (2024)"
        movie.mkdir(parents=True)  # nothing inside

        config = _make_v15_config(disk_path, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="orphans")

        # Empty dir not counted as orphan; orphan mode leaves it alone.
        assert movie.exists()
        assert result.deleted_count == 0

    def test_orphan_with_only_trailer_is_deleted(self, tmp_path: Path) -> None:
        """A release dir with just a trailer/sample video is still an orphan."""
        disk_path = tmp_path / "medias"
        movie = disk_path / "films" / "Trailer Only (2024)"
        movie.mkdir(parents=True)
        # Trailer marker in stem demotes it from "main video".
        (movie / "movie-trailer.mp4").write_bytes(b"\x00" * (60 * 1024 * 1024))
        (movie / "movie.nfo").write_text("<movie/>")

        config = _make_v15_config(disk_path, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="orphans")

        assert not movie.exists()
        assert result.deleted_count == 1

    def test_orphan_main_video_in_season_dir(self, tmp_path: Path) -> None:
        """TV shows with episodes inside ``Saison 01/`` count as having a main video."""
        disk_path = tmp_path / "medias"
        show = disk_path / "series" / "Show (2024)"
        season = show / "Saison 01"
        season.mkdir(parents=True)
        (season / "S01E01.mkv").write_bytes(b"\x00" * (60 * 1024 * 1024))
        (show / "tvshow.nfo").write_text("<tvshow/>")

        config = _make_v15_config(disk_path, "disk1", "series", "tv_shows", tmp_path)
        result = clean_library(config, apply=True, only="orphans")

        assert show.exists()
        assert result.deleted_count == 0

    def test_orphan_too_small_video_is_orphan(self, tmp_path: Path) -> None:
        """Sub-50 MB videos don't count as main, so the dir is an orphan."""
        disk_path = tmp_path / "medias"
        movie = disk_path / "films" / "Tiny (2024)"
        movie.mkdir(parents=True)
        (movie / "tiny.mkv").write_bytes(b"\x00" * 1024)  # 1 KB
        (movie / "movie.nfo").write_text("<movie/>")

        config = _make_v15_config(disk_path, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="orphans")

        assert not movie.exists()
        assert result.deleted_count == 1

    def test_orphan_skip_audiobook_category(self, tmp_path: Path) -> None:
        """Audiobook category is skipped by orphan mode (no video = expected)."""
        disk_path = tmp_path / "medias"
        book = disk_path / "audiobooks" / "Book"
        book.mkdir(parents=True)
        (book / "book.m4b").write_bytes(b"\x00" * 1024)

        disk_cfg = DiskConfig(id="disk1", path=disk_path, categories=["audiobooks"])
        config = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "torrents",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[disk_cfg],
            categories={"audiobooks": CategoryConfig(folder_name="audiobooks")},
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        result = clean_library(config, apply=True, only="orphans")

        assert book.exists()
        assert result.deleted_count == 0


class TestInternalHelpers:
    """Direct tests of internal helpers — fault paths not reachable via clean_library."""

    def test_dir_size_oserror_returns_zero(self, tmp_path: Path, monkeypatch) -> None:
        """``_dir_size`` should swallow OSError from rglob and return what was counted."""
        from personalscraper.maintenance import disk_cleaner as _dc

        d = tmp_path / "d"
        d.mkdir()

        def boom(self, _pattern):
            raise OSError("rglob failed")

        monkeypatch.setattr(_dc.Path, "rglob", boom)
        # Should not raise; total stays at 0.
        assert _dc._dir_size(d) == 0

    def test_dir_size_skips_unstattable_files(self, tmp_path: Path, monkeypatch) -> None:
        """``_dir_size`` should skip files whose ``stat()`` raises OSError."""
        from personalscraper.maintenance import disk_cleaner as _dc

        d = tmp_path / "d"
        d.mkdir()
        (d / "ok.txt").write_bytes(b"hi")

        original_stat = Path.stat

        def flaky_stat(self, *args, **kwargs):
            if self.name == "ok.txt":
                raise OSError("permission")
            return original_stat(self, *args, **kwargs)

        monkeypatch.setattr(_dc.Path, "stat", flaky_stat)
        assert _dc._dir_size(d) == 0

    def test_scandir_rmtree_unlinks_symlink(self, tmp_path: Path) -> None:
        """``_scandir_rmtree`` should ``unlink`` a symlink rather than recurse."""
        from personalscraper.maintenance import disk_cleaner as _dc

        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)

        _dc._scandir_rmtree(link)
        assert not link.exists()
        assert target.exists()  # target untouched

    def test_scandir_rmtree_unlinks_non_directory(self, tmp_path: Path) -> None:
        """``_scandir_rmtree`` should ``unlink`` a path that is not a directory."""
        from personalscraper.maintenance import disk_cleaner as _dc

        f = tmp_path / "f.txt"
        f.write_bytes(b"hi")
        _dc._scandir_rmtree(f)
        assert not f.exists()

    def test_scandir_rmtree_records_ghost_filenotfound(self, tmp_path: Path, monkeypatch) -> None:
        """FileNotFoundError on unlink should be recorded as a ghost dirent."""
        import os as _os

        from personalscraper.maintenance import disk_cleaner as _dc

        d = tmp_path / "d"
        d.mkdir()
        (d / "real.txt").write_bytes(b"x")

        original_unlink = _os.unlink

        def flaky_unlink(p):
            if str(p).endswith("real.txt"):
                raise FileNotFoundError("ghost")
            return original_unlink(p)

        monkeypatch.setattr(_dc.os, "unlink", flaky_unlink)

        ghosts: list[str] = []
        # Parent rmdir will then raise OSError (ENOTEMPTY) — bubble it up.
        try:
            _dc._scandir_rmtree(d, ghosts=ghosts)
        except OSError:
            pass

        assert any("real.txt" in g for g in ghosts)

    def test_scandir_rmtree_records_ghost_on_is_dir_oserror(self, tmp_path: Path, monkeypatch) -> None:
        """If ``DirEntry.is_dir`` raises OSError the entry is logged as ghost."""
        from personalscraper.maintenance import disk_cleaner as _dc

        d = tmp_path / "d"
        d.mkdir()
        (d / "x").write_bytes(b"hi")

        class FlakyEntry:
            def __init__(self, real):
                self._real = real
                self.path = real.path

            def is_dir(self, follow_symlinks=False):  # noqa: ARG002
                raise OSError("ghost is_dir")

        original_scandir = _dc.os.scandir

        class FlakyScandir:
            def __init__(self, path):
                self._inner = original_scandir(path)

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self._inner.__exit__(*_)

            def __iter__(self):
                for e in self._inner:
                    yield FlakyEntry(e)

        monkeypatch.setattr(_dc.os, "scandir", lambda p: FlakyScandir(p))

        ghosts: list[str] = []
        try:
            _dc._scandir_rmtree(d, ghosts=ghosts)
        except OSError:
            pass
        assert ghosts, "expected at least one ghost recorded"

    def test_delete_file_stat_oserror_size_zero(self, tmp_path: Path, monkeypatch) -> None:
        """File whose ``stat()`` fails is reported with size 0 but still deleted."""
        from personalscraper.maintenance import disk_cleaner as _dc

        f = tmp_path / "f.txt"
        f.write_bytes(b"hi")

        def boom(self, *args, **kwargs):
            raise OSError("no stat")

        monkeypatch.setattr(_dc.Path, "stat", boom)

        result = _dc.CleanResult(dry_run=False)
        # Disable outbox publish to keep this hermetic.
        monkeypatch.setattr(_dc, "_publish_deleted", lambda *a, **k: None)
        _dc._delete_file(f, result, dry_run=False, label="x", db_path=tmp_path / "db.sqlite")
        # Restore stat so the existence check below works normally.
        monkeypatch.undo()
        assert result.deleted_count == 1
        assert result.freed_bytes == 0
        assert not f.exists()

    def test_delete_file_unlink_oserror_recorded(self, tmp_path: Path, monkeypatch) -> None:
        """``unlink`` failure is recorded as a CleanResult error."""
        from personalscraper.maintenance import disk_cleaner as _dc

        f = tmp_path / "f.txt"
        f.write_bytes(b"hi")

        def boom(self):
            raise OSError("locked")

        monkeypatch.setattr(_dc.Path, "unlink", boom)

        result = _dc.CleanResult(dry_run=False)
        _dc._delete_file(f, result, dry_run=False, label="x", db_path=tmp_path / "db.sqlite")
        assert result.error_count == 1
        assert result.deleted_count == 0

    def test_delete_dir_records_ghost_summary(self, tmp_path: Path, monkeypatch) -> None:
        """When ``_scandir_rmtree`` reports ghosts, ``_delete_dir`` summarises them."""
        from personalscraper.maintenance import disk_cleaner as _dc

        d = tmp_path / "ghosted"
        d.mkdir()

        # Simulate the ghost path: rmtree appends to ``ghosts`` and raises.
        def fake_rmtree(path, ghosts=None):
            if ghosts is not None:
                ghosts.extend(["g1.jpg", "g2.jpg", "g3.jpg", "g4.jpg"])
            raise OSError("ENOTEMPTY")

        monkeypatch.setattr(_dc, "_scandir_rmtree", fake_rmtree)

        result = _dc.CleanResult(dry_run=False)
        _dc._delete_dir(d, result, dry_run=False, label=".actors", db_path=tmp_path / "db.sqlite")

        assert result.error_count == 1
        assert any("ghost dirent" in e for e in result.errors)

    def test_is_effectively_empty_oserror_returns_false(self, tmp_path: Path, monkeypatch) -> None:
        """If the dir cannot be listed it is conservatively considered non-empty."""
        from personalscraper.maintenance import disk_cleaner as _dc

        d = tmp_path / "d"
        d.mkdir()

        def boom(self):
            raise OSError("nope")

        monkeypatch.setattr(_dc.Path, "iterdir", boom)
        assert _dc._is_effectively_empty(d) is False

    def test_has_main_video_oserror_returns_true(self, tmp_path: Path, monkeypatch) -> None:
        """If the dir cannot be listed, ``_has_main_video`` returns True."""
        from personalscraper.maintenance import disk_cleaner as _dc

        d = tmp_path / "d"
        d.mkdir()

        def boom(self):
            raise OSError("nope")

        monkeypatch.setattr(_dc.Path, "iterdir", boom)
        assert _dc._has_main_video(d) is True

    def test_has_main_video_season_iterdir_oserror_returns_true(self, tmp_path: Path, monkeypatch) -> None:
        """OSError listing a Saison sub-dir is conservatively a 'video present'."""
        from personalscraper.maintenance import disk_cleaner as _dc

        show = tmp_path / "Show"
        season = show / "Saison 01"
        season.mkdir(parents=True)
        (season / "ep.mkv").write_bytes(b"\x00")

        original = Path.iterdir

        def flaky(self):
            if self == season:
                raise OSError("ghost season listing")
            return original(self)

        monkeypatch.setattr(_dc.Path, "iterdir", flaky)
        assert _dc._has_main_video(show) is True

    def test_looks_like_main_video_non_video_extension(self, tmp_path: Path) -> None:
        """Non-video extensions are rejected outright."""
        from personalscraper.maintenance import disk_cleaner as _dc

        f = tmp_path / "doc.txt"
        f.write_bytes(b"\x00")
        assert _dc._looks_like_main_video(f) is False

    def test_looks_like_main_video_trailer_marker_rejected(self, tmp_path: Path) -> None:
        """Filenames containing trailer markers are not 'main' videos."""
        from personalscraper.maintenance import disk_cleaner as _dc

        f = tmp_path / "movie-trailer.mp4"
        f.write_bytes(b"\x00" * (60 * 1024 * 1024))
        assert _dc._looks_like_main_video(f) is False

    def test_looks_like_main_video_stat_oserror_returns_false(self, tmp_path: Path, monkeypatch) -> None:
        """``stat()`` failure means we cannot confirm size — treat as non-main."""
        from personalscraper.maintenance import disk_cleaner as _dc

        f = tmp_path / "movie.mkv"
        f.write_bytes(b"\x00")

        def boom(self, *args, **kwargs):
            raise OSError("stat failed")

        monkeypatch.setattr(_dc.Path, "stat", boom)
        assert _dc._looks_like_main_video(f) is False

    def test_publish_deleted_no_disk_match_silent(self, tmp_path: Path, monkeypatch) -> None:
        """When ``disk_id_for_path`` returns None, publish is skipped without error."""
        from personalscraper.maintenance import disk_cleaner as _dc

        called: dict[str, bool] = {"publish": False}

        def fake_disk_id_for_path(_path, _db_path):
            return None

        def fake_publish_event(*args, **kwargs):  # pragma: no cover - should not run
            called["publish"] = True

        # Patch the deferred imports inside _publish_deleted via sys.modules.
        import personalscraper.indexer.outbox._disk as _disk_mod
        import personalscraper.indexer.outbox._publish as _pub_mod

        monkeypatch.setattr(_disk_mod, "disk_id_for_path", fake_disk_id_for_path)
        monkeypatch.setattr(_pub_mod, "publish_event", fake_publish_event)

        # Should not raise.
        _dc._publish_deleted(tmp_path / "x.jpg", ".actors", tmp_path / "db.sqlite")
        assert called["publish"] is False

    def test_publish_deleted_calls_publish_event(self, tmp_path: Path, monkeypatch) -> None:
        """When disk match succeeds, publish_event is called with op='move'."""
        from personalscraper.maintenance import disk_cleaner as _dc

        captured: dict[str, object] = {}

        def fake_disk_id_for_path(_path, _db_path):
            return (42, "rel/path/x.jpg")

        def fake_publish_event(disk_id, op, payload, db_path, source):
            captured["disk_id"] = disk_id
            captured["op"] = op
            captured["payload"] = payload
            captured["source"] = source

        import personalscraper.indexer.outbox._disk as _disk_mod
        import personalscraper.indexer.outbox._publish as _pub_mod

        monkeypatch.setattr(_disk_mod, "disk_id_for_path", fake_disk_id_for_path)
        monkeypatch.setattr(_pub_mod, "publish_event", fake_publish_event)

        _dc._publish_deleted(tmp_path / "x.jpg", ".actors", tmp_path / "db.sqlite")
        assert captured["disk_id"] == 42
        assert captured["op"] == "move"
        assert captured["payload"]["src_rel_path"] == "rel/path/x.jpg"
        assert captured["payload"]["dst_rel_path"] == ""
        assert captured["payload"]["_clean_label"] == ".actors"

    def test_publish_deleted_swallows_exceptions(self, tmp_path: Path, monkeypatch) -> None:
        """Any exception inside publish must be swallowed (best-effort)."""
        from personalscraper.maintenance import disk_cleaner as _dc

        def fake_disk_id_for_path(_path, _db_path):
            raise RuntimeError("DB exploded")

        import personalscraper.indexer.outbox._disk as _disk_mod

        monkeypatch.setattr(_disk_mod, "disk_id_for_path", fake_disk_id_for_path)

        # Must not raise.
        _dc._publish_deleted(tmp_path / "x.jpg", ".actors", tmp_path / "db.sqlite")


class TestDeletePermitHardSkip:
    """Tests for the VETO hard-skip behaviour (DESIGN §7.3)."""

    @staticmethod
    def _veto_actors_permit():
        """A DeletePermit that vetoes .actors/ directories."""
        from personalscraper.core.delete_permit import ALLOW, veto

        class VetoActorsPermit:
            def may_delete(self, path: Path):
                if ".actors" in str(path):
                    return veto("still-seeding-actors")
                return ALLOW

        return VetoActorsPermit()

    @staticmethod
    def _veto_everything_permit():
        """A DeletePermit that vetoes everything."""
        from personalscraper.core.delete_permit import veto

        class VetoAllPermit:
            def may_delete(self, path: Path):
                return veto("still-seeding-all")

        return VetoAllPermit()

    def test_veto_hard_skip_actors_dir(self, tmp_path: Path) -> None:
        """VETO on .actors/ dir → hard-skip, count, NOT deleted."""
        from personalscraper.core.delete_permit import ALLOW, veto

        veto_count = 0

        class CountingVetoPermit:
            def may_delete(self, path: Path):
                nonlocal veto_count
                if ".actors" in str(path):
                    veto_count += 1
                    return veto("still-seeding-actors")
                return ALLOW

        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        actors = movie / ".actors"
        actors.mkdir(parents=True)
        (actors / "thumb.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="actors", permit=CountingVetoPermit())

        # Must be skipped, not deleted.
        assert actors.exists(), "VETOed .actors/ directory MUST NOT be deleted"
        assert result.deleted_count == 0, "VETOed items should NOT count as deleted"
        assert result.skipped_by_obligation == 1, f"Expected 1 skip, got {result.skipped_by_obligation}"
        assert veto_count == 1

    def test_veto_dry_run_still_counts_skip(self, tmp_path: Path) -> None:
        """Dry-run with VETO → skip counted, item untouched."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        actors = movie / ".actors"
        actors.mkdir(parents=True)
        (actors / "thumb.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=False, only="actors", permit=self._veto_actors_permit())

        # Dry-run must still show the veto (before the dry-run branch).
        assert actors.exists(), "DRY-RUN VETOed .actors/ MUST still exist"
        assert result.skipped_by_obligation == 1, f"DRY-RUN should count skip, got {result.skipped_by_obligation}"

    def test_allow_permit_deletes_actors(self, tmp_path: Path) -> None:
        """ALLOW permit → normal deletion proceeds."""
        from personalscraper.core.delete_permit import AllowAllPermit

        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        actors = movie / ".actors"
        actors.mkdir(parents=True)
        (actors / "thumb.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="actors", permit=AllowAllPermit())

        assert not actors.exists(), "ALLOWed .actors/ directory MUST be deleted"
        assert result.deleted_count == 1
        assert result.skipped_by_obligation == 0

    def test_fail_open_default_still_deletes(self, tmp_path: Path) -> None:
        """AllowAllPermit (default) → deletion proceeds (unchanged behavior)."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        actors = movie / ".actors"
        actors.mkdir(parents=True)
        (actors / "thumb.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        # No permit arg → default AllowAllPermit().
        result = clean_library(config, apply=True, only="actors")

        assert not actors.exists(), "Default permit MUST allow deletion"
        assert result.deleted_count == 1
        assert result.skipped_by_obligation == 0

    def test_veto_hard_skip_junk_file(self, tmp_path: Path) -> None:
        """VETO on a junk file → hard-skip, count, NOT deleted."""
        from personalscraper.core.delete_permit import ALLOW, veto

        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        junk = movie / ".DS_Store"
        junk.write_text("junk")

        class VetoJunkPermit:
            def may_delete(self, path: Path):
                if ".DS_Store" in str(path):
                    return veto("still-seeding-junk")
                return ALLOW

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        result = clean_library(config, apply=True, only="junk", permit=VetoJunkPermit())

        assert junk.exists(), "VETOed junk file MUST NOT be deleted"
        assert result.deleted_count == 0
        assert result.skipped_by_obligation == 1


class _RaisingPermit:
    """A DeletePermit whose may_delete always raises (F2 fail-open consult)."""

    def may_delete(self, path: Path):  # noqa: D102, ANN001
        raise RuntimeError("permit boom")


class TestDeletePermitConsultFailOpen:
    """F2: a raising permit consult is fail-open — deletion PROCEEDS + logs.

    DESIGN §7.3 / §9: ``permit.may_delete`` may raise (DB locked, corrupt
    store, etc.). The consult must never abort cleanup — the deleter treats
    the error as ALLOW and logs ``disk_cleaner.permit_error``. Pre-fix the
    exception propagated and failed the clean run CLOSED.
    """

    def test_delete_dir_raising_permit_deletes_and_logs(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """``_delete_dir`` with a raising permit DELETES (ALLOW) + logs permit_error."""
        from personalscraper.maintenance import disk_cleaner as _dc

        d = tmp_path / "medias" / ".actors"
        d.mkdir(parents=True)
        (d / "thumb.jpg").write_bytes(b"\x00" * 100)

        result = _dc.CleanResult(dry_run=False)
        monkeypatch.setattr(_dc, "_publish_deleted", lambda *a, **k: None)
        with caplog.at_level("WARNING"):
            _dc._delete_dir(
                d, result, dry_run=False, label=".actors", db_path=tmp_path / "db.sqlite", permit=_RaisingPermit()
            )

        # Real deletion happened (fail-open ALLOW), NOT skipped, NOT aborted.
        assert not d.exists(), "Raising permit MUST fail OPEN → dir deleted"
        assert result.deleted_count == 1
        assert result.skipped_by_obligation == 0
        assert "disk_cleaner.permit_error" in caplog.text
        assert "permit boom" in caplog.text

    def test_delete_file_raising_permit_deletes_and_logs(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """``_delete_file`` with a raising permit DELETES (ALLOW) + logs permit_error."""
        from personalscraper.maintenance import disk_cleaner as _dc

        f = tmp_path / ".DS_Store"
        f.write_text("junk")

        result = _dc.CleanResult(dry_run=False)
        monkeypatch.setattr(_dc, "_publish_deleted", lambda *a, **k: None)
        with caplog.at_level("WARNING"):
            _dc._delete_file(
                f, result, dry_run=False, label="junk", db_path=tmp_path / "db.sqlite", permit=_RaisingPermit()
            )

        assert not f.exists(), "Raising permit MUST fail OPEN → file deleted"
        assert result.deleted_count == 1
        assert result.skipped_by_obligation == 0
        assert "disk_cleaner.permit_error" in caplog.text
        assert "permit boom" in caplog.text

    def test_clean_library_raising_permit_does_not_abort(self, tmp_path: Path) -> None:
        """End-to-end: ``clean_library`` with a raising permit completes (deletes)."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        actors = movie / ".actors"
        actors.mkdir(parents=True)
        (actors / "thumb.jpg").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        # No raise propagates out of clean_library → the run completes.
        result = clean_library(config, apply=True, only="actors", permit=_RaisingPermit())

        assert not actors.exists(), "Raising permit MUST NOT abort cleanup"
        assert result.deleted_count == 1
        assert result.skipped_by_obligation == 0
