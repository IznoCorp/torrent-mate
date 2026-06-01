"""Tests for personalscraper.indexer.scanner._modes._item_stage_types — scan-stage dataclasses."""

from personalscraper.indexer.scanner._modes._item_stage_types import (
    ISSUE_ACTORS_DIR,
    ISSUE_EMPTY_SUBDIR,
    ArtworkStatus,
    LibraryScanItem,
    NfoStatus,
    SeasonInfo,
)


class TestNfoStatus:
    """Tests for NfoStatus invariant enforcement."""

    def test_present_and_valid(self) -> None:
        """Valid NFO with IDs should store all fields."""
        nfo = NfoStatus(present=True, valid=True, tmdb_id="12345", imdb_id="tt999")
        assert nfo.present is True
        assert nfo.valid is True
        assert nfo.tmdb_id == "12345"
        assert nfo.imdb_id == "tt999"

    def test_absent_forces_invalid_and_no_ids(self) -> None:
        """Absent NFO must force valid=False and clear IDs."""
        nfo = NfoStatus(present=False, valid=True, tmdb_id="12345", imdb_id="tt999")
        assert nfo.present is False
        assert nfo.valid is False
        assert nfo.tmdb_id is None
        assert nfo.imdb_id is None

    def test_present_but_invalid(self) -> None:
        """Present but invalid NFO (corrupt XML) should clear IDs."""
        nfo = NfoStatus(present=True, valid=False, tmdb_id=None, imdb_id=None)
        assert nfo.present is True
        assert nfo.valid is False


class TestArtworkStatus:
    """Tests for ArtworkStatus defaults."""

    def test_all_false_by_default(self) -> None:
        """All artwork types default to False (not present)."""
        art = ArtworkStatus()
        assert art.poster is False
        assert art.fanart is False
        assert art.landscape is False
        assert art.banner is False
        assert art.clearlogo is False
        assert art.clearart is False
        assert art.discart is False
        assert art.characterart is False


class TestSeasonInfo:
    """Tests for SeasonInfo."""

    def test_basic_season(self) -> None:
        """Season with basic info."""
        s = SeasonInfo(number=1, path="/tmp/Saison 01", episode_count=8, has_poster=True, episodes_with_nfo=6)
        assert s.number == 1
        assert s.episode_count == 8
        assert s.episodes_with_nfo == 6


class TestLibraryScanItem:
    """Tests for LibraryScanItem."""

    def test_movie_has_no_seasons(self) -> None:
        """Movie scan item should have seasons=None."""
        item = LibraryScanItem(
            path="/Volumes/Disk1/medias/films/Movie (2024)",
            disk="Disk1",
            category="films",
            media_type="movie",
            title="Movie",
            year=2024,
            folder_size_gb=2.5,
            nfo=NfoStatus(present=True, valid=True, tmdb_id="1", imdb_id=None),
            artwork=ArtworkStatus(poster=True, landscape=True),
            actors_dir=False,
            issues=[],
            seasons=None,
            scanned_at="2026-04-15T12:00:00",
        )
        assert item.seasons is None
        assert item.media_type == "movie"

    def test_tvshow_with_seasons(self) -> None:
        """TV show scan item should have populated seasons list."""
        item = LibraryScanItem(
            path="/Volumes/Disk1/medias/series/Show (2024)",
            disk="Disk1",
            category="series",
            media_type="tvshow",
            title="Show",
            year=2024,
            folder_size_gb=15.0,
            nfo=NfoStatus(present=True, valid=True, tmdb_id="1", imdb_id=None),
            artwork=ArtworkStatus(poster=True),
            actors_dir=True,
            issues=[ISSUE_ACTORS_DIR, ISSUE_EMPTY_SUBDIR],
            seasons=[
                SeasonInfo(number=1, path="/tmp/Saison 01", episode_count=10, has_poster=True, episodes_with_nfo=10)
            ],
            scanned_at="2026-04-15T12:00:00",
        )
        assert item.seasons is not None and len(item.seasons) == 1
        assert ISSUE_ACTORS_DIR in item.issues
