"""Tests for personalscraper.conf.migration — V14 → V15 migration utilities."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from personalscraper.conf.ids import BUILTIN_CATEGORY_IDS
from personalscraper.conf.migration import (
    V14_KNOWN_CATEGORIES,
    V14_LABEL_TO_ID,
    V14_TMDB_MOVIE_GENRE_MAP,
    V14_TMDB_TV_GENRE_MAP,
    V14_TVDB_GENRE_MAP,
    generate_config_from_env,
    migrate_category_files,
    migrate_data_dir,
    migrate_library_json,
    migrate_library_preferences,
)
from personalscraper.conf.models import Config, LibraryPrefs

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
V14_ENV_SAMPLE = FIXTURES_DIR / "v14_env_sample.env"
V14_LIB_PREFS_SAMPLE = FIXTURES_DIR / "v14_library_preferences_sample.json"
V14_LIB_INDEX_SAMPLE = FIXTURES_DIR / "v14_library_index_sample.json"
V14_LIB_ANALYSIS_SAMPLE = FIXTURES_DIR / "v14_library_analysis_sample.json"
V14_LIB_RESCRAPE_SAMPLE = FIXTURES_DIR / "v14_library_rescrape_sample.json"
V14_LIB_RECOMMENDATIONS_SAMPLE = FIXTURES_DIR / "v14_library_recommendations_sample.json"
V14_LIB_VALIDATION_SAMPLE = FIXTURES_DIR / "v14_library_validation_sample.json"


# ---------------------------------------------------------------------------
# Helper: parse v14_env_sample.env into a dict
# ---------------------------------------------------------------------------


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a plain dict, ignoring blank/comment lines.

    Args:
        path: Path to the .env file.

    Returns:
        Dict mapping variable names to their string values.
    """
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


# ===========================================================================
# 4.1 — V14 table coherence
# ===========================================================================


class TestV14TableCoherence:
    """Coherence checks between V14_LABEL_TO_ID and V14_KNOWN_CATEGORIES."""

    def test_label_to_id_keys_equal_known_categories(self) -> None:
        """V14_LABEL_TO_ID.keys() must match V14_KNOWN_CATEGORIES exactly."""
        assert set(V14_LABEL_TO_ID.keys()) == V14_KNOWN_CATEGORIES

    def test_known_categories_has_11_entries(self) -> None:
        """V14 has exactly 11 known categories."""
        assert len(V14_KNOWN_CATEGORIES) == 11

    def test_label_to_id_values_are_builtin_ids(self) -> None:
        """All V15 IDs in V14_LABEL_TO_ID must be valid builtin category IDs."""
        for label, cid in V14_LABEL_TO_ID.items():
            assert cid in BUILTIN_CATEGORY_IDS, f"V14 label '{label}' maps to unknown V15 ID '{cid}'"

    def test_tmdb_movie_genre_map_values_are_builtin_ids(self) -> None:
        """All V15 IDs in V14_TMDB_MOVIE_GENRE_MAP must be builtin IDs."""
        for gid, cid in V14_TMDB_MOVIE_GENRE_MAP.items():
            assert cid in BUILTIN_CATEGORY_IDS, f"TMDB movie genre {gid} maps to unknown ID '{cid}'"

    def test_tmdb_tv_genre_map_values_are_builtin_ids(self) -> None:
        """All V15 IDs in V14_TMDB_TV_GENRE_MAP must be builtin IDs."""
        for gid, cid in V14_TMDB_TV_GENRE_MAP.items():
            assert cid in BUILTIN_CATEGORY_IDS, f"TMDB TV genre {gid} maps to unknown ID '{cid}'"

    def test_tvdb_genre_map_values_are_builtin_ids(self) -> None:
        """All V15 IDs in V14_TVDB_GENRE_MAP must be builtin IDs."""
        for gid, cid in V14_TVDB_GENRE_MAP.items():
            assert cid in BUILTIN_CATEGORY_IDS, f"TVDB genre {gid} maps to unknown ID '{cid}'"

    def test_tmdb_movie_genre_map_known_ids(self) -> None:
        """Spot-check V14 TMDB movie genre IDs are correctly mapped."""
        assert V14_TMDB_MOVIE_GENRE_MAP[16] == "movies_animation"
        assert V14_TMDB_MOVIE_GENRE_MAP[99] == "movies_documentary"

    def test_tmdb_tv_genre_map_known_ids(self) -> None:
        """Spot-check V14 TMDB TV genre IDs are correctly mapped."""
        assert V14_TMDB_TV_GENRE_MAP[16] == "tv_shows_animation"
        assert V14_TMDB_TV_GENRE_MAP[99] == "tv_shows_documentary"
        assert V14_TMDB_TV_GENRE_MAP[10764] == "tv_programs"
        assert V14_TMDB_TV_GENRE_MAP[10767] == "tv_programs"
        assert V14_TMDB_TV_GENRE_MAP[10763] == "tv_programs"

    def test_tvdb_genre_map_known_ids(self) -> None:
        """Spot-check V14 TVDB genre IDs are correctly mapped."""
        assert V14_TVDB_GENRE_MAP[27] == "anime"
        assert V14_TVDB_GENRE_MAP[17] == "tv_shows_animation"
        assert V14_TVDB_GENRE_MAP[3] == "tv_shows_documentary"
        assert V14_TVDB_GENRE_MAP[8] == "tv_programs"
        assert V14_TVDB_GENRE_MAP[10] == "tv_programs"
        assert V14_TVDB_GENRE_MAP[11] == "tv_programs"


# ===========================================================================
# 4.2 — generate_config_from_env
# ===========================================================================


class TestGenerateConfigFromEnv:
    """Tests for generate_config_from_env."""

    @pytest.fixture()
    def v14_env(self) -> dict[str, str]:
        """Load the V14 sample .env fixture."""
        return _load_env_file(V14_ENV_SAMPLE)

    def test_result_validates_as_config(self, v14_env: dict[str, str]) -> None:
        """generate_config_from_env result must pass Config.model_validate."""
        result = generate_config_from_env(v14_env)
        cfg = Config.model_validate(result)
        assert cfg is not None

    def test_four_disks_generated(self, v14_env: dict[str, str]) -> None:
        """Four DISK*_DIR env vars must produce 4 disks."""
        result = generate_config_from_env(v14_env)
        assert len(result["disks"]) == 4

    def test_disk_ids_are_disk_n(self, v14_env: dict[str, str]) -> None:
        """Disk IDs must be 'disk_1', 'disk_2', 'disk_3', 'disk_4'."""
        result = generate_config_from_env(v14_env)
        ids = [d["id"] for d in result["disks"]]
        assert ids == ["disk_1", "disk_2", "disk_3", "disk_4"]

    def test_disk_paths_match_env(self, v14_env: dict[str, str]) -> None:
        """Disk paths must match the corresponding DISK*_DIR env vars."""
        result = generate_config_from_env(v14_env)
        disks_by_id = {d["id"]: d for d in result["disks"]}
        assert disks_by_id["disk_1"]["path"] == v14_env["DISK1_DIR"]
        assert disks_by_id["disk_2"]["path"] == v14_env["DISK2_DIR"]

    def test_disk1_categories_mapped_to_v15_ids(self, v14_env: dict[str, str]) -> None:
        """Disk1 categories must all be valid V15 builtin IDs."""
        result = generate_config_from_env(v14_env)
        disk1 = next(d for d in result["disks"] if d["id"] == "disk_1")
        for cid in disk1["categories"]:
            assert cid in BUILTIN_CATEGORY_IDS, f"'{cid}' is not a builtin ID"

    def test_disk2_has_anime(self, v14_env: dict[str, str]) -> None:
        """Disk2 had 'series animes' in V14 → must have 'anime' in V15."""
        result = generate_config_from_env(v14_env)
        disk2 = next(d for d in result["disks"] if d["id"] == "disk_2")
        assert "anime" in disk2["categories"]

    def test_paths_present(self, v14_env: dict[str, str]) -> None:
        """paths.torrent_complete_dir and paths.staging_dir must be set."""
        result = generate_config_from_env(v14_env)
        assert result["paths"]["torrent_complete_dir"] == v14_env["TORRENT_COMPLETE_DIR"]
        assert result["paths"]["staging_dir"] == v14_env["STAGING_DIR"]

    def test_data_dir_inside_staging(self, v14_env: dict[str, str]) -> None:
        """data_dir must be inside staging_dir as '<staging>/.data'."""
        result = generate_config_from_env(v14_env)
        expected = str(Path(v14_env["STAGING_DIR"]) / ".data")
        assert result["paths"]["data_dir"] == expected

    def test_genre_mapping_present(self, v14_env: dict[str, str]) -> None:
        """genre_mapping must contain tmdb_movies, tmdb_tv, tvdb entries."""
        result = generate_config_from_env(v14_env)
        gm = result["genre_mapping"]
        assert "16" in gm["tmdb_movies"]
        assert "16" in gm["tmdb_tv"]
        assert "27" in gm["tvdb"]

    def test_anime_rule_present(self, v14_env: dict[str, str]) -> None:
        """anime_rule must be enabled and mirror V14 behavior."""
        result = generate_config_from_env(v14_env)
        ar = result["anime_rule"]
        assert ar["enabled"] is True
        assert ar["requires_genre_id"] == 16
        assert "JP" in ar["requires_origin_country"]
        assert ar["maps_to"] == "anime"
        assert ar["applies_to"] == "tv"

    def test_categories_use_v14_folder_names(self, v14_env: dict[str, str]) -> None:
        """categories[id].folder_name must be the original V14 French label."""
        result = generate_config_from_env(v14_env)
        cats = result["categories"]
        # 'films' V14 label → 'movies' ID → folder_name should be 'films'
        assert cats["movies"]["folder_name"] == "films"
        assert cats["anime"]["folder_name"] == "series animes"

    def test_missing_disk_env_produces_fewer_disks(self) -> None:
        """If only 2 DISK*_DIR are provided, only 2 disks should appear."""
        env = {
            "DISK1_DIR": "/mnt/disk1",
            "DISK3_DIR": "/mnt/disk3",
            "STAGING_DIR": "/mnt/staging",
            "TORRENT_COMPLETE_DIR": "/mnt/complete",
        }
        result = generate_config_from_env(env)
        ids = [d["id"] for d in result["disks"]]
        assert "disk_1" in ids
        assert "disk_3" in ids
        assert "disk_2" not in ids
        assert "disk_4" not in ids

    def test_library_empty_without_prefs_path(self, v14_env: dict[str, str]) -> None:
        """Without library_prefs_path, result['library'] must be an empty dict."""
        result = generate_config_from_env(v14_env)
        assert result["library"] == {}

    def test_library_merged_with_prefs_path(self, v14_env: dict[str, str]) -> None:
        """With library_prefs_path, result['library'] must contain video/audio sections."""
        result = generate_config_from_env(v14_env, library_prefs_path=V14_LIB_PREFS_SAMPLE)
        lib = result["library"]
        assert "video" in lib
        assert "audio" in lib
        assert "subtitles" in lib

    def test_full_config_with_library_validates(self, v14_env: dict[str, str]) -> None:
        """Full result with library prefs must validate as Config."""
        result = generate_config_from_env(v14_env, library_prefs_path=V14_LIB_PREFS_SAMPLE)
        cfg = Config.model_validate(result)
        assert cfg.library.video.preferred_codec == "hevc"


# ===========================================================================
# 4.3 — migrate_library_preferences
# ===========================================================================


class TestMigrateLibraryPreferences:
    """Tests for migrate_library_preferences."""

    def test_returns_dict(self) -> None:
        """migrate_library_preferences must return a dict."""
        result = migrate_library_preferences(V14_LIB_PREFS_SAMPLE)
        assert isinstance(result, dict)

    def test_result_validates_as_library_prefs(self) -> None:
        """Result must pass LibraryPrefs.model_validate."""
        result = migrate_library_preferences(V14_LIB_PREFS_SAMPLE)
        prefs = LibraryPrefs.model_validate(result)
        assert prefs is not None

    def test_video_section_preserved(self) -> None:
        """Video section must be present with correct values."""
        result = migrate_library_preferences(V14_LIB_PREFS_SAMPLE)
        assert result["video"]["preferred_codec"] == "hevc"
        assert result["video"]["preferred_resolution"] == "1080p"

    def test_audio_section_preserved(self) -> None:
        """Audio section must be present."""
        result = migrate_library_preferences(V14_LIB_PREFS_SAMPLE)
        assert "profile_priority" in result["audio"]

    def test_subtitles_section_preserved(self) -> None:
        """Subtitles section must be present with required_languages."""
        result = migrate_library_preferences(V14_LIB_PREFS_SAMPLE)
        assert result["subtitles"]["required_languages"] == ["fra"]

    def test_encoding_rules_preserved(self) -> None:
        """encoding_rules must be a non-empty list."""
        result = migrate_library_preferences(V14_LIB_PREFS_SAMPLE)
        assert isinstance(result["encoding_rules"], list)
        assert len(result["encoding_rules"]) == 2

    def test_encoding_rule_criteria_genre(self) -> None:
        """EncodingRule criteria.genre (string) must survive migration unchanged."""
        result = migrate_library_preferences(V14_LIB_PREFS_SAMPLE)
        rule = result["encoding_rules"][0]
        assert rule["criteria"]["genre"] == "Animation"

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """ValueError must be raised for a non-existent path."""
        with pytest.raises(ValueError, match="Cannot read"):
            migrate_library_preferences(tmp_path / "nonexistent.json")

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        """ValueError must be raised for invalid JSON."""
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="Cannot read"):
            migrate_library_preferences(bad)

    def test_raises_on_non_object_json(self, tmp_path: Path) -> None:
        """ValueError must be raised when JSON root is not an object."""
        bad = tmp_path / "array.json"
        bad.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="Expected a JSON object"):
            migrate_library_preferences(bad)


# ===========================================================================
# 4.4 — migrate_library_json
# ===========================================================================


class TestMigrateLibraryJson:
    """Tests for migrate_library_json."""

    def _copy_fixture(self, src: Path, dst: Path) -> Path:
        """Copy a fixture file to a temp directory and return the new path."""
        target = dst / src.name
        shutil.copy2(src, target)
        return target

    def test_library_index_labels_rewritten(self, tmp_path: Path) -> None:
        """V14 labels in library_index.json must be rewritten to V15 IDs."""
        target = self._copy_fixture(V14_LIB_INDEX_SAMPLE, tmp_path)
        target = target.rename(tmp_path / "library_index.json")
        migrate_library_json(target)
        data = json.loads(target.read_text(encoding="utf-8"))
        categories = {item["category"] for item in data["items"]}
        assert categories <= BUILTIN_CATEGORY_IDS, f"Non-ID values remain: {categories - BUILTIN_CATEGORY_IDS}"

    def test_backup_created(self, tmp_path: Path) -> None:
        """A .v14.bak backup file must be created."""
        target = self._copy_fixture(V14_LIB_INDEX_SAMPLE, tmp_path)
        target = target.rename(tmp_path / "library_index.json")
        migrate_library_json(target)
        backup = target.with_suffix(".json.v14.bak")
        assert backup.exists()

    def test_backup_contains_original_labels(self, tmp_path: Path) -> None:
        """Backup must contain the original V14 French labels."""
        target = self._copy_fixture(V14_LIB_INDEX_SAMPLE, tmp_path)
        target = target.rename(tmp_path / "library_index.json")
        migrate_library_json(target)
        backup = target.with_suffix(".json.v14.bak")
        bak_data = json.loads(backup.read_text(encoding="utf-8"))
        original_labels = {item["category"] for item in bak_data["items"]}
        # All original labels must be V14 known categories
        assert original_labels <= V14_KNOWN_CATEGORIES

    def test_raises_if_backup_exists(self, tmp_path: Path) -> None:
        """FileExistsError must be raised if backup already exists."""
        target = self._copy_fixture(V14_LIB_INDEX_SAMPLE, tmp_path)
        target = target.rename(tmp_path / "library_index.json")
        backup = target.with_suffix(".json.v14.bak")
        backup.write_text("{}", encoding="utf-8")
        with pytest.raises(FileExistsError, match="Backup already exists"):
            migrate_library_json(target)

    def test_unknown_label_left_as_is(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown V14 labels must be left in place and a WARN must be logged."""
        data = {
            "items": [
                {"category": "films", "title": "Known"},
                {"category": "unknown_v14_category", "title": "Unknown"},
            ]
        }
        target = tmp_path / "library_index.json"
        target.write_text(json.dumps(data), encoding="utf-8")
        import logging

        with caplog.at_level(logging.WARNING, logger="personalscraper.conf.migration"):
            migrate_library_json(target)

        updated = json.loads(target.read_text(encoding="utf-8"))
        cats = {item["category"] for item in updated["items"]}
        assert "unknown_v14_category" in cats, "Unknown label must not be removed"
        assert "movies" in cats, "Known label must be rewritten"
        messages = [r.getMessage() for r in caplog.records]
        assert any("unknown_v14_category" in m for m in messages)

    def test_analysis_labels_rewritten(self, tmp_path: Path) -> None:
        """V14 labels in library_analysis.json must be rewritten."""
        target = self._copy_fixture(V14_LIB_ANALYSIS_SAMPLE, tmp_path)
        target = target.rename(tmp_path / "library_analysis.json")
        migrate_library_json(target)
        data = json.loads(target.read_text(encoding="utf-8"))
        categories = {item["category"] for item in data["items"]}
        assert categories <= BUILTIN_CATEGORY_IDS

    def test_rescrape_labels_rewritten(self, tmp_path: Path) -> None:
        """V14 labels in library_rescrape.json must be rewritten."""
        target = self._copy_fixture(V14_LIB_RESCRAPE_SAMPLE, tmp_path)
        target = target.rename(tmp_path / "library_rescrape.json")
        migrate_library_json(target)
        data = json.loads(target.read_text(encoding="utf-8"))
        for item in data["items"]:
            assert item["category"] in BUILTIN_CATEGORY_IDS

    def test_recommendations_labels_rewritten(self, tmp_path: Path) -> None:
        """V14 labels in library_recommendations.json must be rewritten."""
        target = self._copy_fixture(V14_LIB_RECOMMENDATIONS_SAMPLE, tmp_path)
        target = target.rename(tmp_path / "library_recommendations.json")
        migrate_library_json(target)
        data = json.loads(target.read_text(encoding="utf-8"))
        for item in data["items"]:
            assert item["category"] in BUILTIN_CATEGORY_IDS

    def test_validation_labels_rewritten(self, tmp_path: Path) -> None:
        """V14 labels in library_validation.json must be rewritten."""
        target = self._copy_fixture(V14_LIB_VALIDATION_SAMPLE, tmp_path)
        target = target.rename(tmp_path / "library_validation.json")
        migrate_library_json(target)
        data = json.loads(target.read_text(encoding="utf-8"))
        for item in data["items"]:
            assert item["category"] in BUILTIN_CATEGORY_IDS

    def test_skips_library_preferences(self, tmp_path: Path) -> None:
        """library_preferences.json must be silently skipped."""
        target = self._copy_fixture(V14_LIB_PREFS_SAMPLE, tmp_path)
        target = target.rename(tmp_path / "library_preferences.json")
        # Must not raise and must not create a backup.
        migrate_library_json(target)
        backup = target.with_suffix(".json.v14.bak")
        assert not backup.exists()

    def test_custom_backup_suffix(self, tmp_path: Path) -> None:
        """Custom backup_suffix must be used for the backup filename."""
        data = {"items": [{"category": "films"}]}
        target = tmp_path / "library_index.json"
        target.write_text(json.dumps(data), encoding="utf-8")
        migrate_library_json(target, backup_suffix=".bak2")
        assert (tmp_path / "library_index.json.bak2").exists()


# ===========================================================================
# 4.5 — migrate_category_files
# ===========================================================================


class TestMigrateCategoryFiles:
    """Tests for migrate_category_files."""

    def _make_nfo(self, directory: Path, filename: str = "movie.nfo") -> Path:
        """Create a minimal NFO file in *directory*.

        Args:
            directory: Target directory.
            filename: NFO filename.

        Returns:
            Path to the created NFO file.
        """
        nfo = directory / filename
        nfo.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<movie>\n"
            "  <title>Test Movie</title>\n"
            "  <genre>Action</genre>\n"
            "</movie>\n",
            encoding="utf-8",
        )
        return nfo

    def test_valid_category_migrated(self, tmp_path: Path) -> None:
        """A valid .category + NFO pair must be migrated and .category deleted."""
        media_dir = tmp_path / "films" / "Inception (2010)"
        media_dir.mkdir(parents=True)
        self._make_nfo(media_dir)
        (media_dir / ".category").write_text("films\n", encoding="utf-8")

        count = migrate_category_files(tmp_path)

        assert count == 1
        assert not (media_dir / ".category").exists()

    def test_nfo_contains_category_element(self, tmp_path: Path) -> None:
        """NFO must contain <category source="personalscraper"> after migration."""
        media_dir = tmp_path / "films" / "Test (2020)"
        media_dir.mkdir(parents=True)
        nfo = self._make_nfo(media_dir)
        (media_dir / ".category").write_text("films", encoding="utf-8")

        migrate_category_files(tmp_path)

        from xml.etree import ElementTree as ET  # noqa: PLC0415

        root = ET.parse(nfo).getroot()  # noqa: S314
        cat_els = [el for el in root.iter("category") if el.get("source") == "personalscraper"]
        assert len(cat_els) == 1
        assert cat_els[0].text == "movies"

    def test_no_nfo_sibling_skipped_with_warn(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Without NFO sibling, .category must be left in place with a WARN."""
        media_dir = tmp_path / "films" / "NoNFO (2020)"
        media_dir.mkdir(parents=True)
        (media_dir / ".category").write_text("films", encoding="utf-8")

        import logging

        with caplog.at_level(logging.WARNING, logger="personalscraper.conf.migration"):
            count = migrate_category_files(tmp_path)

        assert count == 0
        assert (media_dir / ".category").exists()
        messages = [r.getMessage() for r in caplog.records]
        assert any("NFO sibling" in m for m in messages)

    def test_unknown_label_skipped_with_warn(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Unknown label must leave .category in place with a WARN."""
        media_dir = tmp_path / "unknown_cat" / "Something"
        media_dir.mkdir(parents=True)
        self._make_nfo(media_dir)
        (media_dir / ".category").write_text("unknown_old_category", encoding="utf-8")

        import logging

        with caplog.at_level(logging.WARNING, logger="personalscraper.conf.migration"):
            count = migrate_category_files(tmp_path)

        assert count == 0
        assert (media_dir / ".category").exists()
        messages = [r.getMessage() for r in caplog.records]
        assert any("unknown_old_category" in m for m in messages)

    def test_idempotent_nfo_already_has_category(self, tmp_path: Path) -> None:
        """If NFO already has <category source="personalscraper">, skip."""
        media_dir = tmp_path / "films" / "Already (2020)"
        media_dir.mkdir(parents=True)
        nfo = media_dir / "movie.nfo"
        nfo.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<movie>\n"
            '  <category source="personalscraper">movies</category>\n'
            "</movie>\n",
            encoding="utf-8",
        )
        (media_dir / ".category").write_text("films", encoding="utf-8")

        count = migrate_category_files(tmp_path)

        # .category must remain because insertion was skipped
        assert count == 0
        assert (media_dir / ".category").exists()

    def test_lock_file_raises(self, tmp_path: Path) -> None:
        """RuntimeError must be raised if a lock file is present."""
        data_dir = tmp_path / ".personalscraper"
        data_dir.mkdir()
        (data_dir / "lock.json").write_text("{}", encoding="utf-8")

        with pytest.raises(RuntimeError, match="lock file"):
            migrate_category_files(tmp_path)

    def test_lock_file_custom_data_dir_raises(self, tmp_path: Path) -> None:
        """RuntimeError must be raised with a custom data_dir lock file."""
        custom_data = tmp_path / ".data"
        custom_data.mkdir()
        (custom_data / "lock.json").write_text("{}", encoding="utf-8")

        with pytest.raises(RuntimeError, match="lock file"):
            migrate_category_files(tmp_path, data_dir=custom_data)

    def test_returns_count_of_migrated(self, tmp_path: Path) -> None:
        """Return count must match number of successfully migrated files."""
        for i, label in enumerate(["films", "series", "theatres"]):
            d = tmp_path / f"media_{i}"
            d.mkdir()
            self._make_nfo(d)
            (d / ".category").write_text(label, encoding="utf-8")

        count = migrate_category_files(tmp_path)
        assert count == 3

    def test_tvshow_nfo_used_when_present(self, tmp_path: Path) -> None:
        """tvshow.nfo must be found and updated for TV .category files."""
        media_dir = tmp_path / "series" / "Breaking Bad"
        media_dir.mkdir(parents=True)
        nfo = self._make_nfo(media_dir, "tvshow.nfo")
        (media_dir / ".category").write_text("series", encoding="utf-8")

        migrate_category_files(tmp_path)

        from xml.etree import ElementTree as ET  # noqa: PLC0415

        root = ET.parse(nfo).getroot()  # noqa: S314
        cat_els = [el for el in root.iter("category") if el.get("source") == "personalscraper"]
        assert len(cat_els) == 1
        assert cat_els[0].text == "tv_shows"


# ===========================================================================
# 4.6 — migrate_data_dir
# ===========================================================================


class TestMigrateDataDir:
    """Tests for migrate_data_dir."""

    def _make_source(self, base: Path) -> Path:
        """Create a .personalscraper directory with sample files.

        Args:
            base: Base directory to create .personalscraper in.

        Returns:
            Path to the created .personalscraper directory.
        """
        src = base / ".personalscraper"
        src.mkdir()
        (src / "library_index.json").write_text("{}", encoding="utf-8")
        return src

    def test_source_moved_to_data(self, tmp_path: Path) -> None:
        """``migrate_data_dir`` must move .personalscraper to .data."""
        self._make_source(tmp_path)
        result = migrate_data_dir(tmp_path)
        assert result == (tmp_path / ".data").resolve()
        assert (tmp_path / ".data").exists()
        assert not (tmp_path / ".personalscraper").exists()

    def test_files_preserved_after_move(self, tmp_path: Path) -> None:
        """Files inside .personalscraper must be accessible under .data."""
        self._make_source(tmp_path)
        migrate_data_dir(tmp_path)
        assert (tmp_path / ".data" / "library_index.json").exists()

    def test_returns_absolute_path(self, tmp_path: Path) -> None:
        """Return value must be an absolute path."""
        self._make_source(tmp_path)
        result = migrate_data_dir(tmp_path)
        assert result.is_absolute()

    def test_raises_if_source_missing(self, tmp_path: Path) -> None:
        """FileNotFoundError must be raised if .personalscraper doesn't exist."""
        with pytest.raises(FileNotFoundError, match="does not exist"):
            migrate_data_dir(tmp_path)

    def test_raises_if_target_exists(self, tmp_path: Path) -> None:
        """FileExistsError must be raised if .data already exists."""
        self._make_source(tmp_path)
        (tmp_path / ".data").mkdir()
        with pytest.raises(FileExistsError, match="already exists"):
            migrate_data_dir(tmp_path)

    def test_raises_if_lock_file_present(self, tmp_path: Path) -> None:
        """RuntimeError must be raised if lock.json is present in source."""
        src = self._make_source(tmp_path)
        (src / "lock.json").write_text("{}", encoding="utf-8")
        with pytest.raises(RuntimeError, match="lock file"):
            migrate_data_dir(tmp_path)
