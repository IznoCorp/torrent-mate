"""Tests for the filesystem probe behind trailer-orphan classification.

``_media_dir_has_content`` decides whether a media directory absent from the
index still holds its media. Its answer routes the directory: holding media it
becomes an index gap to heal and keeps its trailers; holding none, its trailers
are true orphans. Its docstring promises a video "not inside a ``Trailers/``
subfolder", and the storage mounts are case-sensitive, so a trailer folder
written under the older lowercase name was descended into like an episode dir.

The legacy files are named ``{show} - Saison 1 - trailer.mp4``, whose stem ends
with "- trailer" and not "-trailer", so :func:`is_trailer_filename` does not
recognise them either — a trailer alone therefore answered for the media.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.trailers.purge_fs import _media_dir_has_content


def _make_file(path: Path, size: int = 4096) -> None:
    """Create *path* and its parents, holding *size* bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)


class TestMediaDirHasContent:
    """Tests for _media_dir_has_content() — media present, or trailers only."""

    def test_a_legacy_trailer_folder_is_not_media(self, tmp_path: Path) -> None:
        """The defect: a show holding only its legacy trailer read as holding media."""
        show_dir = tmp_path / "Ahsoka (2023)"
        _make_file(show_dir / "trailers" / "Ahsoka - Saison 1 - trailer.mp4")
        assert _media_dir_has_content(show_dir) is False

    def test_a_canonical_trailer_folder_is_not_media(self, tmp_path: Path) -> None:
        """The spelling the probe already skipped keeps behaving as it did."""
        show_dir = tmp_path / "Ahsoka (2023)"
        _make_file(show_dir / "Trailers" / "Ahsoka (2023).mp4")
        assert _media_dir_has_content(show_dir) is False

    def test_an_episode_one_level_down_is_media(self, tmp_path: Path) -> None:
        """The TV layout the probe exists for still answers True."""
        show_dir = tmp_path / "Ahsoka (2023)"
        _make_file(show_dir / "Saison 01" / "Ahsoka - S01E01.mkv")
        assert _media_dir_has_content(show_dir) is True

    def test_a_flat_movie_video_is_media(self, tmp_path: Path) -> None:
        """The movie layout still answers True."""
        movie_dir = tmp_path / "Fight Club (1999)"
        _make_file(movie_dir / "Fight Club (1999).mkv")
        assert _media_dir_has_content(movie_dir) is True

    def test_a_show_with_both_a_trailer_folder_and_episodes_is_media(self, tmp_path: Path) -> None:
        """A characterization hold, green before and after — NOT a proof of the fix.

        The episode is found through the season directory whatever the trailer
        folder is called, so the skip plays no part. It is kept because it pins
        that the change subtracts nothing from a show that does hold its media,
        which is the direction a reader will worry about.
        """
        show_dir = tmp_path / "Ahsoka (2023)"
        _make_file(show_dir / "trailers" / "Ahsoka - Saison 1 - trailer.mp4")
        _make_file(show_dir / "Saison 01" / "Ahsoka - S01E01.mkv")
        assert _media_dir_has_content(show_dir) is True

    def test_an_absent_directory_is_not_media(self, tmp_path: Path) -> None:
        """An unmounted or moved dir answers False rather than raising."""
        assert _media_dir_has_content(tmp_path / "nothing here") is False
