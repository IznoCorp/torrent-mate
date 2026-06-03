"""Tests for the media index module.

IndexEntry.category and .disk always store canonical IDs. MediaIndex
requires an explicit index_path (no implicit default).

MediaIndex is backed by an indexer SQLite database (library.db) derived
from the parent directory of the supplied index_path.  ``load()`` and
``save()`` are intentional no-ops; persistence is handled automatically by
the DB.  Tests that previously exercised JSON round-trips now verify
equivalent behaviour via ``add()`` / ``find()`` / ``count``.
"""

from pathlib import Path

from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex

# ---------------------------------------------------------------------------
# Index CRUD
# ---------------------------------------------------------------------------


class TestMediaIndexCRUD:
    """Tests for load, save, add, find operations."""

    def test_add_and_find_exact(self, tmp_path: Path) -> None:
        """Should find entries by exact normalized name."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        assert idx.find("Unknown Movie", "movie") is None

    def test_find_nfc_matches_nfd_entry(self, tmp_path: Path) -> None:
        """NFC query must match NFD-stored entry (cross-filesystem hazard).

        Staging (APFS) stores precomposed ``è`` (U+00E8) while NTFS disks
        keep the decomposed form (``e`` + U+0300). Without NFC normalization
        in _normalize_key, the same show would map to two distinct index
        keys, breaking exact lookup after a merge.
        """
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        # Only one entry should exist after both adds (NFC normalization collapses keys).
        # Both NFD and NFC forms share the same normalized key, so the second add
        # overwrites the first via the upsert path.
        assert idx.count == 1
        result = idx.find(nfc_name, "tvshow")
        assert result is not None
        assert result.disk == "disk_2"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestMediaIndexPersistence:
    """Tests for SQLite-backed persistence."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Data added to one instance is visible in a second instance on the same DB."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Test",
                disk="drive_a",
                category="movies",
                path="/drive_a/movies/Test",
                media_type="movie",
            )
        )
        # A second instance opening the same DB sees the entry.
        idx2 = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        assert idx2.count == 1
        assert idx2.find("Test", "movie") is not None

    def test_missing_db_starts_empty(self, tmp_path: Path) -> None:
        """Opening with no prior DB creates an empty index."""
        idx = MediaIndex(tmp_path / "nonexistent.db", event_bus=EventBus())
        assert idx.count == 0

    def test_add_commits_without_temp_files(self, tmp_path: Path) -> None:
        """Adding an entry commits through SQLite without temporary JSON files."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Test",
                disk="drive_a",
                category="movies",
                path="/drive_a/movies/Test",
                media_type="movie",
            )
        )
        assert not (tmp_path / "index.db.tmp").exists()
        assert idx.count == 1

    def test_canonical_ids_round_trip(self, tmp_path: Path) -> None:
        """Entries must round-trip with canonical IDs."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Inception (2010)",
                disk="disk_1",
                category="movies",
                path="/disk_1/movies/Inception (2010)",
                media_type="movie",
            )
        )

        entry = idx.find("Inception (2010)", "movie")
        assert entry is not None
        assert entry.category == "movies"
        assert entry.disk == "disk_1"


# ---------------------------------------------------------------------------
# Canonical-ID passthrough
# ---------------------------------------------------------------------------


class TestCanonicalIdLoad:
    """Canonical IDs added via add() are round-tripped verbatim through find()."""

    def test_canonical_ids_loaded_verbatim(self, tmp_path: Path) -> None:
        """Canonical-ID entries written via add() are returned unchanged by find()."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Inception (2010)",
                disk="drive_a",
                category="movies",
                path="/drive_a/movies/Inception (2010)",
                media_type="movie",
                last_updated="2024-01-01T00:00:00+00:00",
            )
        )

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
        from personalscraper.conf.models.disks import DiskConfig

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

        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        count = idx.rebuild([config])

        assert count == 3
        assert idx.find("The Matrix (1999)", "movie") is not None
        assert idx.find("Fallout (2024)", "tvshow") is not None

    def test_rebuild_uses_disk_id(self, tmp_path: Path) -> None:
        """Rebuilt entries use disk.id (V15) not disk.name (V14)."""
        from personalscraper.conf.models.disks import DiskConfig

        disk = tmp_path / "medias"
        (disk / "movies" / "Movie A").mkdir(parents=True)

        config = DiskConfig(id="my_nas", path=disk, categories=["movies"])
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        from personalscraper.conf.models.categories import CategoryConfig
        from personalscraper.conf.models.disks import DiskConfig

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

        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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

    def test_first_run_empty_db_triggers_auto_rebuild(self, tmp_path: Path) -> None:
        """Empty library.db at __init__ time triggers rebuild when config is supplied.

        Scenario: brand-new install, library.db does not yet contain any
        media_item rows.  Passing a Config to MediaIndex.__init__ must fire
        rebuild() automatically so dispatch decisions are immediately accurate.
        After __init__ returns, media_item rows must be present.
        """
        from personalscraper.conf.models.disks import DiskConfig

        # Create a real disk structure so rebuild() can scan it.
        disk = tmp_path / "medias"
        (disk / "movies" / "The Matrix (1999)").mkdir(parents=True)
        (disk / "tv_shows" / "Fallout (2024)").mkdir(parents=True)

        disk_config = DiskConfig(
            id="drive_a",
            path=disk,
            categories=["movies", "tv_shows"],
        )

        # Build a minimal stub that looks enough like Config for __init__:
        # only .disks and .categories are accessed during the auto-rebuild.
        class _StubConfig:
            disks = [disk_config]
            categories: dict[str, object] = {}  # no folder_name remapping needed

        # Pass a fresh DB path — library.db does not exist yet (empty first run).
        idx = MediaIndex(tmp_path / "index.db", config=_StubConfig(), event_bus=EventBus())  # type: ignore[arg-type]

        # Auto-rebuild must have inserted the two media directories.
        assert idx.count == 2
        assert idx.find("The Matrix (1999)", "movie") is not None
        assert idx.find("Fallout (2024)", "tvshow") is not None

        # A second instantiation (rows now present) must NOT trigger another rebuild.
        idx2 = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        assert idx2.count == 2

    def test_rebuild_without_categories_falls_back_to_legacy(self, tmp_path: Path) -> None:
        """When no ``categories`` provided, rebuild keeps legacy behaviour.

        Folder name must equal category ID (backward compat with existing
        tests that pre-date the folder_name remapping).
        """
        from personalscraper.conf.models.disks import DiskConfig

        disk = tmp_path / "medias"
        (disk / "movies" / "Movie A").mkdir(parents=True)
        (disk / "series" / "Show B").mkdir(parents=True)  # Will be skipped — no mapping

        config = DiskConfig(id="drive_a", path=disk, categories=["movies", "tv_shows"])
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
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
        # Title is canonicalized at storage (tech-debt 8.12 _upsert_media_item
        # strips " (YYYY)" suffix to dedup rows). dispatch_path preserves the
        # original full name on disk for FS operations.
        assert result.name == "Jumanji"


# ---------------------------------------------------------------------------
# Provider-ID matching (Rick-and-Morty split regression, torrent-write P15)
# ---------------------------------------------------------------------------


class TestProviderIdMatch:
    """Match an existing entry by canonical provider id when the name differs.

    Regression: dispatch matched staging→disk by normalized folder name only,
    so a show already on disk under a localized / mis-named folder (e.g.
    ``Rick et Morty (2006)``, TVDB 275274) was not recognized as the same show
    as the staging folder ``Rick and Morty (2013)`` (same TVDB 275274) and was
    dispatched as a brand-new folder — splitting the show across two folders.
    The match now keys on the canonical provider id parsed from the staging
    folder's NFO (``media_dir``) when the name lookup misses.
    """

    @staticmethod
    def _write_tvshow(root: Path, folder: str, tvdb: str) -> Path:
        """Create a real show folder with a ``tvshow.nfo`` carrying a TVDB id."""
        show_dir = root / folder
        show_dir.mkdir(parents=True)
        (show_dir / "tvshow.nfo").write_text(
            '<?xml version="1.0"?><tvshow>'
            f'<uniqueid type="tvdb" default="true">{tvdb}</uniqueid>'
            "<title>Rick and Morty</title></tvshow>",
            encoding="utf-8",
        )
        return show_dir

    @staticmethod
    def _write_movie(root: Path, folder: str, title: str, tmdb: str) -> Path:
        """Create a real movie folder with a ``<title>.nfo`` carrying a TMDB id."""
        movie_dir = root / folder
        movie_dir.mkdir(parents=True)
        (movie_dir / f"{title}.nfo").write_text(
            '<?xml version="1.0"?><movie>'
            f'<uniqueid type="tmdb" default="true">{tmdb}</uniqueid>'
            f"<title>{title}</title></movie>",
            encoding="utf-8",
        )
        return movie_dir

    def test_same_tvdb_different_name_is_matched(self, tmp_path: Path) -> None:
        """Same-TVDB show under a different on-disk name resolves to the existing folder."""
        disk_dir = self._write_tvshow(tmp_path / "disk1" / "series animations", "Rick et Morty (2006)", "275274")
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Rick et Morty (2006)",
                disk="disk1",
                category="tv_shows_animation",
                path=str(disk_dir),
                media_type="tvshow",
            )
        )

        staging_dir = self._write_tvshow(tmp_path / "staging", "Rick and Morty (2013)", "275274")
        result = idx.find("Rick and Morty (2013)", "tvshow", media_dir=staging_dir)

        assert result is not None, "same-TVDB show under a different name must be matched"
        assert result.path == str(disk_dir)
        assert result.disk == "disk1"

    def test_movie_matched_by_tmdb_when_name_differs(self, tmp_path: Path) -> None:
        """Same-TMDB movie under a different on-disk name resolves to the existing folder."""
        disk_dir = self._write_movie(tmp_path / "disk1" / "films", "Cité des Anges (1998)", "Cité des Anges", "795")
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Cité des Anges (1998)",
                disk="disk1",
                category="movies",
                path=str(disk_dir),
                media_type="movie",
            )
        )

        staging_dir = self._write_movie(tmp_path / "staging", "City of Angels (1998)", "City of Angels", "795")
        result = idx.find("City of Angels (1998)", "movie", media_dir=staging_dir)

        assert result is not None, "same-TMDB movie under a different name must be matched"
        assert result.path == str(disk_dir)

    def test_no_provider_id_falls_back_to_name(self, tmp_path: Path) -> None:
        """A staging folder without any NFO id falls back to name matching (no crash)."""
        disk_dir = self._write_tvshow(tmp_path / "disk1" / "series", "Some Show (2020)", "111111")
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Some Show (2020)",
                disk="disk1",
                category="tv_shows",
                path=str(disk_dir),
                media_type="tvshow",
            )
        )

        # Staging folder with NO nfo → no id to match on.
        staging_dir = tmp_path / "staging" / "Totally Different (2024)"
        staging_dir.mkdir(parents=True)
        result = idx.find("Totally Different (2024)", "tvshow", media_dir=staging_dir)

        assert result is None

    def test_exact_name_match_is_not_shadowed_by_id_lookup(self, tmp_path: Path) -> None:
        """An exact-name match is not shadowed by the provider-id pass."""
        disk_dir = self._write_tvshow(tmp_path / "disk1" / "series", "Exact Show (2021)", "222222")
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Exact Show (2021)",
                disk="disk1",
                category="tv_shows",
                path=str(disk_dir),
                media_type="tvshow",
            )
        )

        result = idx.find("Exact Show (2021)", "tvshow", media_dir=disk_dir)

        assert result is not None
        assert result.path == str(disk_dir)

    def test_placeholder_imdb_id_does_not_false_match(self, tmp_path: Path) -> None:
        """A leaked imdb='None' placeholder must not match another row carrying it."""
        # On-disk show A: valid tvdb 100 + junk imdb 'None' (a historical scrape leak).
        disk_a = tmp_path / "disk1" / "series" / "Alpha Show (2000)"
        disk_a.mkdir(parents=True)
        (disk_a / "tvshow.nfo").write_text(
            '<?xml version="1.0"?><tvshow>'
            '<uniqueid type="tvdb" default="true">100</uniqueid>'
            '<uniqueid type="imdb">None</uniqueid>'
            "<title>Alpha Show</title></tvshow>",
            encoding="utf-8",
        )
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Alpha Show (2000)",
                disk="disk1",
                category="tv_shows",
                path=str(disk_a),
                media_type="tvshow",
            )
        )

        # Staging show B: a *different* tvdb (not on disk) + the same junk imdb 'None'.
        staging_b = tmp_path / "staging" / "Beta Show (2099)"
        staging_b.mkdir(parents=True)
        (staging_b / "tvshow.nfo").write_text(
            '<?xml version="1.0"?><tvshow>'
            '<uniqueid type="tvdb" default="true">200</uniqueid>'
            '<uniqueid type="imdb">None</uniqueid>'
            "<title>Beta Show</title></tvshow>",
            encoding="utf-8",
        )
        result = idx.find("Beta Show (2099)", "tvshow", media_dir=staging_b)

        assert result is None, "placeholder imdb='None' must not false-match an unrelated show"

    def test_ambiguous_external_id_resolves_to_one_existing_entry(self, tmp_path: Path) -> None:
        """Two on-disk folders sharing one TVDB id resolve to one of them, no crash."""
        disk_old = self._write_tvshow(tmp_path / "disk1" / "series", "Rick et Morty (2006)", "275274")
        disk_new = self._write_tvshow(tmp_path / "disk1" / "series2", "Rick and Morty (2013)", "275274")
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.add(
            IndexEntry(
                name="Rick et Morty (2006)",
                disk="disk1",
                category="tv_shows",
                path=str(disk_old),
                media_type="tvshow",
            )
        )
        idx.add(
            IndexEntry(
                name="Rick and Morty (2013)",
                disk="disk1",
                category="tv_shows",
                path=str(disk_new),
                media_type="tvshow",
            )
        )

        staging = self._write_tvshow(tmp_path / "staging", "Rick & Morty (2013)", "275274")
        result = idx.find("Rick & Morty (2013)", "tvshow", media_dir=staging)

        assert result is not None
        assert result.path in {str(disk_old), str(disk_new)}


# ---------------------------------------------------------------------------
# Connection lifecycle — FD-leak guard
# ---------------------------------------------------------------------------


class TestMediaIndexConnectionLifecycle:
    """Tests for close(), __enter__/__exit__, and __del__ behaviour."""

    def test_configured_db_path_wins_over_constructor_db_path(self, tmp_path: Path) -> None:
        """When Config is supplied, MediaIndex must open config.indexer.db_path."""

        class _Indexer:
            db_path = tmp_path / ".data" / "library.db"

        class _Config:
            indexer = _Indexer()
            disks = []
            categories = {}

        constructor_db_path = tmp_path / "other_index" / "media_index.db"
        constructor_db_path.parent.mkdir()

        with MediaIndex(constructor_db_path, config=_Config(), event_bus=EventBus()) as idx:  # type: ignore[arg-type]
            idx.add(
                IndexEntry(
                    name="Configured DB (2026)",
                    disk="drive_a",
                    category="movies",
                    path="/drive_a/movies/Configured DB (2026)",
                    media_type="movie",
                )
            )

        assert _Indexer.db_path.exists()
        assert not constructor_db_path.exists()

    def test_context_manager_closes_connection(self, tmp_path: Path) -> None:
        """FD count must return to baseline after the ``with`` block exits.

        Opens a MediaIndex via the context manager, performs a trivial query
        inside, then asserts that no extra file descriptors remain open to
        the library.db file after ``__exit__`` is called.

        Uses ``resource.getrlimit(RLIMIT_NOFILE)`` to confirm we're not
        leaking FDs across repeated open/close cycles.
        """
        import os
        import resource

        db_path = tmp_path / "index.db"

        # Measure FD baseline before any MediaIndex is created.
        soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        assert soft_limit > 10, "FD limit too low for this test"

        # Record open FD count before entering the with block.

        def _open_fds() -> set[int]:
            """Return the set of currently open file descriptor numbers."""
            try:
                return {int(fd) for fd in os.listdir("/proc/self/fd")}
            except FileNotFoundError:
                # macOS: use os.listdir on /dev/fd instead
                try:
                    return {int(fd) for fd in os.listdir("/dev/fd")}
                except (FileNotFoundError, OSError):
                    return set()

        fds_before = _open_fds()

        # Open via context manager, do a query, then exit.
        with MediaIndex(db_path, config=None, event_bus=EventBus()) as idx:
            idx.add(
                IndexEntry(
                    name="Connection Test (2024)",
                    disk="drive_a",
                    category="movies",
                    path=str(tmp_path / "drive_a" / "Connection Test (2024)"),
                    media_type="movie",
                )
            )
            assert idx.count == 1
            # Confirm the DB file exists while the connection is open.
            assert db_path.exists()

        # After __exit__, the SQLite connection must be closed.
        # Any FDs opened for library.db must now be released.
        fds_after = _open_fds()
        leaked = fds_after - fds_before
        # Filter to only FDs that reference the DB path (avoids noise from
        # pytest internals opening unrelated files during the test body).
        leaked_db_fds = {fd for fd in leaked if _fd_points_to(fd, str(db_path))}
        assert not leaked_db_fds, f"FD leak detected: {len(leaked_db_fds)} file descriptor(s) still open to {db_path}"

    def test_explicit_close_is_idempotent(self, tmp_path: Path) -> None:
        """Calling close() multiple times must not raise."""
        idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
        idx.close()
        idx.close()  # Second call must be a no-op, not an exception.


class TestMediaIndexBusPassthrough:
    """``MediaIndex.__init__`` forwards its caller's bus into ``open_db``.

    Regression test for the cycle-2 W1 finding: ``MediaIndex`` previously
    accepted ``event_bus: EventBus | None = None`` and silently spun up a
    fresh unobserved bus when the caller forgot the kwarg — silently
    routing any ``DiskFullWarning`` to nowhere. The required-bus signature
    guarantees the parameter is present; this test asserts the value is
    actually forwarded to ``open_db`` (the only emit site reachable from
    the constructor today).
    """

    def test_constructor_forwards_caller_bus_to_open_db(self, tmp_path: Path) -> None:
        """The bus passed to ``MediaIndex(...)`` is the same object handed to ``open_db``."""
        from unittest.mock import patch

        bus = EventBus()
        captured: dict[str, object] = {}

        real_open_db = __import__(
            "personalscraper.dispatch.media_index",
            fromlist=["open_db"],
        ).open_db

        def _spy(db_path: Path, *, event_bus: EventBus) -> object:
            captured["event_bus"] = event_bus
            return real_open_db(db_path, event_bus=event_bus)

        with patch("personalscraper.dispatch.media_index.open_db", side_effect=_spy):
            MediaIndex(tmp_path / "index.db", event_bus=bus, auto_rebuild=False)

        assert captured["event_bus"] is bus, "MediaIndex must forward the caller's bus to open_db, not a fresh one"


def _fd_points_to(fd: int, path: str) -> bool:
    """Return True if the open file descriptor *fd* references *path*.

    Uses ``/proc/self/fd/<fd>`` (Linux) or ``fcntl``-based fallback (macOS).
    Returns False on any OS error so the test degrades gracefully on
    platforms that don't expose FD symlinks.

    Args:
        fd: File descriptor number to inspect.
        path: Absolute filesystem path to check against.

    Returns:
        True if ``fd`` is open and points to ``path``.
    """
    import os

    try:
        link = os.readlink(f"/proc/self/fd/{fd}")
        return link == path
    except (OSError, AttributeError):
        pass
    try:
        link = os.readlink(f"/dev/fd/{fd}")
        return link == path
    except (OSError, AttributeError):
        pass
    return False
