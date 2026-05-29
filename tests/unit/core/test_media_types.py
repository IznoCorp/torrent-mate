"""Regression / identity tests for core.media_types (arch-cleanup-2 Phase 3).

Invariants:
- VIDEO_EXTENSIONS in core.media_types is a frozenset containing 'mkv'.
- FileType enum is importable from core.media_types.
- is_trailer_filename is callable and returns bool.
- The VIDEO_EXTENSIONS object is identical (same frozenset) whether imported
  from core.media_types or from sorter.file_type (identity, not just equality).
  This guards against accidental duplication that would allow them to diverge.
"""

from __future__ import annotations

from personalscraper.core.media_types import (
    VIDEO_EXTENSIONS,
    FileType,
    is_trailer_filename,
)


def test_video_extensions_is_frozenset_with_mkv() -> None:
    """VIDEO_EXTENSIONS is a frozenset and contains the canonical 'mkv' extension."""
    assert isinstance(VIDEO_EXTENSIONS, frozenset)
    assert "mkv" in VIDEO_EXTENSIONS


def test_file_type_enum_has_expected_members() -> None:
    """FileType enum is importable and has the canonical members."""
    assert hasattr(FileType, "MOVIE")
    assert hasattr(FileType, "TVSHOW")
    assert FileType.MOVIE.value == "movie"
    assert FileType.TVSHOW.value == "tvshow"


def test_is_trailer_filename_returns_bool() -> None:
    """is_trailer_filename is callable and returns a bool for a known trailer name."""
    result = is_trailer_filename("The.Movie-trailer.mkv")
    assert isinstance(result, bool)
    assert result is True  # stem ends with "-trailer"


def test_is_trailer_filename_non_trailer() -> None:
    """is_trailer_filename returns False for a normal video filename."""
    assert is_trailer_filename("The.Movie.mkv") is False


def test_video_extensions_same_object_as_sorter() -> None:
    """After Phase 3, sorter.file_type.VIDEO_EXTENSIONS IS core.media_types.VIDEO_EXTENSIONS.

    Guards against accidental duplication — the two names must resolve to the
    exact same frozenset object (sorter re-imports from core.media_types).
    """
    from personalscraper.sorter.file_type import VIDEO_EXTENSIONS as sorter_ve

    assert sorter_ve is VIDEO_EXTENSIONS, (
        "sorter.file_type.VIDEO_EXTENSIONS and core.media_types.VIDEO_EXTENSIONS "
        "are different objects — sorter/file_type.py must import from core.media_types, "
        "not re-define the set."
    )
