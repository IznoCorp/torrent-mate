"""Tests that config.example.json5 passes Pydantic validation via load_config."""

from pathlib import Path

from personalscraper.conf.loader import load_config
from personalscraper.conf.models import Config

# Resolve relative to the repo root (two levels up from tests/conf/)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_CONFIG_PATH = _REPO_ROOT / "config.example.json5"


class TestExampleConfig:
    """Tests for the bundled config.example.json5 template."""

    def test_example_parses_and_validates(self):
        """config.example.json5 must load and pass full Pydantic validation."""
        assert EXAMPLE_CONFIG_PATH.exists(), f"config.example.json5 not found at {EXAMPLE_CONFIG_PATH}"
        config = load_config(EXAMPLE_CONFIG_PATH)
        assert isinstance(config, Config)

    def test_example_has_expected_structure(self):
        """config.example.json5 must have the expected top-level structure."""
        config = load_config(EXAMPLE_CONFIG_PATH)
        assert config.config_version == 1
        assert len(config.disks) >= 1
        assert config.disks[0].id == "drive_a"

    def test_example_genre_mapping_populated(self):
        """config.example.json5 genre_mapping must have TMDB and TVDB entries."""
        config = load_config(EXAMPLE_CONFIG_PATH)
        assert 16 in config.genre_mapping.tmdb_movies
        assert 16 in config.genre_mapping.tmdb_tv
        assert 27 in config.genre_mapping.tvdb

    def test_example_anime_rule_enabled(self):
        """config.example.json5 anime_rule must be enabled and target anime."""
        config = load_config(EXAMPLE_CONFIG_PATH)
        assert config.anime_rule.enabled is True
        assert config.anime_rule.maps_to == "anime"
        assert "JP" in config.anime_rule.requires_origin_country

    def test_example_all_eleven_categories_defined(self):
        """config.example.json5 must define all 11 builtin category folder names."""
        from personalscraper.conf.ids import BUILTIN_CATEGORY_IDS

        config = load_config(EXAMPLE_CONFIG_PATH)
        for cid in BUILTIN_CATEGORY_IDS:
            cat = config.category(cid)
            assert cat.folder_name, f"Category '{cid}' has empty folder_name"
