"""Tests for process/reclean.py — is_title_polluted and reclean_folders."""


from personalscraper.process.reclean import is_title_polluted


class TestIsTitlePolluted:
    """Tests for release token detection in folder names."""

    def test_raw_release_name_detected(self):
        """Full release name with codec, resolution, group → polluted."""
        assert is_title_polluted("Movie.Title.2024.1080p.BluRay.x264-GROUP") is True

    def test_avatar_neostark_detected(self):
        """Real-world case: Avatar with release group → polluted."""
        assert is_title_polluted("Avatar de feu et de cendres 7 1 neostark") is True

    def test_tvshow_release_detected(self):
        """TV show release name with resolution and group → polluted."""
        assert is_title_polluted("The.Boys.S05E01.MULTi.1080p-R3MiX") is True

    def test_clean_title_not_flagged(self):
        """Clean title 'The Matrix' → not polluted."""
        assert is_title_polluted("The Matrix") is False

    def test_scream_7_not_flagged(self):
        """Title with number 'Scream 7' → not polluted (7 is not a resolution)."""
        assert is_title_polluted("Scream 7") is False

    def test_title_with_year_not_flagged(self):
        """Clean 'Title (Year)' format → not polluted."""
        assert is_title_polluted("Shrinking (2023)") is False

    def test_2001_space_odyssey_not_flagged(self):
        """Title starting with year-like number → not polluted."""
        assert is_title_polluted("2001 A Space Odyssey") is False

    def test_jury_duty_not_flagged(self):
        """Simple clean title → not polluted."""
        assert is_title_polluted("Jury Duty") is False
