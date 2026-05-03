"""Tests for personalscraper.conf.models Pydantic schema."""

import pytest
from pydantic import ValidationError

from personalscraper.conf import ids as CID
from personalscraper.conf.models import (
    CategoryConfig,
    CategoryRule,
    Config,
    DiskConfig,
    EncodingRule,
    GenreMapping,
    PathConfig,
    RuleCriteria,
    SubtitlePrefs,
    VideoPrefs,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_config(tmp_path):
    """Build the minimal valid Config for testing.

    Args:
        tmp_path: Pytest tmp_path fixture value.

    Returns:
        A valid Config instance with one disk accepting all builtin categories.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "complete",
            staging_dir=tmp_path / "staging",
        ),
        disks=[
            DiskConfig(
                id="disk_a",
                path=tmp_path / "disk_a",
                categories=list(CID.BUILTIN_CATEGORY_IDS),
            )
        ],
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


# ---------------------------------------------------------------------------
# CategoryConfig
# ---------------------------------------------------------------------------


class TestCategoryConfig:
    """Tests for CategoryConfig model."""

    def test_default_for(self):
        """default_for should produce folder_name with spaces instead of underscores."""
        cfg = CategoryConfig.default_for("tv_shows_animation")
        assert cfg.folder_name == "tv shows animation"
        assert cfg.aliases == []

    def test_valid_with_aliases(self):
        """CategoryConfig with aliases should parse correctly."""
        cfg = CategoryConfig(folder_name="Films", aliases=["movies", "film"])
        assert cfg.aliases == ["movies", "film"]

    def test_extra_fields_forbidden(self):
        """Unknown fields must raise ValidationError."""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            CategoryConfig(folder_name="Films", unknown_key="x")  # type: ignore[call-arg]

    def test_folder_name_empty_rejected(self):
        """Empty folder_name must be rejected."""
        with pytest.raises(ValidationError):
            CategoryConfig(folder_name="")


# ---------------------------------------------------------------------------
# DiskConfig
# ---------------------------------------------------------------------------


class TestDiskConfig:
    """Tests for DiskConfig model."""

    def test_valid(self, tmp_path):
        """Valid DiskConfig should parse without error."""
        disk = DiskConfig(
            id="nas_main",
            path=tmp_path / "nas",
            categories=[CID.MOVIES, CID.TV_SHOWS],
        )
        assert disk.id == "nas_main"

    def test_id_pattern_invalid(self, tmp_path):
        """Disk IDs not matching pattern must be rejected."""
        with pytest.raises(ValidationError, match="String should match pattern"):
            DiskConfig(id="Disk-A", path=tmp_path, categories=[CID.MOVIES])

    def test_empty_categories_rejected(self, tmp_path):
        """Empty categories list must be rejected (min_length=1)."""
        with pytest.raises(ValidationError):
            DiskConfig(id="disk_a", path=tmp_path, categories=[])


# ---------------------------------------------------------------------------
# CategoryRule
# ---------------------------------------------------------------------------


class TestCategoryRule:
    """Tests for CategoryRule exactly-one-pattern validator."""

    def test_valid_path_contains(self):
        """Rule with path_contains should be valid."""
        rule = CategoryRule(path_contains="/standup/", category=CID.STANDUP)
        assert rule.path_contains == "/standup/"

    def test_valid_tmdb_keyword(self):
        """Rule with non-empty tmdb_keyword list should be valid."""
        rule = CategoryRule(tmdb_keyword=["stand-up"], category=CID.STANDUP)
        assert rule.tmdb_keyword == ["stand-up"]

    def test_zero_patterns_rejected(self):
        """Rule with no match pattern must be rejected."""
        with pytest.raises(ValidationError, match="exactly one"):
            CategoryRule(category=CID.STANDUP)

    def test_two_patterns_rejected(self):
        """Rule with two match patterns must be rejected."""
        with pytest.raises(ValidationError, match="exactly one"):
            CategoryRule(
                path_contains="/foo/",
                title_regex="bar",
                category=CID.STANDUP,
            )

    def test_empty_string_treated_as_not_set(self):
        """Empty string for path_contains should count as not set."""
        with pytest.raises(ValidationError, match="exactly one"):
            # Both path_contains="" (not set) and title_regex unset → 0 patterns
            CategoryRule(path_contains="", category=CID.STANDUP)

    def test_empty_list_treated_as_not_set(self):
        """Empty list for tmdb_keyword should count as not set."""
        with pytest.raises(ValidationError, match="exactly one"):
            CategoryRule(tmdb_keyword=[], category=CID.STANDUP)


# ---------------------------------------------------------------------------
# PathConfig
# ---------------------------------------------------------------------------


class TestPathConfig:
    """Tests for PathConfig field validator."""

    def test_relative_path_resolved(self, tmp_path, monkeypatch):
        """Relative paths must be resolved to absolute.

        Pydantic accepts a ``str`` and coerces it to ``Path`` at runtime;
        the type ignore acknowledges that we're testing the coercion path
        explicitly.
        """
        monkeypatch.chdir(tmp_path)
        cfg = PathConfig(
            torrent_complete_dir="./complete",  # type: ignore[arg-type]
            staging_dir="./staging",  # type: ignore[arg-type]
        )
        assert cfg.torrent_complete_dir.is_absolute()
        assert cfg.staging_dir.is_absolute()

    def test_absolute_path_unchanged(self, tmp_path):
        """Absolute paths must remain as-is (minus symlink resolution)."""
        cfg = PathConfig(
            torrent_complete_dir=tmp_path / "complete",
            staging_dir=tmp_path / "staging",
        )
        assert cfg.torrent_complete_dir == (tmp_path / "complete").resolve()


# ---------------------------------------------------------------------------
# VideoPrefs
# ---------------------------------------------------------------------------


class TestVideoPrefs:
    """Tests for VideoPrefs model."""

    def test_default_values(self):
        """Default VideoPrefs should have expected codec values."""
        vp = VideoPrefs()
        assert vp.preferred_codec == "hevc"
        assert "av1" in vp.fallback_codecs
        assert "mpeg2" in vp.rejected_codecs

    def test_codec_overlap_rejected(self):
        """Overlap between fallback and rejected codecs must be rejected."""
        with pytest.raises(ValidationError, match="Codec sets overlap"):
            VideoPrefs(preferred_codec="hevc", fallback_codecs=["h264"], rejected_codecs=["h264"])


# ---------------------------------------------------------------------------
# SubtitlePrefs
# ---------------------------------------------------------------------------


class TestSubtitlePrefs:
    """Tests for SubtitlePrefs model."""

    def test_required_languages_default(self):
        """required_languages defaults to French subtitles."""
        assert SubtitlePrefs().required_languages == ["fra"]


# ---------------------------------------------------------------------------
# RuleCriteria / EncodingRule
# ---------------------------------------------------------------------------


class TestRuleCriteria:
    """Tests for RuleCriteria model."""

    def test_all_none_rejected(self):
        """RuleCriteria with all None fields must be rejected."""
        with pytest.raises(ValidationError, match="at least one"):
            RuleCriteria()

    def test_valid(self):
        """RuleCriteria with one field set should be valid."""
        rc = RuleCriteria(genre="Animation")
        assert rc.genre == "Animation"


class TestEncodingRule:
    """Tests for EncodingRule model."""

    def test_no_target_rejected(self):
        """EncodingRule with no target fields must be rejected."""
        with pytest.raises(ValidationError, match="at least one target"):
            EncodingRule(criteria=RuleCriteria(genre="Animation"))

    def test_valid(self):
        """EncodingRule with one target should be valid."""
        er = EncodingRule(criteria=RuleCriteria(genre="Animation"), codec="hevc")
        assert er.codec == "hevc"


# ---------------------------------------------------------------------------
# Config — validators and methods
# ---------------------------------------------------------------------------


class TestConfigValidCustomIds:
    """Tests for Config._validate_custom_ids."""

    def test_valid_custom_id(self, tmp_path):
        """Valid custom ID should be accepted."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES, "my_custom"])],
            custom_categories=["my_custom"],
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        assert "my_custom" in cfg.all_category_ids

    def test_invalid_pattern_rejected(self, tmp_path):
        """Custom ID with invalid pattern must be rejected."""
        with pytest.raises(ValidationError, match="Invalid custom category ID"):
            Config(
                paths=PathConfig(
                    torrent_complete_dir=tmp_path / "c",
                    staging_dir=tmp_path / "s",
                ),
                disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
                custom_categories=["Bad-ID"],
                staging_dirs=CANONICAL_STAGING_DIRS,
            )

    def test_builtin_collision_rejected(self, tmp_path):
        """Custom ID matching a builtin must be rejected."""
        with pytest.raises(ValidationError, match="conflicts with builtin"):
            Config(
                paths=PathConfig(
                    torrent_complete_dir=tmp_path / "c",
                    staging_dir=tmp_path / "s",
                ),
                disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
                custom_categories=[CID.MOVIES],
                staging_dirs=CANONICAL_STAGING_DIRS,
            )


class TestConfigCrossReferences:
    """Tests for Config._validate_cross_references."""

    def test_unknown_category_in_categories_dict(self, tmp_path):
        """Unknown category ID in categories dict must be rejected."""
        with pytest.raises(ValidationError, match="Unknown category IDs in 'categories'"):
            Config(
                paths=PathConfig(
                    torrent_complete_dir=tmp_path / "c",
                    staging_dir=tmp_path / "s",
                ),
                disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
                categories={"ghost_id": CategoryConfig(folder_name="Ghost")},
                staging_dirs=CANONICAL_STAGING_DIRS,
            )

    def test_unknown_category_in_disk(self, tmp_path):
        """Unknown category ID referenced by a disk must be rejected."""
        with pytest.raises(ValidationError, match="unknown categories"):
            Config(
                paths=PathConfig(
                    torrent_complete_dir=tmp_path / "c",
                    staging_dir=tmp_path / "s",
                ),
                disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=["ghost_id"])],
                staging_dirs=CANONICAL_STAGING_DIRS,
            )

    def test_duplicate_disk_ids_rejected(self, tmp_path):
        """Duplicate disk IDs must be rejected."""
        with pytest.raises(ValidationError, match="Duplicate disk IDs"):
            Config(
                paths=PathConfig(
                    torrent_complete_dir=tmp_path / "c",
                    staging_dir=tmp_path / "s",
                ),
                disks=[
                    DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES]),
                    DiskConfig(id="disk_a", path=tmp_path / "b", categories=[CID.TV_SHOWS]),
                ],
                staging_dirs=CANONICAL_STAGING_DIRS,
            )

    def test_genre_mapping_unknown_category(self, tmp_path):
        """genre_mapping referencing an unknown category must be rejected."""
        with pytest.raises(ValidationError, match="unknown categories"):
            Config(
                paths=PathConfig(
                    torrent_complete_dir=tmp_path / "c",
                    staging_dir=tmp_path / "s",
                ),
                disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
                genre_mapping=GenreMapping(tmdb_movies={16: "ghost_id"}),
                staging_dirs=CANONICAL_STAGING_DIRS,
            )

    def test_category_rules_unknown_category(self, tmp_path):
        """category_rules referencing an unknown category must be rejected."""
        with pytest.raises(ValidationError, match="unknown"):
            Config(
                paths=PathConfig(
                    torrent_complete_dir=tmp_path / "c",
                    staging_dir=tmp_path / "s",
                ),
                disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
                category_rules=[CategoryRule(path_contains="/foo/", category="ghost_id")],
                staging_dirs=CANONICAL_STAGING_DIRS,
            )

    def test_extra_field_forbidden(self, tmp_path):
        """Unknown top-level config fields must be rejected."""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            Config(
                paths=PathConfig(
                    torrent_complete_dir=tmp_path / "c",
                    staging_dir=tmp_path / "s",
                ),
                disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
                unknown_key="surprise",  # type: ignore[call-arg]
                staging_dirs=CANONICAL_STAGING_DIRS,
            )


class TestConfigMethods:
    """Tests for Config lookup methods."""

    def test_category_with_config(self, tmp_path):
        """category() should return configured CategoryConfig when present."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
            categories={CID.MOVIES: CategoryConfig(folder_name="Films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        assert cfg.category(CID.MOVIES).folder_name == "Films"

    def test_category_fallback_default(self, tmp_path):
        """category() should fall back to default_label when not in categories dict."""
        cfg = _minimal_config(tmp_path)
        assert cfg.category(CID.TV_SHOWS_ANIMATION).folder_name == "tv shows animation"

    def test_disk_by_id_found(self, tmp_path):
        """disk_by_id() should return the disk when ID exists."""
        cfg = _minimal_config(tmp_path)
        disk = cfg.disk_by_id("disk_a")
        assert disk is not None
        assert disk.id == "disk_a"

    def test_disk_by_id_not_found(self, tmp_path):
        """disk_by_id() should return None for unknown IDs."""
        cfg = _minimal_config(tmp_path)
        assert cfg.disk_by_id("nonexistent") is None

    def test_disks_accepting(self, tmp_path):
        """disks_accepting() should return matching disks."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[
                DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES]),
                DiskConfig(id="disk_b", path=tmp_path / "b", categories=[CID.TV_SHOWS]),
            ],
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        result = cfg.disks_accepting(CID.MOVIES)
        assert len(result) == 1
        assert result[0].id == "disk_a"

    def test_disks_accepting_many_to_one_allowed(self, tmp_path):
        """Multiple disks can accept the same category."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[
                DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES]),
                DiskConfig(id="disk_b", path=tmp_path / "b", categories=[CID.MOVIES]),
            ],
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        result = cfg.disks_accepting(CID.MOVIES)
        assert len(result) == 2

    def test_resolve_category_alias_by_id(self, tmp_path):
        """resolve_category_alias() should accept a valid ID directly."""
        cfg = _minimal_config(tmp_path)
        assert cfg.resolve_category_alias(CID.MOVIES) == CID.MOVIES

    def test_resolve_category_alias_by_alias(self, tmp_path):
        """resolve_category_alias() should resolve via aliases list."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES])],
            categories={CID.MOVIES: CategoryConfig(folder_name="Films", aliases=["films", "movie"])},
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        assert cfg.resolve_category_alias("films") == CID.MOVIES
        assert cfg.resolve_category_alias("movie") == CID.MOVIES

    def test_resolve_category_alias_unknown(self, tmp_path):
        """resolve_category_alias() should return None for unknown inputs."""
        cfg = _minimal_config(tmp_path)
        assert cfg.resolve_category_alias("ghost") is None

    def test_all_category_ids_includes_custom(self, tmp_path):
        """all_category_ids should include custom IDs."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "c",
                staging_dir=tmp_path / "s",
            ),
            disks=[DiskConfig(id="disk_a", path=tmp_path / "a", categories=[CID.MOVIES, "my_custom"])],
            custom_categories=["my_custom"],
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        assert "my_custom" in cfg.all_category_ids
        assert CID.MOVIES in cfg.all_category_ids


# ---------------------------------------------------------------------------
# TrailersConfig and nested models
# ---------------------------------------------------------------------------


class TestTrailersConfig:
    """Tests for TrailersConfig and nested Pydantic models."""

    def test_trailers_config_defaults_to_disabled(self):
        """TrailersConfig defaults to enabled=False when not present in config.json5."""
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert cfg.enabled is False

    def test_trailers_config_languages_default(self):
        """TrailersConfig.languages defaults to ['fr-FR', 'en-US']."""
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert cfg.languages == ["fr-FR", "en-US"]

    def test_trailers_config_retry_after_days_default(self):
        """TrailersConfig.retry_after_days defaults to [1, 7, 30]."""
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert cfg.retry_after_days == [1, 7, 30]

    def test_trailers_config_state_file_default(self):
        """TrailersConfig.state_file defaults to None (resolved at Config level)."""
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert cfg.state_file is None

    def test_trailers_filters_defaults(self):
        """TrailersFiltersConfig defaults match the runtime trailer gates."""
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert cfg.filters.min_file_size_bytes == 102400
        assert cfg.filters.max_filesize_mb == 500
        assert set(cfg.filters.allowed_extensions) == {"mp4", "mkv", "webm"}

    def test_trailers_ytdlp_defaults(self):
        """TrailersYtdlpConfig defaults match the runtime downloader settings."""
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert "height<=1080" in cfg.ytdlp.format
        assert cfg.ytdlp.socket_timeout_sec == 30
        assert cfg.ytdlp.retries == 3

    def test_trailers_two_circuit_breakers(self):
        """Two distinct breakers prevent YouTube failures from tripping TMDB."""
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert cfg.circuit_breakers.tmdb_videos.errors_threshold == 5
        assert cfg.circuit_breakers.tmdb_videos.cooldown_sec == 1800
        assert cfg.circuit_breakers.youtube.errors_threshold == 5
        assert cfg.circuit_breakers.youtube.cooldown_sec == 3600

    def test_trailers_youtube_api_defaults(self):
        """YouTube Data API v3 quota accounting defaults."""
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert cfg.youtube_api.daily_quota_units == 10_000
        assert cfg.youtube_api.search_list_cost_units == 100

    def test_trailers_config_has_seasons_default_disabled(self):
        """Season-level trailer download is opt-in (default off).

        Most shows lack TMDB season-level trailers; enabling by default would spam
        YouTube searches that return nothing.
        """
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert cfg.seasons.enabled is False

    def test_trailers_config_library_check_defaults(self):
        """Library-aware idempotence has per-media-type toggles.

        Defaults:
        - movies: False — films rarely get re-ingested; library scan cost unjustified.
        - tv_shows: True — new episodes of existing shows arrive frequently.
        """
        from personalscraper.conf.models import TrailersConfig

        cfg = TrailersConfig()
        assert cfg.library_check.movies is False
        assert cfg.library_check.tv_shows is True

    def test_config_trailers_field_defaults_to_disabled(self, tmp_path):
        """Config.trailers defaults to TrailersConfig() with enabled=False."""
        cfg = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "complete",
                staging_dir=tmp_path / "staging",
            ),
            disks=[DiskConfig(id="disk_a", path=tmp_path / "disk_a", categories=list(CID.BUILTIN_CATEGORY_IDS))],
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        assert cfg.trailers.enabled is False

    def test_config_without_trailers_section_is_valid(self, tmp_path):
        """Config without a trailers block parses cleanly (enabled=False by default)."""
        from personalscraper.conf.loader import load_config_dir

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        complete = str(tmp_path / "complete")
        staging = str(tmp_path / "staging")
        data = str(tmp_path / ".data")
        disk_a = str(tmp_path / "disk_a")
        (cfg_dir / "config.json5").write_text(
            '{ config_version: 2, overlays: ["paths.json5", "disks.json5", "patterns.json5"] }',
            encoding="utf-8",
        )
        (cfg_dir / "paths.json5").write_text(
            "{\n"
            f'  paths: {{ torrent_complete_dir: "{complete}", staging_dir: "{staging}", data_dir: "{data}" }},\n'
            "}",
            encoding="utf-8",
        )
        (cfg_dir / "disks.json5").write_text(
            "{\n"
            f'  disks: [{{ id: "disk_a", path: "{disk_a}", categories: ["movies", "tv_shows"] }}],\n'
            "}",
            encoding="utf-8",
        )
        (cfg_dir / "patterns.json5").write_text(
            "{\n"
            "  staging_dirs: [\n"
            '    { id: 1, name: "movies", file_type: "movie" },\n'
            '    { id: 2, name: "tvshows", file_type: "tvshow" },\n'
            '    { id: 97, name: "temp", file_type: null, role: "ingest" },\n'
            "  ],\n"
            "}",
            encoding="utf-8",
        )
        config = load_config_dir(cfg_dir)
        assert config.trailers.enabled is False

    def test_negative_circuit_breaker_threshold_rejected(self):
        """errors_threshold must be >= 1 — a 0 means the breaker would never trip OR trip on first call."""
        import pydantic

        from personalscraper.conf.models import TrailersCircuitBreakerConfig

        with pytest.raises(pydantic.ValidationError):
            TrailersCircuitBreakerConfig(errors_threshold=0, cooldown_sec=60)

    def test_zero_max_filesize_rejected(self):
        """max_filesize_mb must be > 0 (a zero cap would block every download)."""
        import pydantic

        from personalscraper.conf.models import TrailersFiltersConfig

        with pytest.raises(pydantic.ValidationError):
            TrailersFiltersConfig(max_filesize_mb=0)

    def test_empty_languages_rejected(self):
        """Languages must be non-empty so the finder always has at least one tier-1 query."""
        import pydantic

        from personalscraper.conf.models import TrailersConfig

        with pytest.raises(pydantic.ValidationError):
            TrailersConfig(languages=[])

    def test_retry_after_days_negative_element_rejected(self):
        """A negative day collapses the back-off ladder into immediate retry."""
        import pydantic

        from personalscraper.conf.models import TrailersConfig

        with pytest.raises(pydantic.ValidationError):
            TrailersConfig(retry_after_days=[-1, 7, 30])

    def test_allowed_extensions_empty_string_rejected(self):
        """An empty extension would silently disable the verify gate."""
        import pydantic

        from personalscraper.conf.models import TrailersFiltersConfig

        with pytest.raises(pydantic.ValidationError):
            TrailersFiltersConfig(allowed_extensions=["", "mp4"])

    def test_allowed_extensions_trailing_space_rejected(self):
        """A typo with trailing whitespace must fail validation, not propagate."""
        import pydantic

        from personalscraper.conf.models import TrailersFiltersConfig

        with pytest.raises(pydantic.ValidationError):
            TrailersFiltersConfig(allowed_extensions=["mp4 ", "mkv"])
