"""Tests for the media index module.

V15 P6.4: IndexEntry.category and .disk store V15 IDs. MediaIndex requires
an explicit index_path (settings.data_dir default removed in P6.1).
Auto-migration from V14 FR labels tested via regression test.
"""

import json
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
        idx.add(
            IndexEntry(
                name="The Matrix (1999)",
                disk="drive_a",
                category="movies",
                path="/drive_a/movies/The Matrix (1999)",
                media_type="movie",
            )
        )
        result = idx.find("The Matrix (1999)", "movie")
        assert result is not None
        assert result.disk == "drive_a"

    def test_find_case_insensitive(self, tmp_path: Path) -> None:
        """Should find entries regardless of case."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(
            IndexEntry(
                name="The Matrix (1999)",
                disk="drive_a",
                category="movies",
                path="/drive_a/movies/The Matrix (1999)",
                media_type="movie",
            )
        )
        result = idx.find("the matrix (1999)", "movie")
        assert result is not None

    def test_find_wrong_type_returns_none(self, tmp_path: Path) -> None:
        """Should not match if media_type differs."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(
            IndexEntry(
                name="Test",
                disk="drive_a",
                category="movies",
                path="/drive_a/movies/Test",
                media_type="movie",
            )
        )
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
        idx.add(
            IndexEntry(
                name="Test",
                disk="drive_a",
                category="movies",
                path="/drive_a/movies/Test",
                media_type="movie",
            )
        )
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
        idx.add(
            IndexEntry(
                name="Test",
                disk="drive_a",
                category="movies",
                path="/drive_a/movies/Test",
                media_type="movie",
            )
        )
        idx.save()
        assert (tmp_path / "index.json").exists()
        assert not (tmp_path / "index.json.tmp").exists()

    def test_save_always_v15_format(self, tmp_path: Path) -> None:
        """Saved entries must use V15 IDs (not V14 labels)."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(
            IndexEntry(
                name="Inception (2010)",
                disk="disk_1",
                category="movies",
                path="/disk_1/movies/Inception (2010)",
                media_type="movie",
            )
        )
        idx.save()

        raw = json.loads((tmp_path / "index.json").read_text())
        entry = next(iter(raw.values()))
        # V15 IDs — not V14 labels
        assert entry["category"] == "movies"
        assert entry["disk"] == "disk_1"


# ---------------------------------------------------------------------------
# V14 → V15 auto-migration
# ---------------------------------------------------------------------------


class TestV14Migration:
    """Regression tests: load V14-format index → entries have V15 IDs."""

    def _write_v14_index(self, path: Path) -> None:
        """Write a synthetic V14 format index to disk."""
        v14_data = {
            "the matrix (1999)": {
                "name": "The Matrix (1999)",
                "disk": "Disk1",
                "category": "films",
                "path": "/Volumes/Disk1/medias/films/The Matrix (1999)",
                "media_type": "movie",
                "last_updated": "2024-01-01T00:00:00+00:00",
            },
            "fallout (2024)": {
                "name": "Fallout (2024)",
                "disk": "Disk2",
                "category": "series",
                "path": "/Volumes/Disk2/medias/series/Fallout (2024)",
                "media_type": "tvshow",
                "last_updated": "2024-01-01T00:00:00+00:00",
            },
            "demon slayer (2019)": {
                "name": "Demon Slayer (2019)",
                "disk": "Disk2",
                "category": "series animes",
                "path": "/Volumes/Disk2/medias/series animes/Demon Slayer (2019)",
                "media_type": "tvshow",
                "last_updated": "2024-01-01T00:00:00+00:00",
            },
        }
        path.write_text(json.dumps(v14_data, indent=2, ensure_ascii=False), encoding="utf-8")

    def test_v14_categories_migrated_to_ids(self, tmp_path: Path) -> None:
        """V14 category labels should be converted to V15 IDs on load."""
        idx_path = tmp_path / "index.json"
        self._write_v14_index(idx_path)

        idx = MediaIndex(idx_path)
        idx.load()

        assert idx.count == 3

        matrix = idx.find("The Matrix (1999)", "movie")
        assert matrix is not None
        assert matrix.category == "movies"  # "films" → "movies"

        fallout = idx.find("Fallout (2024)", "tvshow")
        assert fallout is not None
        assert fallout.category == "tv_shows"  # "series" → "tv_shows"

        slayer = idx.find("Demon Slayer (2019)", "tvshow")
        assert slayer is not None
        assert slayer.category == "anime"  # "series animes" → "anime"

    def test_v14_disk_names_migrated_to_ids(self, tmp_path: Path) -> None:
        """V14 disk names (Disk1..Disk4) should be converted to disk IDs."""
        idx_path = tmp_path / "index.json"
        self._write_v14_index(idx_path)

        idx = MediaIndex(idx_path)
        idx.load()

        matrix = idx.find("The Matrix (1999)", "movie")
        assert matrix is not None
        assert matrix.disk == "disk_1"  # "Disk1" → "disk_1"

        fallout = idx.find("Fallout (2024)", "tvshow")
        assert fallout is not None
        assert fallout.disk == "disk_2"  # "Disk2" → "disk_2"

    def test_v15_format_passthrough(self, tmp_path: Path) -> None:
        """V15-format index (IDs) should load without modification."""
        v15_data = {
            "inception (2010)": {
                "name": "Inception (2010)",
                "disk": "drive_a",
                "category": "movies",
                "path": "/drive_a/movies/Inception (2010)",
                "media_type": "movie",
                "last_updated": "2024-01-01T00:00:00+00:00",
            }
        }
        idx_path = tmp_path / "index.json"
        idx_path.write_text(json.dumps(v15_data), encoding="utf-8")

        idx = MediaIndex(idx_path)
        idx.load()

        entry = idx.find("Inception (2010)", "movie")
        assert entry is not None
        assert entry.category == "movies"
        assert entry.disk == "drive_a"

    def test_save_after_v14_load_writes_v15(self, tmp_path: Path) -> None:
        """After loading V14 data, save() must write V15 IDs to disk."""
        idx_path = tmp_path / "index.json"
        self._write_v14_index(idx_path)

        idx = MediaIndex(idx_path)
        idx.load()
        idx.save()

        raw = json.loads(idx_path.read_text())
        for entry_data in raw.values():
            # No V14 labels should remain after save
            assert entry_data["category"] not in {
                "films",
                "series",
                "series animes",
                "films animations",
                "emissions",
            }
            # No V14 disk names (Disk1..Disk4) should remain
            assert entry_data["disk"] not in {"Disk1", "Disk2", "Disk3", "Disk4"}


# ---------------------------------------------------------------------------
# Rebuild
# ---------------------------------------------------------------------------


class TestMediaIndexRebuild:
    """Tests for rebuild from disk scan."""

    def test_rebuild_indexes_media(self, tmp_path: Path) -> None:
        """Should index media directories from disk structure."""
        from personalscraper.conf.models import DiskConfig

        # Create fake disk structure using V15 category IDs as folder names
        disk = tmp_path / "medias"
        (disk / "movies" / "The Matrix (1999)").mkdir(parents=True)
        (disk / "movies" / "Inception (2010)").mkdir(parents=True)
        (disk / "tv_shows" / "Fallout (2024)").mkdir(parents=True)

        config = DiskConfig(
            id="drive_a",
            path=disk,
            categories=["movies", "tv_shows"],
        )

        idx = MediaIndex(tmp_path / "index.json")
        count = idx.rebuild([config])

        assert count == 3
        assert idx.find("The Matrix (1999)", "movie") is not None
        assert idx.find("Fallout (2024)", "tvshow") is not None

    def test_rebuild_uses_disk_id(self, tmp_path: Path) -> None:
        """Rebuilt entries use disk.id (V15) not disk.name (V14)."""
        from personalscraper.conf.models import DiskConfig

        disk = tmp_path / "medias"
        (disk / "movies" / "Movie A").mkdir(parents=True)

        config = DiskConfig(id="my_nas", path=disk, categories=["movies"])
        idx = MediaIndex(tmp_path / "index.json")
        idx.rebuild([config])

        entry = idx.find("Movie A", "movie")
        assert entry is not None
        assert entry.disk == "my_nas"


# ---------------------------------------------------------------------------
# Remove stale
# ---------------------------------------------------------------------------


class TestMediaIndexRemoveStale:
    """Tests for remove_stale cleanup."""

    def test_removes_nonexistent_paths(self, tmp_path: Path) -> None:
        """Should remove entries for paths that no longer exist."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(
            IndexEntry(
                name="Gone Movie",
                disk="drive_a",
                category="movies",
                path="/nonexistent/path",
                media_type="movie",
            )
        )
        idx.add(
            IndexEntry(
                name="Exists",
                disk="drive_a",
                category="movies",
                path=str(tmp_path),
                media_type="movie",
            )
        )

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
        idx.add(
            IndexEntry(
                name="The Matrix Reloaded (2003)",
                disk="drive_a",
                category="movies",
                path="/d/movies/The Matrix Reloaded (2003)",
                media_type="movie",
            )
        )

        result = idx.find("The Matrix (1999)", "movie")
        assert result is None

    def test_alien_does_not_match_aliens(self, tmp_path: Path) -> None:
        """'Alien (1979)' should NOT match 'Aliens (1986)' (year + threshold)."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(
            IndexEntry(
                name="Aliens (1986)",
                disk="drive_a",
                category="movies",
                path="/d/movies/Aliens (1986)",
                media_type="movie",
            )
        )

        result = idx.find("Alien (1979)", "movie")
        assert result is None

    def test_jumanji_matches_jumanji(self, tmp_path: Path) -> None:
        """'Jumanji (1995)' SHOULD match 'Jumanji (1995)' in the index."""
        idx = MediaIndex(tmp_path / "index.json")
        idx.add(
            IndexEntry(
                name="Jumanji (1995)",
                disk="drive_a",
                category="movies",
                path="/d/movies/Jumanji (1995)",
                media_type="movie",
            )
        )

        result = idx.find("Jumanji (1995)", "movie")
        assert result is not None
        assert result.name == "Jumanji (1995)"
