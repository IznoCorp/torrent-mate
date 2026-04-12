"""Tests for the media index module."""

from pathlib import Path

from personalscraper.dispatch.media_index import IndexEntry, MediaIndex

# ---------------------------------------------------------------------------
# Index CRUD
# ---------------------------------------------------------------------------

class TestMediaIndexCRUD:
    """Tests for load, save, add, find operations."""

    def test_add_and_find_exact(self, tmp_path: Path) -> None:
        """Should find entries by exact normalized name."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(IndexEntry(
            name="The Matrix (1999)", disk="Disk1",
            category="films", path="/d1/films/The Matrix (1999)",
            media_type="movie",
        ))
        result = idx.find("The Matrix (1999)", "movie")
        assert result is not None
        assert result.disk == "Disk1"

    def test_find_case_insensitive(self, tmp_path: Path) -> None:
        """Should find entries regardless of case."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(IndexEntry(
            name="The Matrix (1999)", disk="Disk1",
            category="films", path="/d1/films/The Matrix (1999)",
            media_type="movie",
        ))
        result = idx.find("the matrix (1999)", "movie")
        assert result is not None

    def test_find_wrong_type_returns_none(self, tmp_path: Path) -> None:
        """Should not match if media_type differs."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(IndexEntry(
            name="Test", disk="Disk1",
            category="films", path="/d1/films/Test",
            media_type="movie",
        ))
        assert idx.find("Test", "tvshow") is None

    def test_find_not_found(self, tmp_path: Path) -> None:
        """Should return None for unknown names."""
        idx = MediaIndex(tmp_path / "index.json")
        assert idx.find("Unknown Movie", "movie") is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestMediaIndexPersistence:
    """Tests for save and load."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Saved index should be loadable."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(IndexEntry(
            name="Test", disk="Disk1",
            category="films", path="/d1/films/Test",
            media_type="movie",
        ))
        idx.save()

        idx2 = MediaIndex(tmp_path / "index.json")
        idx2.load()
        assert idx2.count == 1
        assert idx2.find("Test", "movie") is not None

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Loading missing file should create empty index."""
        idx = MediaIndex(tmp_path / "nonexistent.json")
        idx.load()
        assert idx.count == 0

    def test_load_corrupted_file(self, tmp_path: Path) -> None:
        """Corrupted file should reset to empty index."""
        path = tmp_path / "bad.json"
        path.write_text("not json {{{")
        idx = MediaIndex(path)
        idx.load()
        assert idx.count == 0

    def test_atomic_save(self, tmp_path: Path) -> None:
        """Save should not leave .tmp files."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(IndexEntry(
            name="Test", disk="Disk1",
            category="films", path="/d1/films/Test",
            media_type="movie",
        ))
        idx.save()
        assert (tmp_path / "index.json").exists()
        assert not (tmp_path / "index.json.tmp").exists()


# ---------------------------------------------------------------------------
# Rebuild
# ---------------------------------------------------------------------------

class TestMediaIndexRebuild:
    """Tests for rebuild from disk scan."""

    def test_rebuild_indexes_media(self, tmp_path: Path) -> None:
        """Should index media directories from disk structure."""
        from personalscraper.dispatch.disk_scanner import DiskConfig

        # Create fake disk structure
        disk = tmp_path / "medias"
        (disk / "films" / "The Matrix (1999)").mkdir(parents=True)
        (disk / "films" / "Inception (2010)").mkdir(parents=True)
        (disk / "series" / "Fallout (2024)").mkdir(parents=True)

        config = DiskConfig(
            name="TestDisk",
            path=disk,
            categories=["films", "series"],
        )

        idx = MediaIndex(tmp_path / "index.json")
        count = idx.rebuild([config])

        assert count == 3
        assert idx.find("The Matrix (1999)", "movie") is not None
        assert idx.find("Fallout (2024)", "tvshow") is not None


# ---------------------------------------------------------------------------
# Remove stale
# ---------------------------------------------------------------------------

class TestMediaIndexRemoveStale:
    """Tests for remove_stale cleanup."""

    def test_removes_nonexistent_paths(self, tmp_path: Path) -> None:
        """Should remove entries for paths that no longer exist."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(IndexEntry(
            name="Gone Movie", disk="Disk1",
            category="films", path="/nonexistent/path",
            media_type="movie",
        ))
        idx.add(IndexEntry(
            name="Exists", disk="Disk1",
            category="films", path=str(tmp_path),
            media_type="movie",
        ))

        removed = idx.remove_stale([])
        assert removed == 1
        assert idx.count == 1


# ---------------------------------------------------------------------------
# Anti-false-positive fuzzy guards
# ---------------------------------------------------------------------------


class TestFuzzyGuards:
    """Test that fuzzy_match_score guards prevent false positives in find()."""

    def test_matrix_does_not_match_matrix_reloaded(self, tmp_path: Path) -> None:
        """'The Matrix' should NOT match 'The Matrix Reloaded' (length guard)."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(IndexEntry(
            name="The Matrix Reloaded (2003)", disk="Disk1",
            category="films", path="/d/films/The Matrix Reloaded (2003)",
            media_type="movie",
        ))

        result = idx.find("The Matrix (1999)", "movie")
        assert result is None

    def test_alien_does_not_match_aliens(self, tmp_path: Path) -> None:
        """'Alien (1979)' should NOT match 'Aliens (1986)' (year + threshold)."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(IndexEntry(
            name="Aliens (1986)", disk="Disk1",
            category="films", path="/d/films/Aliens (1986)",
            media_type="movie",
        ))

        result = idx.find("Alien (1979)", "movie")
        assert result is None

    def test_jumanji_matches_jumanji(self, tmp_path: Path) -> None:
        """'Jumanji (1995)' SHOULD match 'Jumanji (1995)' in the index."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(IndexEntry(
            name="Jumanji (1995)", disk="Disk1",
            category="films", path="/d/films/Jumanji (1995)",
            media_type="movie",
        ))

        result = idx.find("Jumanji (1995)", "movie")
        assert result is not None
        assert result.name == "Jumanji (1995)"
