"""Tests for the media index module.

IndexEntry.category and .disk always store canonical IDs. MediaIndex
requires an explicit index_path (no implicit default).
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

    def test_find_nfc_matches_nfd_entry(self, tmp_path: Path) -> None:
        """NFC query must match NFD-stored entry (cross-filesystem hazard).

        Staging (APFS) stores precomposed ``è`` (U+00E8) while NTFS disks
        keep the decomposed form (``e`` + U+0300). Without NFC normalization
        in _normalize_key, the same show would map to two distinct index
        keys, breaking exact lookup after a merge.
        """
        idx = MediaIndex(tmp_path / "index.json")
        nfd_name = "Top Chef Le Concours Paralle\u0300le (2026)"
        nfc_name = "Top Chef Le Concours Parall\u00e8le (2026)"
        assert nfd_name != nfc_name
        idx.add(
            IndexEntry(
                name=nfd_name,
                disk="disk_1",
                category="tv_programs",
                path=f"/disk_1/emissions/{nfd_name}",
                media_type="tvshow",
            )
        )
        result = idx.find(nfc_name, "tvshow")
        assert result is not None
        assert result.disk == "disk_1"

    def test_add_nfc_after_nfd_does_not_create_duplicate_key(self, tmp_path: Path) -> None:
        """Adding the NFC form of an NFD-keyed entry must update, not duplicate."""
        idx = MediaIndex(tmp_path / "index.json")
        nfd_name = "Acharne\u0301s (2023)"
        nfc_name = "Acharn\u00e9s (2023)"
        idx.add(
            IndexEntry(
                name=nfd_name,
                disk="disk_1",
                category="tv_shows",
                path=f"/disk_1/series/{nfd_name}",
                media_type="tvshow",
            )
        )
        idx.add(
            IndexEntry(
                name=nfc_name,
                disk="disk_2",
                category="tv_shows",
                path=f"/disk_2/series/{nfc_name}",
                media_type="tvshow",
            )
        )
        # Only one entry should exist after both adds (NFC normalization collapses keys)
        assert len(idx._entries) == 1
        result = idx.find(nfc_name, "tvshow")
        assert result is not None
        assert result.disk == "disk_2"


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
# Canonical-ID passthrough
# ---------------------------------------------------------------------------


class TestCanonicalIdLoad:
    """Loading an index already written with canonical IDs is a no-op."""

    def test_canonical_ids_loaded_verbatim(self, tmp_path: Path) -> None:
        data = {
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
        idx_path.write_text(json.dumps(data), encoding="utf-8")

        idx = MediaIndex(idx_path)
        idx.load()

        entry = idx.find("Inception (2010)", "movie")
        assert entry is not None
        assert entry.category == "movies"
        assert entry.disk == "drive_a"


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

    def test_rebuild_resolves_folder_name_to_category_id(self, tmp_path: Path) -> None:
        """Should resolve on-disk folder_name → V15 category_id via ``categories`` map.

        Production disks use French folder names (``series``, ``films``,
        ``emissions``) while V15 category IDs are English (``tv_shows``,
        ``movies``, ``tv_programs``). Without the reverse lookup, rebuild
        silently skipped every folder whose name was not already a V15 ID.
        """
        from personalscraper.conf.models import CategoryConfig, DiskConfig

        disk = tmp_path / "medias"
        (disk / "series" / "Fallout (2024)").mkdir(parents=True)
        (disk / "emissions" / "Top Chef (France) (2010)").mkdir(parents=True)
        (disk / "films" / "The Matrix (1999)").mkdir(parents=True)

        config = DiskConfig(
            id="drive_a",
            path=disk,
            categories=["tv_shows", "tv_programs", "movies"],
        )
        categories = {
            "tv_shows": CategoryConfig(folder_name="series"),
            "tv_programs": CategoryConfig(folder_name="emissions"),
            "movies": CategoryConfig(folder_name="films"),
        }

        idx = MediaIndex(tmp_path / "index.json")
        count = idx.rebuild([config], categories=categories)

        assert count == 3

        fallout = idx.find("Fallout (2024)", "tvshow")
        assert fallout is not None
        assert fallout.category == "tv_shows"
        assert fallout.disk == "drive_a"

        topchef = idx.find("Top Chef (France) (2010)", "tvshow")
        assert topchef is not None
        assert topchef.category == "tv_programs"

        matrix = idx.find("The Matrix (1999)", "movie")
        assert matrix is not None
        assert matrix.category == "movies"

    def test_rebuild_without_categories_falls_back_to_legacy(self, tmp_path: Path) -> None:
        """When no ``categories`` provided, rebuild keeps legacy behaviour.

        Folder name must equal category ID (backward compat with existing
        tests that pre-date the folder_name remapping).
        """
        from personalscraper.conf.models import DiskConfig

        disk = tmp_path / "medias"
        (disk / "movies" / "Movie A").mkdir(parents=True)
        (disk / "series" / "Show B").mkdir(parents=True)  # Will be skipped — no mapping

        config = DiskConfig(id="drive_a", path=disk, categories=["movies", "tv_shows"])
        idx = MediaIndex(tmp_path / "index.json")
        count = idx.rebuild([config])  # no categories kwarg

        assert count == 1  # Only "movies" dir matched (folder_name == category_id)
        assert idx.find("Movie A", "movie") is not None
        assert idx.find("Show B", "tvshow") is None


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
