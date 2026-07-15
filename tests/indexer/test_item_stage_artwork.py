"""Regression: scanner artwork detection follows the real filename conventions.

The old checks were exact-name (``{title}-poster.jpg`` for movies, bare
``poster.jpg`` for shows): any prefix divergence (MediaElch
``{Folder (YYYY)}-poster.png``, scraper-written ``{Title}-poster.jpg`` on a
retitled item) read as « pas de poster » while the artwork sat on disk
(e2e loop 1 — 28→50 items falsely poster-less).
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.indexer.scanner._modes._item_stage import (
    _artwork_inventory_movie,
    _artwork_inventory_tvshow,
)


def test_movie_prefixed_artwork_detected(tmp_path: Path) -> None:
    """Folder-name-prefixed artwork (year + double space) counts as present."""
    movie = tmp_path / "Astérix  Le Domaine des dieux (2014)"
    movie.mkdir()
    (movie / "Astérix  Le Domaine des dieux (2014)-poster.jpg").write_bytes(b"x")
    (movie / "Astérix  Le Domaine des dieux (2014)-fanart.png").write_bytes(b"x")

    inv = _artwork_inventory_movie(movie, "Astérix Le Domaine des dieux")
    assert inv.poster is True
    assert inv.fanart is True
    assert inv.banner is False


def test_movie_kodi_folder_jpg_detected(tmp_path: Path) -> None:
    """The Kodi ``folder.jpg`` form counts as a poster."""
    movie = tmp_path / "Heat (1995)"
    movie.mkdir()
    (movie / "folder.jpg").write_bytes(b"x")
    assert _artwork_inventory_movie(movie, "Heat").poster is True


def test_show_prefixed_poster_detected_but_season_posters_excluded(tmp_path: Path) -> None:
    """A show's own prefixed poster counts; season posters alone do NOT."""
    show = tmp_path / "Silo"
    show.mkdir()
    (show / "season01-poster.jpg").write_bytes(b"x")
    assert _artwork_inventory_tvshow(show).poster is False, "season posters are per-season facts"

    (show / "Silo-poster.jpg").write_bytes(b"x")
    assert _artwork_inventory_tvshow(show).poster is True


def test_unreadable_dir_fails_soft(tmp_path: Path) -> None:
    """A missing directory yields an all-False inventory, never a crash."""
    inv = _artwork_inventory_movie(tmp_path / "does-not-exist", "X")
    assert inv.poster is False
