"""``_read_episode_titles``: multi-root episode NFOs and unreadable NFOs."""

from __future__ import annotations

from pathlib import Path

from personalscraper.indexer.scanner._modes._item_stage import _read_episode_titles


def _season(tmp_path: Path) -> Path:
    season = tmp_path / "Saison 01"
    season.mkdir()
    return season


def test_multi_root_nfo_indexes_each_episode_title(tmp_path: Path) -> None:
    """A span file whose NFO holds two roots yields both titles."""
    season = _season(tmp_path)
    (season / "Show - S01E01-E02 - Pilot.mkv").write_bytes(b"x")
    (season / "Show - S01E01-E02 - Pilot.nfo").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<episodedetails><title>First</title></episodedetails>\n"
        "<episodedetails><title>Second</title></episodedetails>\n"
    )
    assert _read_episode_titles(season) == {1: "First", 2: "Second"}


def test_single_root_nfo_unchanged(tmp_path: Path) -> None:
    """The usual one-root NFO keeps giving its title."""
    season = _season(tmp_path)
    (season / "Show - S01E03 - Three.mkv").write_bytes(b"x")
    (season / "Show - S01E03 - Three.nfo").write_text("<episodedetails><title>Three</title></episodedetails>")
    assert _read_episode_titles(season) == {3: "Three"}


def test_unreadable_nfo_keeps_null_title(tmp_path: Path) -> None:
    """A truncated NFO still maps to a NULL title, no exception."""
    season = _season(tmp_path)
    (season / "Show - S01E04 - Four.mkv").write_bytes(b"x")
    (season / "Show - S01E04 - Four.nfo").write_text("<episodedetails><title>Fo")
    assert _read_episode_titles(season) == {4: None}


def test_empty_nfo_keeps_null_title(tmp_path: Path) -> None:
    """A 0-byte NFO maps to a NULL title."""
    season = _season(tmp_path)
    (season / "Show - S01E05 - Five.mkv").write_bytes(b"x")
    (season / "Show - S01E05 - Five.nfo").write_bytes(b"")
    assert _read_episode_titles(season) == {5: None}
