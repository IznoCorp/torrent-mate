"""Build the v0.7 parity fixture filesystem deterministically.

Creates ~30 media items spanning movies, TV shows with seasons, and audiobooks
under ``tests/fixtures/parity/v0.7-fs/``.  The layout mirrors what the real
media library looks like on disk so that ``library-scan`` and
``MediaIndex.rebuild()`` produce representative output.

Directory structure created::

    v0.7-fs/
        disk_fixture/
            films/                         # movies (folder_name for "movies")
                Inception (2010)/
                    Inception.nfo
                    Inception-poster.jpg
                    Inception-fanart.jpg
                    Inception.mkv          # zero-byte placeholder
                ...
            series/                        # tv_shows
                Breaking Bad (2008)/
                    tvshow.nfo
                    poster.jpg
                    fanart.jpg
                    Saison 01/
                        S01E01.mkv
                        ...
                ...
            livres audios/                 # audiobooks
                Dune - Frank Herbert/
                    Dune.mp3
                ...

Usage::

    python tests/fixtures/parity/build_v07_fs.py

The script is idempotent: running it twice produces the same tree.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# All paths are relative to the repository root (two levels up from this file).
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent.parent
_OUTPUT_DIR = _SCRIPT_DIR / "v0.7-fs" / "disk_fixture"

# Pinned seed for deterministic output across runs and machines.
_SEED = 42

# Minimal NFO templates — real XML so nfo_utils.is_nfo_complete() returns True.
_MOVIE_NFO_TMPL = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>{title}</title>
  <year>{year}</year>
  <uniqueid type="tmdb">{tmdb_id}</uniqueid>
  <uniqueid type="imdb">tt{imdb_id}</uniqueid>
</movie>
"""

_TVSHOW_NFO_TMPL = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
  <title>{title}</title>
  <year>{year}</year>
  <uniqueid type="tmdb">{tmdb_id}</uniqueid>
  <uniqueid type="imdb">tt{imdb_id}</uniqueid>
</tvshow>
"""

# 1×1 white JPEG – small but valid enough for artwork presence checks.
_TINY_JPEG = bytes(
    [
        0xFF,
        0xD8,
        0xFF,
        0xE0,
        0x00,
        0x10,
        0x4A,
        0x46,
        0x49,
        0x46,
        0x00,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x00,
        0x01,
        0x00,
        0x00,
        0xFF,
        0xDB,
        0x00,
        0x43,
        0x00,
        0x08,
        0x06,
        0x06,
        0x07,
        0x06,
        0x05,
        0x08,
        0x07,
        0x07,
        0x07,
        0x09,
        0x09,
        0x08,
        0x0A,
        0x0C,
        0x14,
        0x0D,
        0x0C,
        0x0B,
        0x0B,
        0x0C,
        0x19,
        0x12,
        0x13,
        0x0F,
        0x14,
        0x1D,
        0x1A,
        0x1F,
        0x1E,
        0x1D,
        0x1A,
        0x1C,
        0x1C,
        0x20,
        0x24,
        0x2E,
        0x27,
        0x20,
        0x22,
        0x2C,
        0x23,
        0x1C,
        0x1C,
        0x28,
        0x37,
        0x29,
        0x2C,
        0x30,
        0x31,
        0x34,
        0x34,
        0x34,
        0x1F,
        0x27,
        0x39,
        0x3D,
        0x38,
        0x32,
        0x3C,
        0x2E,
        0x33,
        0x34,
        0x32,
        0xFF,
        0xC0,
        0x00,
        0x0B,
        0x08,
        0x00,
        0x01,
        0x00,
        0x01,
        0x01,
        0x01,
        0x11,
        0x00,
        0xFF,
        0xC4,
        0x00,
        0x1F,
        0x00,
        0x00,
        0x01,
        0x05,
        0x01,
        0x01,
        0x01,
        0x01,
        0x01,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x01,
        0x02,
        0x03,
        0x04,
        0x05,
        0x06,
        0x07,
        0x08,
        0x09,
        0x0A,
        0x0B,
        0xFF,
        0xC4,
        0x00,
        0xB5,
        0x10,
        0x00,
        0x02,
        0x01,
        0x03,
        0x03,
        0x02,
        0x04,
        0x03,
        0x05,
        0x05,
        0x04,
        0x04,
        0x00,
        0x00,
        0x01,
        0x7D,
        0x01,
        0x02,
        0x03,
        0x00,
        0x04,
        0x11,
        0x05,
        0x12,
        0x21,
        0x31,
        0x41,
        0x06,
        0x13,
        0x51,
        0x61,
        0x07,
        0x22,
        0x71,
        0x14,
        0x32,
        0x81,
        0x91,
        0xA1,
        0x08,
        0x23,
        0x42,
        0xB1,
        0xC1,
        0x15,
        0x52,
        0xD1,
        0xF0,
        0x24,
        0x33,
        0x62,
        0x72,
        0x82,
        0x09,
        0x0A,
        0x16,
        0x17,
        0x18,
        0x19,
        0x1A,
        0x25,
        0x26,
        0x27,
        0x28,
        0x29,
        0x2A,
        0x34,
        0x35,
        0x36,
        0x37,
        0x38,
        0x39,
        0x3A,
        0x43,
        0x44,
        0x45,
        0x46,
        0x47,
        0x48,
        0x49,
        0x4A,
        0x53,
        0x54,
        0x55,
        0x56,
        0x57,
        0x58,
        0x59,
        0x5A,
        0x63,
        0x64,
        0x65,
        0x66,
        0x67,
        0x68,
        0x69,
        0x6A,
        0x73,
        0x74,
        0x75,
        0x76,
        0x77,
        0x78,
        0x79,
        0x7A,
        0x83,
        0x84,
        0x85,
        0x86,
        0x87,
        0x88,
        0x89,
        0x8A,
        0x93,
        0x94,
        0x95,
        0x96,
        0x97,
        0x98,
        0x99,
        0x9A,
        0xA2,
        0xA3,
        0xA4,
        0xA5,
        0xA6,
        0xA7,
        0xA8,
        0xA9,
        0xAA,
        0xB2,
        0xB3,
        0xB4,
        0xB5,
        0xB6,
        0xB7,
        0xB8,
        0xB9,
        0xBA,
        0xC2,
        0xC3,
        0xC4,
        0xC5,
        0xC6,
        0xC7,
        0xC8,
        0xC9,
        0xCA,
        0xD2,
        0xD3,
        0xD4,
        0xD5,
        0xD6,
        0xD7,
        0xD8,
        0xD9,
        0xDA,
        0xE1,
        0xE2,
        0xE3,
        0xE4,
        0xE5,
        0xE6,
        0xE7,
        0xE8,
        0xE9,
        0xEA,
        0xF1,
        0xF2,
        0xF3,
        0xF4,
        0xF5,
        0xF6,
        0xF7,
        0xF8,
        0xF9,
        0xFA,
        0xFF,
        0xDA,
        0x00,
        0x08,
        0x01,
        0x01,
        0x00,
        0x00,
        0x3F,
        0x00,
        0xFB,
        0xD2,
        0x8A,
        0x28,
        0x03,
        0xFF,
        0xD9,
    ]
)

# ---------------------------------------------------------------------------
# Item specs
# ---------------------------------------------------------------------------

# Movies: (folder_name, tmdb_id_int, imdb_id_suffix_int)
_MOVIES: list[tuple[str, int, int]] = [
    ("Inception (2010)", 27205, 1375666),
    ("The Dark Knight (2008)", 155, 468569),
    ("Interstellar (2014)", 157336, 816692),
    ("Parasite (2019)", 496243, 7286456),
    ("The Godfather (1972)", 238, 68646),
    ("Fight Club (1999)", 550, 137523),
    ("Pulp Fiction (1994)", 680, 110912),
    ("The Matrix (1999)", 603, 133093),
    ("Schindler's List (1993)", 424, 108052),
    ("Goodfellas (1990)", 769, 99685),
]

# TV shows: (folder_name, seasons_count, episodes_per_season, tmdb_id, imdb_id_suffix)
_TV_SHOWS: list[tuple[str, int, int, int, int]] = [
    ("Breaking Bad (2008)", 5, 3, 1396, 903747),
    ("Game of Thrones (2011)", 8, 2, 1399, 944947),
    ("The Wire (2002)", 5, 2, 1438, 306414),
    ("Chernobyl (2019)", 1, 5, 87108, 9174558),
    ("Succession (2018)", 4, 3, 73586, 7660850),
    ("Stranger Things (2016)", 4, 2, 66732, 4574334),
    ("True Detective (2014)", 3, 3, 46648, 2356777),
    ("Ozark (2017)", 4, 2, 69737, 5720236),
    ("Peaky Blinders (2013)", 6, 2, 60574, 2442560),
    ("Better Call Saul (2015)", 6, 2, 60059, 3032476),
]

# Audiobooks: (folder_name,) — no year in folder name (scanner skips bad_dir_name for audiobooks)
_AUDIOBOOKS: list[tuple[str]] = [
    ("Dune - Frank Herbert",),
    ("Foundation - Isaac Asimov",),
    ("1984 - George Orwell",),
    ("The Lord of the Rings - J.R.R. Tolkien",),
    ("Neuromancer - William Gibson",),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_bytes(path: Path, data: bytes) -> None:
    """Write raw bytes to a file, creating parent directories as needed.

    Args:
        path: Destination file path.
        data: Bytes to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _touch(path: Path) -> None:
    """Create a zero-byte placeholder file, creating parent dirs as needed.

    Args:
        path: File path to touch.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def _write_text(path: Path, text: str) -> None:
    """Write a UTF-8 text file, creating parent dirs as needed.

    Args:
        path: Destination file path.
        text: Text content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Category builders
# ---------------------------------------------------------------------------


def _build_movie(base: Path, folder: str, tmdb_id: int, imdb_suffix: int) -> None:
    """Build a single movie directory with NFO and artwork stubs.

    Args:
        base: Parent category directory (e.g. ``films/``).
        folder: Directory name (e.g. ``Inception (2010)``).
        tmdb_id: TMDB numeric ID embedded in the NFO.
        imdb_suffix: Numeric suffix for the IMDB tt-ID embedded in the NFO.
    """
    movie_dir = base / folder
    movie_dir.mkdir(parents=True, exist_ok=True)

    # Title = folder name without the year suffix.
    title = folder.rsplit(" (", 1)[0]
    year = folder.rsplit("(", 1)[-1].rstrip(")")

    # Real NFO file so is_nfo_complete() returns True.
    nfo_text = _MOVIE_NFO_TMPL.format(
        title=title,
        year=year,
        tmdb_id=tmdb_id,
        imdb_id=f"{imdb_suffix:07d}",
    )
    _write_text(movie_dir / f"{title}.nfo", nfo_text)

    # Real (tiny) JPEG so artwork presence flags are True.
    _write_bytes(movie_dir / f"{title}-poster.jpg", _TINY_JPEG)
    _write_bytes(movie_dir / f"{title}-fanart.jpg", _TINY_JPEG)

    # Zero-byte video placeholder.
    _touch(movie_dir / f"{title}.mkv")


def _build_tvshow(
    base: Path,
    folder: str,
    seasons: int,
    episodes_per_season: int,
    tmdb_id: int,
    imdb_suffix: int,
) -> None:
    """Build a single TV show directory with NFO, artwork, and season subdirs.

    Args:
        base: Parent category directory (e.g. ``series/``).
        folder: Directory name (e.g. ``Breaking Bad (2008)``).
        seasons: Number of season directories to create.
        episodes_per_season: Number of zero-byte episode files per season.
        tmdb_id: TMDB numeric ID embedded in the NFO.
        imdb_suffix: Numeric suffix for the IMDB tt-ID embedded in the NFO.
    """
    show_dir = base / folder
    show_dir.mkdir(parents=True, exist_ok=True)

    title = folder.rsplit(" (", 1)[0]
    year = folder.rsplit("(", 1)[-1].rstrip(")")

    nfo_text = _TVSHOW_NFO_TMPL.format(
        title=title,
        year=year,
        tmdb_id=tmdb_id,
        imdb_id=f"{imdb_suffix:07d}",
    )
    _write_text(show_dir / "tvshow.nfo", nfo_text)
    _write_bytes(show_dir / "poster.jpg", _TINY_JPEG)
    _write_bytes(show_dir / "fanart.jpg", _TINY_JPEG)

    for s in range(1, seasons + 1):
        season_dir = show_dir / f"Saison {s:02d}"
        season_dir.mkdir(parents=True, exist_ok=True)

        # Season poster at show-dir level (scanner checks show_dir/seasonXX-poster.jpg).
        _write_bytes(show_dir / f"season{s:02d}-poster.jpg", _TINY_JPEG)

        for ep in range(1, episodes_per_season + 1):
            _touch(season_dir / f"{title} - S{s:02d}E{ep:02d}.mkv")


def _build_audiobook(base: Path, folder: str) -> None:
    """Build a single audiobook directory with a zero-byte audio placeholder.

    Args:
        base: Parent category directory (e.g. ``livres audios/``).
        folder: Directory name (e.g. ``Dune - Frank Herbert``).
    """
    ab_dir = base / folder
    ab_dir.mkdir(parents=True, exist_ok=True)
    # Zero-byte placeholder — file extension is mp3 so sorter file_type recognises it.
    _touch(ab_dir / f"{folder}.mp3")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def build(output_dir: Path | None = None) -> Path:
    """Build the v0.7 parity fixture filesystem.

    Creates all directories and files under *output_dir* (or the default
    ``tests/fixtures/parity/v0.7-fs/disk_fixture/``).  Idempotent: safe to
    call multiple times.

    Args:
        output_dir: Override the output root.  Defaults to
            ``tests/fixtures/parity/v0.7-fs/disk_fixture/`` relative to
            this script's parent directory.

    Returns:
        The ``disk_fixture`` root Path that was created.
    """
    rng = random.Random(_SEED)  # noqa: S311 — not security-sensitive
    _ = rng  # seed consumed; determinism comes from fixed specs above

    root = output_dir if output_dir is not None else _OUTPUT_DIR
    os.makedirs(root, exist_ok=True)

    films_dir = root / "films"
    series_dir = root / "series"
    audiobooks_dir = root / "livres audios"

    for folder, tmdb_id, imdb_suffix in _MOVIES:
        _build_movie(films_dir, folder, tmdb_id, imdb_suffix)

    for folder, seasons, eps, tmdb_id, imdb_suffix in _TV_SHOWS:
        _build_tvshow(series_dir, folder, seasons, eps, tmdb_id, imdb_suffix)

    for (folder,) in _AUDIOBOOKS:
        _build_audiobook(audiobooks_dir, folder)

    total_items = len(_MOVIES) + len(_TV_SHOWS) + len(_AUDIOBOOKS)
    print(f"Built {total_items} items under {root}")
    return root


if __name__ == "__main__":
    build()
