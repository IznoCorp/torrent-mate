"""Tests for the Plex match-hint writer (scraper/plexmatch.py)."""

from pathlib import Path

import pytest

from personalscraper.scraper.plexmatch import PLEXMATCH_FILENAME, _content, write_plexmatch


def test_content_format_follows_plex_doc() -> None:
    """Directives are one ``hint: value`` per line; tvdbid overrides title."""
    body = _content("Les Groos", 478476)
    assert body == "title: Les Groos\ntvdbid: 478476\n"


def test_write_creates_file_next_to_nfo(tmp_path: Path) -> None:
    """The file lands in the show directory with the exact Plex name."""
    show_dir = tmp_path / "Les Groos (2022)"
    show_dir.mkdir()
    assert write_plexmatch(show_dir, title="Les Groos", tvdb_id=478476, dry_run=False) is True
    written = (show_dir / PLEXMATCH_FILENAME).read_text(encoding="utf-8")
    assert written == "title: Les Groos\ntvdbid: 478476\n"


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
