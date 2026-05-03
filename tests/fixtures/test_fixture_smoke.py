"""Smoke tests for the shared test_config fixture."""

from personalscraper.conf import ids as CID
from personalscraper.conf.models.config import Config


class TestTestConfigFixture:
    """Smoke tests verifying the test_config fixture is well-formed."""

    def test_fixture_is_valid_config(self, test_config):
        """test_config must be a fully validated Config instance."""
        assert isinstance(test_config, Config)

    def test_drive_a_is_first_disk(self, test_config):
        """First disk must have id 'drive_a'."""
        assert test_config.disks[0].id == "drive_a"

    def test_three_disks(self, test_config):
        """Fixture must have exactly 3 disks."""
        assert len(test_config.disks) == 3

    def test_all_builtin_categories_configured(self, test_config):
        """All 11 builtin IDs must have a category config."""
        for cid in CID.BUILTIN_CATEGORY_IDS:
            cat = test_config.category(cid)
            assert cat.folder_name == f"cat_{cid}", f"Expected folder_name='cat_{cid}', got '{cat.folder_name}'"

    def test_anime_rule_targets_tv(self, test_config):
        """anime_rule must be enabled and apply to 'tv'."""
        assert test_config.anime_rule.enabled
        assert test_config.anime_rule.applies_to == "tv"
        assert test_config.anime_rule.maps_to == CID.ANIME

    def test_genre_mapping_tmdb_movies(self, test_config):
        """Genre mapping for TMDB movies must map animation and documentary."""
        assert test_config.genre_mapping.tmdb_movies[16] == CID.MOVIES_ANIMATION
        assert test_config.genre_mapping.tmdb_movies[99] == CID.MOVIES_DOCUMENTARY

    def test_genre_mapping_tvdb_anime(self, test_config):
        """TVDB genre 27 (Anime) must map to anime."""
        assert test_config.genre_mapping.tvdb[27] == CID.ANIME

    def test_disks_accept_expected_categories(self, test_config):
        """drive_a must accept movies, tv_shows, anime."""
        drive_a = test_config.disk_by_id("drive_a")
        assert drive_a is not None
        assert CID.MOVIES in drive_a.categories
        assert CID.TV_SHOWS in drive_a.categories
        assert CID.ANIME in drive_a.categories

    def test_drive_c_accepts_standup_and_theater(self, test_config):
        """drive_c must accept standup and theater categories."""
        drive_c = test_config.disk_by_id("drive_c")
        assert drive_c is not None
        assert CID.STANDUP in drive_c.categories
        assert CID.THEATER in drive_c.categories

    def test_all_categories_covered_by_some_disk(self, test_config):
        """Every builtin category ID must be accepted by at least one disk."""
        for cid in CID.BUILTIN_CATEGORY_IDS:
            accepting = test_config.disks_accepting(cid)
            assert accepting, f"No disk accepts category '{cid}'"
