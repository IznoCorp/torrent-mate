"""Integration tests for the full library maintenance workflow.

Tests the chain: scan -> clean -> validate -> recommend -> report.
Uses a realistic temporary filesystem with movies and TV shows.
"""

from pathlib import Path

import pytest

from personalscraper.library.models import (
    ISSUE_ACTORS_DIR,
    ISSUE_JUNK_FILES,
)

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def mini_library(tmp_path: Path):
    """Build a realistic mini-library for integration testing.

    Structure:
        Disk1/medias/
            films/
                The Matrix (1999)/
                    The Matrix.mkv (1 KB fake)
                    The Matrix.nfo (valid, TMDB ID)
                    The Matrix-poster.jpg
                    The Matrix-landscape.jpg
                    .actors/Actor.jpg
                    .DS_Store
                Incomplete Movie/
                    movie.mkv (1 KB fake, no NFO, no year in name)
            series/
                Fallout (2024)/
                    tvshow.nfo (valid)
                    poster.jpg
                    season01-poster.jpg
                    Saison 01/
                        S01E01 - The Beginning.mkv
                        S01E01 - The Beginning.nfo
                        S01E02 - The End.mkv
                    .actors/
                    empty_release_dir/  (empty)
    """
    disk = tmp_path / "Disk1" / "medias"

    # --- Movie: complete ---
    matrix = disk / "films" / "The Matrix (1999)"
    matrix.mkdir(parents=True)
    (matrix / "The Matrix.mkv").write_bytes(b"\x00" * 1000)
    (matrix / "The Matrix.nfo").write_text(
        "<movie><title>The Matrix</title><year>1999</year>"
        '<uniqueid type="tmdb">603</uniqueid>'
        '<uniqueid type="imdb">tt0133093</uniqueid></movie>'
    )
    (matrix / "The Matrix-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    (matrix / "The Matrix-landscape.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    actors = matrix / ".actors"
    actors.mkdir()
    (actors / "Keanu Reeves.jpg").write_bytes(b"\x00" * 50)
    (matrix / ".DS_Store").write_bytes(b"\x00" * 10)

    # --- Movie: incomplete (no NFO, bad naming) ---
    incomplete = disk / "films" / "Incomplete Movie"
    incomplete.mkdir(parents=True)
    (incomplete / "movie.mkv").write_bytes(b"\x00" * 1000)

    # --- TV Show ---
    fallout = disk / "series" / "Fallout (2024)"
    fallout.mkdir(parents=True)
    (fallout / "tvshow.nfo").write_text(
        '<tvshow><title>Fallout</title><uniqueid type="tmdb">106379</uniqueid></tvshow>'
    )
    (fallout / "poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    (fallout / "season01-poster.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 100)
    s01 = fallout / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - The Beginning.mkv").write_bytes(b"\x00" * 2000)
    (s01 / "S01E01 - The Beginning.nfo").write_text("<episodedetails><title>The Beginning</title></episodedetails>")
    (s01 / "S01E02 - The End.mkv").write_bytes(b"\x00" * 2000)
    show_actors = fallout / ".actors"
    show_actors.mkdir()
    (show_actors / "Ella Purnell.jpg").write_bytes(b"\x00" * 50)
    (fallout / "empty_release_dir").mkdir()

    # Build DiskConfig + Config for scan operations
    from personalscraper.conf.models.categories import CategoryConfig
    from personalscraper.conf.models.config import Config
    from personalscraper.conf.models.disks import DiskConfig
    from personalscraper.conf.models.paths import PathConfig
    from tests.fixtures.config import CANONICAL_STAGING_DIRS

    disk_cfg = DiskConfig(id="disk1", path=disk, categories=["movies", "tv_shows"])
    config = Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={
            "movies": CategoryConfig(folder_name="films"),
            "tv_shows": CategoryConfig(folder_name="series"),
        },
        staging_dirs=CANONICAL_STAGING_DIRS,
    )

    return {
        "disk": disk,
        "config": config,
        "disk_cfg": disk_cfg,
        "matrix": matrix,
        "incomplete": incomplete,
        "fallout": fallout,
    }


class TestScanIntegration:
    """Integration test for library scanning (DB-backed API)."""

    def test_scan_finds_all_items(self, mini_library) -> None:
        """stage_library_items(conn, config) -> 2 movies + 1 TV show = 3 media_item rows."""
        import sqlite3

        from personalscraper.indexer.db import apply_migrations
        from personalscraper.indexer.scanner._modes._item_stage import stage_library_items

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn, MIGRATIONS_DIR)
        stage_library_items(conn, mini_library["config"])

        count = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
        assert count == 3

        titles = {row[0] for row in conn.execute("SELECT title FROM media_item").fetchall()}
        assert "The Matrix" in titles
        assert "Incomplete Movie" in titles
        assert "Fallout" in titles

    def test_scan_detects_issues(self, mini_library) -> None:
        """stage_library_items must persist item_issue rows for .actors and junk files."""
        import sqlite3

        from personalscraper.indexer.db import apply_migrations
        from personalscraper.indexer.scanner._modes._item_stage import stage_library_items

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn, MIGRATIONS_DIR)
        stage_library_items(conn, mini_library["config"])

        # Matrix item should have actors_dir + junk_files issues
        matrix_id = conn.execute("SELECT id FROM media_item WHERE title = 'The Matrix'").fetchone()[0]
        issue_types = {
            row[0] for row in conn.execute("SELECT type FROM item_issue WHERE item_id = ?", (matrix_id,)).fetchall()
        }
        assert ISSUE_ACTORS_DIR in issue_types
        assert ISSUE_JUNK_FILES in issue_types

    def test_scan_detects_seasons(self, mini_library) -> None:
        """stage_library_items must persist season and episode rows for TV shows."""
        import sqlite3

        from personalscraper.indexer.db import apply_migrations
        from personalscraper.indexer.scanner._modes._item_stage import stage_library_items

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn, MIGRATIONS_DIR)
        stage_library_items(conn, mini_library["config"])

        fallout_id = conn.execute("SELECT id FROM media_item WHERE title = 'Fallout'").fetchone()[0]

        season_count = conn.execute("SELECT COUNT(*) FROM season WHERE item_id = ?", (fallout_id,)).fetchone()[0]
        assert season_count == 1

        season = conn.execute("SELECT number FROM season WHERE item_id = ?", (fallout_id,)).fetchone()
        assert season[0] == 1

        episode_count = conn.execute(
            "SELECT COUNT(*) FROM episode e JOIN season s ON e.season_id = s.id WHERE s.item_id = ?",
            (fallout_id,),
        ).fetchone()[0]
        assert episode_count == 2

    def test_scan_db_roundtrip(self, mini_library) -> None:
        """After stage_library_items, DB queries must return consistent item counts by kind."""
        import sqlite3

        from personalscraper.indexer.db import apply_migrations
        from personalscraper.indexer.scanner._modes._item_stage import stage_library_items

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn, MIGRATIONS_DIR)
        stage_library_items(conn, mini_library["config"])

        movie_count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'movie'").fetchone()[0]
        show_count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'show'").fetchone()[0]
        assert movie_count == 2
        assert show_count == 1


class TestCleanIntegration:
    """Integration test for library-clean."""

    def test_clean_actors_apply(self, mini_library) -> None:
        """Clean should remove .actors/ directories."""
        from personalscraper.library.disk_cleaner import clean_library

        result = clean_library(mini_library["config"], apply=True, only="actors")

        assert result.deleted_count == 2  # Matrix + Fallout .actors
        assert not (mini_library["matrix"] / ".actors").exists()
        assert not (mini_library["fallout"] / ".actors").exists()

    def test_clean_junk_apply(self, mini_library) -> None:
        """Clean should remove .DS_Store files."""
        from personalscraper.library.disk_cleaner import clean_library

        clean_library(mini_library["config"], apply=True, only="junk")

        assert not (mini_library["matrix"] / ".DS_Store").exists()

    def test_clean_dry_run_preserves(self, mini_library) -> None:
        """Dry-run should not delete anything."""
        from personalscraper.library.disk_cleaner import clean_library

        result = clean_library(mini_library["config"], apply=False)

        assert result.dry_run is True
        assert result.deleted_count > 0  # counted
        assert (mini_library["matrix"] / ".actors").exists()  # preserved
        assert (mini_library["matrix"] / ".DS_Store").exists()  # preserved


class TestRecommendIntegration:
    """Integration test for library-recommend."""

    def test_recommend_from_analysis(self) -> None:
        """Recommendations should be generated from analysis data."""
        from personalscraper.conf.models.preferences import LibraryPrefs, VideoPrefs
        from personalscraper.insights.recommender import generate_recommendations
        from personalscraper.library.models import (
            AudioTrack,
            LibraryAnalysisItem,
            MediaFileAnalysis,
            VideoInfo,
        )

        # H.264 movie at 8 GB — should trigger codec + size recommendations
        items = [
            LibraryAnalysisItem(
                path="/tmp/BigMovie (2024)",
                disk="Disk1",
                category="films",
                media_type="movie",
                title="BigMovie",
                year=2024,
                files=[
                    MediaFileAnalysis(
                        path="/tmp/BigMovie (2024)/BigMovie.mkv",
                        size_gb=8.0,
                        duration_seconds=7200,
                        video=VideoInfo(
                            codec="h264", width=1920, height=1080, bitrate_kbps=10000, hdr=False, hdr_type=None
                        ),
                        audio_tracks=[
                            AudioTrack(codec="ac3", language="fra", channels=6, is_atmos=False, is_default=True)
                        ],
                        subtitle_tracks=[],
                        audio_profile="vf",
                        subtitle_languages=[],
                        analyzed_at="2026-04-15T12:00:00",
                    )
                ],
            )
        ]

        prefs = LibraryPrefs(video=VideoPrefs(max_size_movie_gb=4.0))
        result = generate_recommendations(items, prefs)

        assert result.total_recommendations == 1
        rec = result.items[0]
        assert rec.priority in ("high", "medium")  # 8 GB = 2x4 GB boundary
        assert rec.estimated_savings_gb is not None
        assert rec.estimated_savings_gb > 0


class TestReportIntegration:
    """Integration test for library-report (DB-backed API)."""

    def test_report_from_scan_data(self, mini_library) -> None:
        """Report should aggregate data from the indexer DB after stage_library_items."""
        import sqlite3

        from personalscraper.indexer.db import apply_migrations
        from personalscraper.indexer.scanner._modes._item_stage import stage_library_items
        from personalscraper.insights.analytics import analyze
        from personalscraper.insights.reporter import generate_report

        conn = sqlite3.connect(":memory:")
        apply_migrations(conn, MIGRATIONS_DIR)
        stage_library_items(conn, mini_library["config"])

        analysis_result = analyze(conn)
        report = generate_report(analysis_result=analysis_result)

        assert report.total_items == 3
        # All items are on disk1
        assert report.items_per_disk.get("disk1", 0) == 3


class TestFullWorkflow:
    """Test the full scan -> clean -> rescan chain (rewritten for v7.2)."""

    def test_clean_then_rescan_shows_fewer_issues(self, mini_library) -> None:
        """After cleaning .actors and junk, rescan must drop those item_issue rows."""
        import sqlite3

        from personalscraper.indexer.db import apply_migrations
        from personalscraper.indexer.scanner._modes._item_stage import stage_library_items
        from personalscraper.library.disk_cleaner import clean_library

        # Use a file DB so it survives between scan calls.
        db_path = mini_library["config"].paths.data_dir / "library.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        stage_library_items(conn, mini_library["config"])

        # Matrix must have issues after first scan
        matrix_id = conn.execute("SELECT id FROM media_item WHERE title = 'The Matrix'").fetchone()[0]
        initial_issues = conn.execute("SELECT COUNT(*) FROM item_issue WHERE item_id = ?", (matrix_id,)).fetchone()[0]
        assert initial_issues >= 2  # .actors + .DS_Store

        # Clean both .actors and junk
        clean_library(mini_library["config"], apply=True)

        # Rescan — issues for Matrix should be gone
        stage_library_items(conn, mini_library["config"])

        remaining = conn.execute("SELECT COUNT(*) FROM item_issue WHERE item_id = ?", (matrix_id,)).fetchone()[0]
        assert remaining < initial_issues
        issue_types = {
            row[0] for row in conn.execute("SELECT type FROM item_issue WHERE item_id = ?", (matrix_id,)).fetchall()
        }
        assert ISSUE_ACTORS_DIR not in issue_types
        assert ISSUE_JUNK_FILES not in issue_types
