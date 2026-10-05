"""The library folder's own poster: resolved at request time from the index, never outside the folder."""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.app.errors import AppNotFound, RefusalCode
from personalscraper.app.library.service import POSTER_MAX_BYTES, _folder_poster
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.library_view import mounted_media_folders
from tests.unit.app.library.world import World

_JPEG = b"\xff\xd8\xff\xe0poster"
_PNG = b"\x89PNG\r\n\x1a\nposter"


def _held_show(world: World, root: Path) -> Path:
    """Hold « Outer Range » on disk 1, mounted at ``root``, and return its media folder.

    Args:
        world: The service's world.
        root: The disk's mount point.

    Returns:
        The show's folder, created on the disk.
    """
    world.index.mount(1, root)
    show = world.index.item("Outer Range", kind="show", tvdb="391101", poster_url=None, poster_file=True)
    world.index.episodes(show, 1, [1, 2], folder="series/Outer Range (2022)/Saison 01")
    folder = root / "series" / "Outer Range (2022)"
    (folder / "Saison 01").mkdir(parents=True)
    return folder


def _refused(world: World, ref: MediaRef) -> AppNotFound:
    """Read the poster and return the refusal it raises.

    Args:
        world: The service's world.
        ref: The medium.

    Returns:
        The ``media.not_found`` refusal.
    """
    with pytest.raises(AppNotFound) as refused:
        world.service.read_local_poster(world.actor, ref)
    assert refused.value.code is RefusalCode.MEDIA_NOT_FOUND
    return refused.value


def test_the_folder_poster_is_served_with_its_media_type(world: World, tmp_path: Path) -> None:
    """A show whose NFO names no poster: the folder's ``poster.jpg``, as JPEG."""
    folder = _held_show(world, tmp_path / "disk1")
    (folder / "poster.jpg").write_bytes(_JPEG)
    (folder / "season01-poster.jpg").write_bytes(b"season")

    poster = world.service.read_local_poster(world.actor, MediaRef(tvdb_id=391101))

    assert (poster.content, poster.media_type) == (_JPEG, "image/jpeg")


def test_a_prefixed_png_poster_is_the_inventory_spelling(world: World, tmp_path: Path) -> None:
    """MediaElch's folder-prefixed PNG counts as the poster, as the artwork inventory reads it."""
    world.index.mount(1, tmp_path / "disk1")
    movie = world.index.item("Heat", tmdb="949", poster_file=True)
    world.index.movie_file(movie, "films/Heat (1995)")
    folder = tmp_path / "disk1" / "films" / "Heat (1995)"
    folder.mkdir(parents=True)
    (folder / "Heat (1995)-poster.png").write_bytes(_PNG)

    poster = world.service.read_local_poster(world.actor, MediaRef(tmdb_id=949))

    assert (poster.content, poster.media_type) == (_PNG, "image/png")


def test_an_id_no_row_holds_is_not_found(world: World) -> None:
    """No row carries the id: ``media.not_found``."""
    assert _refused(world, MediaRef(tvdb_id=1)).params == {"provider": "tvdb"}


def test_a_row_without_live_files_is_not_found(world: World, tmp_path: Path) -> None:
    """A row whose files are all tombstoned holds nothing to read a folder from."""
    world.index.mount(1, tmp_path / "disk1")
    movie = world.index.item("Heat", tmdb="949", poster_file=True)
    world.index.movie_file(movie, "films/Heat", deleted=True)
    folder = tmp_path / "disk1" / "films" / "Heat"
    folder.mkdir(parents=True)
    (folder / "poster.jpg").write_bytes(_JPEG)

    _refused(world, MediaRef(tmdb_id=949))


def test_a_folder_without_poster_is_not_found(world: World, tmp_path: Path) -> None:
    """Only a season poster in the folder: no item poster, ``media.not_found``."""
    folder = _held_show(world, tmp_path / "disk1")
    (folder / "season01-poster.jpg").write_bytes(b"season")

    _refused(world, MediaRef(tvdb_id=391101))


def test_an_unmounted_disk_is_not_found(world: World, tmp_path: Path) -> None:
    """The index says the disk is not mounted: ``media.not_found``, the disk never read."""
    folder = _held_show(world, tmp_path / "disk1")
    (folder / "poster.jpg").write_bytes(_JPEG)
    world.index.mount(1, None)

    _refused(world, MediaRef(tvdb_id=391101))


def test_a_vanished_mount_point_is_not_found(world: World, tmp_path: Path) -> None:
    """The index still names a mount point that is gone: ``media.not_found``, never an OS error."""
    _held_show(world, tmp_path / "disk1")
    world.index.mount(1, tmp_path / "gone")

    _refused(world, MediaRef(tvdb_id=391101))


def test_a_symlink_out_of_the_folder_is_never_served(world: World, tmp_path: Path) -> None:
    """A ``poster.jpg`` linking outside the folder is refused; the target's bytes never leave."""
    folder = _held_show(world, tmp_path / "disk1")
    secret = tmp_path / "secret.jpg"
    secret.write_bytes(b"not a poster")
    (folder / "poster.jpg").symlink_to(secret)

    _refused(world, MediaRef(tvdb_id=391101))


def test_a_folder_escaping_its_disk_is_never_read(world: World, tmp_path: Path) -> None:
    """An index path climbing out of the disk (``..``) is refused, whatever it reaches."""
    world.index.mount(1, tmp_path / "disk1")
    (tmp_path / "disk1").mkdir()
    outside = tmp_path / "outside"
    (outside / "Heat").mkdir(parents=True)
    (outside / "poster.jpg").write_bytes(_JPEG)
    movie = world.index.item("Heat", tmdb="949", poster_file=True)
    world.index.movie_file(movie, "../outside/Heat")

    _refused(world, MediaRef(tmdb_id=949))


def test_a_media_folder_in_a_symlink_loop_is_not_found(world: World, tmp_path: Path) -> None:
    """A media folder that is a symlink to itself: ``media.not_found``, never an internal error."""
    world.index.mount(1, tmp_path / "disk1")
    (tmp_path / "disk1" / "films").mkdir(parents=True)
    (tmp_path / "disk1" / "films" / "Heat").symlink_to(tmp_path / "disk1" / "films" / "Heat")
    movie = world.index.item("Heat", tmdb="949", poster_file=True)
    world.index.movie_file(movie, "films/Heat")

    _refused(world, MediaRef(tmdb_id=949))


def test_a_mount_point_in_a_symlink_loop_is_not_found(world: World, tmp_path: Path) -> None:
    """The disk's mount point is a symlink to itself: ``media.not_found``, never an internal error."""
    (tmp_path / "disk1").symlink_to(tmp_path / "disk1")
    world.index.mount(1, tmp_path / "disk1")
    movie = world.index.item("Heat", tmdb="949", poster_file=True)
    world.index.movie_file(movie, "films/Heat")

    _refused(world, MediaRef(tmdb_id=949))


@pytest.mark.parametrize("rel_path", ["films", "", "a/../x"], ids=["category", "empty", "dot-dot"])
def test_a_folder_that_is_not_a_media_folder_is_never_read(world: World, tmp_path: Path, rel_path: str) -> None:
    """An index path naming the category or the disk's root, not a media folder: its posters are never served."""
    root = tmp_path / "disk1"
    world.index.mount(1, root)
    for directory in (root / "a" / "x", root / "films"):
        directory.mkdir(parents=True)
    for directory in (root, root / "films", root / "a", root / "a" / "x"):
        (directory / "poster.jpg").write_bytes(_JPEG)
    movie = world.index.item("Heat", tmdb="949", poster_file=True)
    world.index.movie_file(movie, rel_path)

    _refused(world, MediaRef(tmdb_id=949))


@pytest.mark.parametrize("folder", ["films", "a/..", "a/../films"], ids=["shallow", "root", "category"])
def test_a_folder_resolving_above_media_depth_is_never_read(tmp_path: Path, folder: str) -> None:
    """Whatever the index spells, a folder resolving to the disk or a category is never read from."""
    root = tmp_path / "disk1"
    for directory in (root / "a", root / "films"):
        directory.mkdir(parents=True)
    for directory in (root, root / "films", root / "a"):
        (directory / "poster.jpg").write_bytes(_JPEG)

    assert _folder_poster(str(root), folder) is None


def test_only_paths_naming_a_media_folder_are_media_folders(world: World, tmp_path: Path) -> None:
    """The index's paths are cut to their media folder; a shallow or dotted one names none."""
    world.index.mount(1, tmp_path / "disk1")
    movie = world.index.item("Heat", tmdb="949", poster_file=True)
    for rel_path in ("films/Heat/Extras", "films", "", "a/../x", "./films/Heat", "films//Heat"):
        world.index.movie_file(movie, rel_path)

    assert mounted_media_folders(world.index.conn, movie) == [(str(tmp_path / "disk1"), "films/Heat")]


def test_a_poster_over_the_size_cap_is_never_read(world: World, tmp_path: Path) -> None:
    """A poster file larger than the cap is refused before it is read (a sparse file, nothing written)."""
    folder = _held_show(world, tmp_path / "disk1")
    with (folder / "poster.jpg").open("wb") as poster:
        poster.truncate(POSTER_MAX_BYTES + 1)

    _refused(world, MediaRef(tvdb_id=391101))


def test_a_media_folder_linking_out_of_the_disk_is_never_read(world: World, tmp_path: Path) -> None:
    """A media folder that is a symlink to a folder outside the disk is refused, its poster never served."""
    world.index.mount(1, tmp_path / "disk1")
    outside = tmp_path / "outside" / "Heat"
    outside.mkdir(parents=True)
    (outside / "poster.jpg").write_bytes(_JPEG)
    (tmp_path / "disk1" / "films").mkdir(parents=True)
    (tmp_path / "disk1" / "films" / "Heat").symlink_to(outside, target_is_directory=True)
    movie = world.index.item("Heat", tmdb="949", poster_file=True)
    world.index.movie_file(movie, "films/Heat")

    _refused(world, MediaRef(tmdb_id=949))
