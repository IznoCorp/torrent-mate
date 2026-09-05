"""The single rule for "does this show already have a trailer".

It exists because the question was answered independently in four places — the
download decision, the derived ``trailer_found`` index, ``trailers audit`` and
the orphan collector — each naming one exact path,
``{show}/Trailers/{show}.{ext}``. A show whose trailer was placed by an earlier
release keeps it in a lowercase ``trailers/`` under a different file name, so
every one of them read it as absent: the runner downloaded a second trailer
beside the first, and once the runner stopped, the shows it stopped downloading
for stayed in the "missing" query forever because the index derived presence
from a narrower question.

WHAT CANNOT BE TESTED HERE, and it is the situation the rule exists for.
``tmp_path`` is on a case-insensitive volume, so ``Trailers/`` and ``trailers/``
collapse into ONE directory in any fixture on this machine — the two-real-
directories case only occurs on the case-sensitive storage mounts. The
discriminating evidence is therefore the production census (606 lowercase
folders against 34 canonical, measured on disk 2026-09-05), not a fixture. What the
holds below CAN pin is the matching rule itself: the case-folding, the ordering,
the sidecar and fragment guards, and the size floor.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.core.media_types import (
    canonical_spelling_first,
    find_trailer_in_media_dir,
    trailer_folders_in,
)


def _show_with(tmp_path: Path, folder: str, filename: str, size: int = 4096) -> Path:
    """Return a show dir holding one file inside the named subfolder."""
    show_dir = tmp_path / "Ahsoka (2023)"
    (show_dir / folder).mkdir(parents=True, exist_ok=True)
    (show_dir / folder / filename).write_bytes(b"\0" * size)
    return show_dir


class TestCanonicalSpellingFirst:
    """The ordering claim, pinned away from the filesystem that cannot show it."""

    def test_the_exact_canonical_name_wins_over_every_variant(self) -> None:
        """A bare sorted() would put TRAILERS first — codepoint order, not intent."""
        folders = [Path(name) for name in ("trailers", "TRAILERS", "Trailers", "TrailerS")]
        assert [p.name for p in sorted(folders, key=canonical_spelling_first)][0] == "Trailers"

    def test_a_bare_sort_would_have_chosen_differently(self) -> None:
        """Pins WHY the key exists: without it the canonical spelling loses."""
        folders = [Path(name) for name in ("trailers", "TRAILERS", "Trailers")]
        assert [p.name for p in sorted(folders)][0] == "TRAILERS"

    def test_the_remainder_is_ordered_stably(self) -> None:
        """The reported path must not depend on filesystem enumeration order."""
        folders = [Path(name) for name in ("trailers", "TrailerS", "TRAILERS")]
        assert [p.name for p in sorted(folders, key=canonical_spelling_first)] == [
            "TRAILERS",
            "TrailerS",
            "trailers",
        ]


class TestTrailerFoldersIn:
    """Which directories count as trailer-extras folders."""

    def test_the_canonical_folder_is_found(self, tmp_path: Path) -> None:
        """The Plex-conformant spelling."""
        show_dir = _show_with(tmp_path, "Trailers", "Ahsoka (2023).mp4")
        assert [p.name.casefold() for p in trailer_folders_in(show_dir)] == ["trailers"]

    def test_the_legacy_spelling_is_found(self, tmp_path: Path) -> None:
        """The defect: an earlier release wrote it in lowercase."""
        show_dir = _show_with(tmp_path, "trailers", "Ahsoka - Saison 1 - trailer.mp4")
        assert [p.name.casefold() for p in trailer_folders_in(show_dir)] == ["trailers"]

    def test_other_plex_extras_folders_are_not_trailer_folders(self, tmp_path: Path) -> None:
        """Only the trailer folder answers."""
        show_dir = _show_with(tmp_path, "Behind The Scenes", "Gag Reel.mkv")
        assert trailer_folders_in(show_dir) == []

    def test_an_unreadable_directory_yields_nothing(self, tmp_path: Path) -> None:
        """An unmounted or moved show dir answers empty rather than raising."""
        assert trailer_folders_in(tmp_path / "nothing here") == []


class TestFindTrailerInMediaDir:
    """What counts as the trailer once the folder is found."""

    def test_a_trailer_named_after_the_show_answers(self, tmp_path: Path) -> None:
        """The canonical placement."""
        show_dir = _show_with(tmp_path, "Trailers", "Ahsoka (2023).mp4")
        assert find_trailer_in_media_dir(show_dir) == show_dir / "Trailers" / "Ahsoka (2023).mp4"

    def test_a_trailer_under_the_legacy_name_answers(self, tmp_path: Path) -> None:
        """The regression: this file read as absent and a second was fetched."""
        show_dir = _show_with(tmp_path, "trailers", "Ahsoka - Saison 1 - trailer.mp4")
        assert find_trailer_in_media_dir(show_dir) is not None

    def test_a_file_with_no_extension_answers(self, tmp_path: Path) -> None:
        """128 of this library's 670 trailer files have none (measured 2026-09-05) — a yt-dlp artefact."""
        show_dir = _show_with(tmp_path, "trailers", "trailer #1")
        assert find_trailer_in_media_dir(show_dir) is not None

    def test_a_dotted_show_title_with_no_extension_answers(self, tmp_path: Path) -> None:
        """``Path.suffix`` is everything after the LAST dot, not the extension.

        ``Path("Mr. Robot - Saison 1 - trailer").suffix`` is
        ``'. Robot - Saison 1 - trailer'``. Judging that as an unknown extension
        hid the file, and Mr. Robot, Dr. Stone and S.W.A.T. are real titles.
        """
        show_dir = _show_with(tmp_path, "trailers", "Mr. Robot - Saison 1 - trailer")
        assert find_trailer_in_media_dir(show_dir) is not None

    def test_a_sidecar_does_not_answer(self, tmp_path: Path) -> None:
        """Admitting extensionless files must not admit every file."""
        show_dir = _show_with(tmp_path, "Trailers", "poster.jpg")
        assert find_trailer_in_media_dir(show_dir) is None

    def test_an_unmerged_format_fragment_does_not_answer(self, tmp_path: Path) -> None:
        """``{stem}.f137.mp4`` is a video-only stream a kill left behind.

        ``.part`` is swept by the downloader's own cleanup; this residue is not,
        and once present it answered for the show forever.
        """
        show_dir = _show_with(tmp_path, "Trailers", "Ahsoka (2023).f137.mp4")
        assert find_trailer_in_media_dir(show_dir) is None

    def test_the_size_floor_is_honoured_when_one_is_given(self, tmp_path: Path) -> None:
        """A truncated download is not a trailer."""
        show_dir = _show_with(tmp_path, "trailers", "trailer #1", size=10)
        assert find_trailer_in_media_dir(show_dir, 1024) is None

    def test_no_floor_asks_only_whether_a_file_is_there(self, tmp_path: Path) -> None:
        """The read-model wants presence, not validation — hence the 0 default."""
        show_dir = _show_with(tmp_path, "trailers", "trailer #1", size=10)
        assert find_trailer_in_media_dir(show_dir) is not None

    def test_a_show_with_no_trailer_folder_has_none(self, tmp_path: Path) -> None:
        """The broadening must not invent a trailer where there is none."""
        show_dir = tmp_path / "Andor (2022)"
        (show_dir / "Saison 01").mkdir(parents=True)
        assert find_trailer_in_media_dir(show_dir) is None
