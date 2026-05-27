"""Tests that config.example/ passes Pydantic validation via load_config_dir."""

from pathlib import Path

from personalscraper.conf.loader import load_config_dir
from personalscraper.conf.models.config import Config

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_DIR = _REPO_ROOT / "config.example"


class TestExampleConfig:
    """Tests for the bundled config.example/ template directory."""

    def test_example_dir_exists_and_has_master(self):
        """config.example/config.json5 must exist."""
        assert EXAMPLE_DIR.is_dir(), f"config.example/ not found at {EXAMPLE_DIR}"
        assert (EXAMPLE_DIR / "config.json5").is_file(), "config.example/config.json5 missing"

    def test_example_parses_and_validates(self):
        """config.example/ must load and pass full Pydantic validation.

        Design: docs/reference/architecture.md#configuration
        Design: docs/reference/scraping.md#configuration-reference
        Contract: example config parses and validates, covering both architecture and scraping config reference docs.
        """
        config = load_config_dir(EXAMPLE_DIR)
        assert isinstance(config, Config)

    def test_example_has_expected_structure(self):
        """config.example/ must have the expected top-level structure."""
        config = load_config_dir(EXAMPLE_DIR)
        assert config.config_version == 1
        assert len(config.disks) >= 1
        assert config.disks[0].id == "drive_a"

    def test_example_genre_mapping_populated(self):
        """config.example/ genre_mapping must have TMDB and TVDB entries."""
        config = load_config_dir(EXAMPLE_DIR)
        assert 16 in config.genre_mapping.tmdb_movies
        assert 16 in config.genre_mapping.tmdb_tv
        assert 27 in config.genre_mapping.tvdb

    def test_example_anime_rule_enabled(self):
        """config.example/ anime_rule must be enabled and target anime."""
        config = load_config_dir(EXAMPLE_DIR)
        assert config.anime_rule.enabled is True
        assert config.anime_rule.maps_to == "anime"
        assert "JP" in config.anime_rule.requires_origin_country

    def test_example_all_eleven_categories_defined(self):
        """config.example/ must define all 11 builtin category folder names."""
        from personalscraper.conf.ids import BUILTIN_CATEGORY_IDS

        config = load_config_dir(EXAMPLE_DIR)
        for cid in BUILTIN_CATEGORY_IDS:
            cat = config.category(cid)
            assert cat.folder_name, f"Category '{cid}' has empty folder_name"

    def test_thresholds_config_loaded(self):
        """config.example/ must define thresholds with defaults."""
        config = load_config_dir(EXAMPLE_DIR)
        assert config.thresholds.min_free_space_staging_gb == 20
        assert config.thresholds.min_free_space_disk_gb == 100
        assert config.thresholds.circuit_breaker_threshold == 5
        assert config.thresholds.circuit_breaker_cooldown == 300

    def test_scraper_artwork_language_loaded(self):
        """config.example/ scraper must define artwork_language."""
        config = load_config_dir(EXAMPLE_DIR)
        assert config.scraper.artwork_language == "en"

    def test_db_path_derived_from_data_dir(self):
        """When db_path is null, it must be derived from paths.data_dir."""
        config = load_config_dir(EXAMPLE_DIR)
        expected = config.paths.data_dir / "library.db"
        assert config.indexer.db_path == expected
