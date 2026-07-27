"""Unit tests for the canonical artwork-presence detection (core/artwork_naming).

Covers :func:`artwork_status` — the single presence owner (DESIGN §5 T4) — across
every legitimate spelling the six former presence checks recognized between them:
the bare Kodi name, the Kodi ``folder.jpg``, the scraper title-prefixed form, the
MediaElch folder-prefixed form, TV show fixed names and season posters, plus the
absent case. Also pins the thin wrappers ``artwork_flags`` / ``has_poster`` to the
same detection so no spelling drifts between them.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.core.artwork_naming import (
    ArtworkStatus,
    artwork_flags,
    artwork_status,
    has_poster,
)


def _touch(directory: Path, *names: str) -> None:
    """Create empty files ``names`` inside ``directory``.

    Args:
        directory: Target directory (created if absent).
        *names: Filenames to create.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(b"")


def test_canonical_bare_names(tmp_path: Path) -> None:
    """Bare Kodi names (``poster.jpg`` / ``fanart.jpg`` / ``landscape.jpg``) are detected."""
    _touch(tmp_path, "poster.jpg", "fanart.jpg", "landscape.jpg", "movie.mkv")
    status = artwork_status(tmp_path, "tvshow")
    assert status.poster is True
    assert status.fanart is True
    assert status.landscape is True
    assert status.poster_name == "poster.jpg"
    assert status.fanart_name == "fanart.jpg"
    assert status.landscape_name == "landscape.jpg"


def test_media_prefixed_scraper_form(tmp_path: Path) -> None:
    """The scraper title-prefixed form (``{Title}-poster.jpg``) is detected."""
    _touch(
        tmp_path,
        "Fight Club (1999)-poster.jpg",
        "Fight Club (1999)-fanart.jpg",
        "Fight Club (1999)-landscape.jpg",
    )
    status = artwork_status(tmp_path, "movie")
    assert status.poster is True
    assert status.fanart is True
    assert status.landscape is True
    assert status.poster_name == "Fight Club (1999)-poster.jpg"


def test_mediaelch_folder_prefixed_png(tmp_path: Path) -> None:
    """MediaElch's folder-prefixed ``.png`` form (``{Folder}-poster.png``) is detected."""
    _touch(tmp_path, "Amelie (2001)-poster.png")
    status = artwork_status(tmp_path, "movie")
    assert status.poster is True
    assert status.poster_name == "Amelie (2001)-poster.png"


def test_kodi_folder_jpg_counts_as_poster(tmp_path: Path) -> None:
    """The Kodi ``folder.jpg`` spelling counts as a poster (not just ``poster.jpg``)."""
    _touch(tmp_path, "folder.jpg")
    status = artwork_status(tmp_path, "movie")
    assert status.poster is True
    assert status.poster_name == "folder.jpg"
    # Wrapper parity: has_poster agrees with artwork_status on folder.jpg.
    assert has_poster(tmp_path) is True


def test_jpeg_and_case_insensitive(tmp_path: Path) -> None:
    """``.jpeg`` and upper-case spellings are detected (case-insensitive)."""
    _touch(tmp_path, "POSTER.JPEG", "Fanart.PNG")
    status = artwork_status(tmp_path)
    assert status.poster is True
    assert status.fanart is True


def test_tvshow_show_poster_and_season_poster(tmp_path: Path) -> None:
    """TV show root poster is detected; a season poster does NOT count as item poster."""
    # A show root with only a season poster and no item-level poster: season
    # artwork must be excluded, so poster stays False.
    _touch(tmp_path, "season01-poster.jpg", "landscape.jpg")
    status = artwork_status(tmp_path, "tvshow")
    assert status.poster is False, "season poster must not satisfy the item-level poster"
    assert status.landscape is True

    # Add the real show poster — now it is detected.
    _touch(tmp_path, "poster.jpg")
    status = artwork_status(tmp_path, "tvshow")
    assert status.poster is True
    assert status.poster_name == "poster.jpg"


def test_absent_artwork(tmp_path: Path) -> None:
    """A folder with only a video file reports no artwork (all False / None)."""
    _touch(tmp_path, "movie.mkv", "movie.nfo")
    status = artwork_status(tmp_path, "movie")
    assert status == ArtworkStatus(poster=False, fanart=False, landscape=False)
    assert status.poster_name is None


def test_unreadable_directory_fail_soft(tmp_path: Path) -> None:
    """A non-existent directory fails soft (all False), never raising."""
    status = artwork_status(tmp_path / "does-not-exist", "movie")
    assert status.poster is False
    assert status.fanart is False
    assert status.landscape is False


def test_wrappers_agree_with_status(tmp_path: Path) -> None:
    """``artwork_flags`` / ``has_poster`` recognize the SAME spellings as ``artwork_status``."""
    _touch(tmp_path, "Show (2010)-poster.png", "fanart.jpg")
    flags = artwork_flags(tmp_path)
    status = artwork_status(tmp_path, "tvshow")
    assert flags["poster"] == status.poster is True
    assert flags["fanart"] == status.fanart is True
    assert has_poster(tmp_path) == status.poster is True
