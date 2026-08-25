"""Tests for the Plex match-hint writer (scraper/plexmatch.py)."""

from pathlib import Path

import pytest

from personalscraper.scraper.plexmatch import PLEXMATCH_FILENAME, _content, write_plexmatch


def test_content_show_carries_tvdbid() -> None:
    """A series hint is ``title:`` + ``tvdbid:`` — the id overrides the title."""
    body = _content("Les Groos", tvdb_id=478476, tmdb_id=None)
    assert body == "title: Les Groos\ntvdbid: 478476\n"


def test_content_movie_carries_tmdbid() -> None:
    """A movie hint is ``title:`` + ``tmdbid:`` — never a tvdbid."""
    body = _content("The Gentlemen", tvdb_id=None, tmdb_id=522627)
    assert body == "title: The Gentlemen\ntmdbid: 522627\n"


def test_write_show_creates_file_next_to_nfo(tmp_path: Path) -> None:
    """The file lands in the show directory with the exact Plex name."""
    show_dir = tmp_path / "Les Groos (2022)"
    show_dir.mkdir()
    assert write_plexmatch(show_dir, title="Les Groos", tvdb_id=478476, dry_run=False) is True
    written = (show_dir / PLEXMATCH_FILENAME).read_text(encoding="utf-8")
    assert written == "title: Les Groos\ntvdbid: 478476\n"


def test_write_movie_creates_file_next_to_nfo(tmp_path: Path) -> None:
    """A movie gets the same sidecar, carrying its TMDB id instead."""
    movie_dir = tmp_path / "The Gentlemen (2020)"
    movie_dir.mkdir()
    assert write_plexmatch(movie_dir, title="The Gentlemen", tmdb_id=522627, dry_run=False) is True
    written = (movie_dir / PLEXMATCH_FILENAME).read_text(encoding="utf-8")
    assert written == "title: The Gentlemen\ntmdbid: 522627\n"


def test_exactly_one_provider_id_enforced(tmp_path: Path) -> None:
    """Neither id, or both ids, is refused — the file must state ONE identity."""
    d = tmp_path / "Show (2020)"
    d.mkdir()
    with pytest.raises(ValueError):
        write_plexmatch(d, title="Show", dry_run=False)
    with pytest.raises(ValueError):
        write_plexmatch(d, title="Show", tvdb_id=1, tmdb_id=2, dry_run=False)


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    """Dry-run reports the intent and touches nothing on disk."""
    show_dir = tmp_path / "Les Groos (2022)"
    show_dir.mkdir()
    assert write_plexmatch(show_dir, title="Les Groos", tvdb_id=478476, dry_run=True) is True
    assert not (show_dir / PLEXMATCH_FILENAME).exists()


def test_oserror_fails_soft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed write must never fail the scrape — it returns False."""
    show_dir = tmp_path / "Les Groos (2022)"
    show_dir.mkdir()

    def _boom(self, content: str, encoding: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _boom)
    assert write_plexmatch(show_dir, title="Les Groos", tvdb_id=478476, dry_run=False) is False
    assert not (show_dir / PLEXMATCH_FILENAME).exists()
