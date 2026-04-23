"""Unit tests for personalscraper.conf.classifier.

Covers all six classification priority levels:
1. NFO override (_read_nfo_category + classify level 1)
2. category_rules (classify level 2, all pattern types)
3. anime_rule (classify level 3)
4. genre_mapping IDs (classify level 4 — tmdb_movies, tmdb_tv, tvdb)
5. Defaults (classify level 5)
6. No-match sentinel (classify level 6)
"""

import textwrap
from pathlib import Path

import pytest

from personalscraper.conf.classifier import _read_nfo_category, classify
from personalscraper.conf.models import AnimeRule, CategoryRule, Config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_nfo(tmp_path: Path, content: str, name: str = "media.nfo") -> Path:
    """Write an NFO XML file and return its path.

    Args:
        tmp_path: Temp directory for the file.
        content: XML string to write.
        name: Filename within tmp_path.

    Returns:
        Path to the written NFO file.
    """
    nfo = tmp_path / name
    nfo.write_text(content, encoding="utf-8")
    return nfo


# ---------------------------------------------------------------------------
# Tests: _read_nfo_category
# ---------------------------------------------------------------------------


class TestReadNfoCategory:
    """Tests for the low-level _read_nfo_category helper."""

    def test_element_with_source_attribute(self, tmp_path: Path) -> None:
        """Element with source='personalscraper' is returned first."""
        nfo = _write_nfo(
            tmp_path,
            textwrap.dedent("""\
                <movie>
                  <category source="personalscraper">anime</category>
                </movie>
            """),
        )
        assert _read_nfo_category(nfo) == "anime"

    def test_element_without_source_attribute(self, tmp_path: Path) -> None:
        """Legacy bare <category> element (no source attr) is returned as fallback."""
        nfo = _write_nfo(
            tmp_path,
            textwrap.dedent("""\
                <movie>
                  <category>movies</category>
                </movie>
            """),
        )
        assert _read_nfo_category(nfo) == "movies"

    def test_source_attribute_takes_priority_over_bare(self, tmp_path: Path) -> None:
        """Source-attributed element takes priority when both types are present."""
        nfo = _write_nfo(
            tmp_path,
            textwrap.dedent("""\
                <movie>
                  <category>old_label</category>
                  <category source="personalscraper">tv_shows</category>
                </movie>
            """),
        )
        assert _read_nfo_category(nfo) == "tv_shows"

    def test_multiple_elements_bare_returns_first(self, tmp_path: Path) -> None:
        """When multiple bare elements exist, the first non-empty one is returned."""
        nfo = _write_nfo(
            tmp_path,
            textwrap.dedent("""\
                <movie>
                  <category>movies</category>
                  <category>anime</category>
                </movie>
            """),
        )
        assert _read_nfo_category(nfo) == "movies"

    def test_invalid_nfo_returns_none(self, tmp_path: Path) -> None:
        """Malformed XML returns None without raising."""
        nfo = _write_nfo(tmp_path, "<<not valid xml>>")
        assert _read_nfo_category(nfo) is None

    def test_empty_element_skipped(self, tmp_path: Path) -> None:
        """Empty <category/> or <category></category> elements are skipped."""
        nfo = _write_nfo(
            tmp_path,
            textwrap.dedent("""\
                <movie>
                  <category></category>
                  <category source="personalscraper"></category>
                </movie>
            """),
        )
        assert _read_nfo_category(nfo) is None

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        """Non-existent NFO path returns None without raising."""
        assert _read_nfo_category(tmp_path / "nonexistent.nfo") is None

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        """Text content is stripped of surrounding whitespace."""
        nfo = _write_nfo(
            tmp_path,
            textwrap.dedent("""\
                <movie>
                  <category source="personalscraper">  anime  </category>
                </movie>
            """),
        )
        assert _read_nfo_category(nfo) == "anime"


# ---------------------------------------------------------------------------
# Tests: classify — Level 1 (NFO override)
# ---------------------------------------------------------------------------


class TestClassifyNfoOverride:
    """Tests for classify() level 1: NFO <category> override."""

    def test_valid_nfo_id_returns_nfo_override(self, test_config: Config, tmp_path: Path) -> None:
        """Valid known category_id in NFO returns immediately with 'nfo_override' reason."""
        nfo = _write_nfo(
            tmp_path,
            '<movie><category source="personalscraper">anime</category></movie>',
        )
        cid, reason = classify(test_config, media_type="tv", nfo_path=nfo)
        assert cid == "anime"
        assert reason == "nfo_override"

    def test_obsolete_nfo_id_falls_through(self, test_config: Config, tmp_path: Path) -> None:
        """Unknown NFO category_id logs a warning and falls through to next levels."""
        nfo = _write_nfo(
            tmp_path,
            '<movie><category source="personalscraper">old_category_id</category></movie>',
        )
        # With no other signals, should fall to default_tv
        cid, reason = classify(test_config, media_type="tv", nfo_path=nfo)
        assert cid == "tv_shows"
        assert reason == "default_tv"

    def test_obsolete_nfo_id_logs_warning(
        self, test_config: Config, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Unknown NFO category_id produces a WARNING log entry."""
        import logging

        nfo = _write_nfo(
            tmp_path,
            '<movie><category source="personalscraper">invalid_id</category></movie>',
        )
        with caplog.at_level(logging.WARNING, logger="personalscraper.conf.classifier"):
            classify(test_config, media_type="movie", nfo_path=nfo)
        assert any("invalid_id" in record.message for record in caplog.records)

    def test_absent_nfo_falls_through(self, test_config: Config, tmp_path: Path) -> None:
        """If nfo_path does not exist, level 1 is skipped entirely."""
        cid, reason = classify(
            test_config,
            media_type="movie",
            nfo_path=tmp_path / "missing.nfo",
        )
        # With no genre signals, should fall to default_movies
        assert cid == "movies"
        assert reason == "default_movies"

    def test_none_nfo_path_skips_level1(self, test_config: Config) -> None:
        """nfo_path=None skips level 1 without error."""
        cid, reason = classify(test_config, media_type="movie", nfo_path=None)
        assert reason == "default_movies"


# ---------------------------------------------------------------------------
# Tests: classify — Level 2 (category_rules)
# ---------------------------------------------------------------------------


class TestClassifyCategoryRules:
    """Tests for classify() level 2: pattern-based category_rules."""

    def _config_with_rules(self, test_config: Config, *rules: CategoryRule) -> Config:
        """Return a copy of test_config with extra category_rules prepended.

        Args:
            test_config: The base config fixture.
            *rules: CategoryRule instances to prepend.

        Returns:
            New Config with the given rules as category_rules.
        """
        return test_config.model_copy(update={"category_rules": list(rules)})

    def test_path_contains_matches(self, test_config: Config, tmp_path: Path) -> None:
        """path_contains rule matches when substring is in path string."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(path_contains="/standup/", category="standup"),
        )
        cid, reason = classify(cfg, media_type="movie", path=tmp_path / "standup" / "show.mkv")
        assert cid == "standup"
        assert reason == "category_rules[0]"

    def test_path_contains_no_match(self, test_config: Config, tmp_path: Path) -> None:
        """path_contains rule does not match when substring is absent."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(path_contains="/standup/", category="standup"),
        )
        cid, reason = classify(cfg, media_type="movie", path=tmp_path / "other" / "movie.mkv")
        # Falls through to default
        assert cid == "movies"
        assert reason == "default_movies"

    def test_path_regex_matches(self, test_config: Config, tmp_path: Path) -> None:
        """path_regex rule matches via re.search on string path."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(path_regex=r"[Ss]tandup", category="standup"),
        )
        cid, reason = classify(cfg, media_type="movie", path=tmp_path / "Standup" / "show.mkv")
        assert cid == "standup"
        assert reason == "category_rules[0]"

    def test_title_regex_matches(self, test_config: Config) -> None:
        """title_regex rule matches via re.search on title string."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(title_regex=r"(?i)stand.?up", category="standup"),
        )
        cid, reason = classify(cfg, media_type="movie", title="Best Stand Up 2024")
        assert cid == "standup"
        assert reason == "category_rules[0]"

    def test_title_regex_no_title_does_not_match(self, test_config: Config) -> None:
        """title_regex rule does not match when title is None."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(title_regex=r"standup", category="standup"),
        )
        cid, _ = classify(cfg, media_type="movie", title=None)
        assert cid != "standup"

    def test_tmdb_genre_contains_matches_case_insensitive(self, test_config: Config) -> None:
        """tmdb_genre_contains matches case-insensitively anywhere in genre string."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(tmdb_genre_contains="documentary", category="movies_documentary"),
        )
        cid, reason = classify(
            cfg,
            media_type="movie",
            tmdb_genres=["Documentary", "Drama"],
        )
        assert cid == "movies_documentary"
        assert reason == "category_rules[0]"

    def test_tmdb_genre_contains_lowercase_genre(self, test_config: Config) -> None:
        """tmdb_genre_contains matches even when genre is fully lowercase."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(tmdb_genre_contains="documentary", category="movies_documentary"),
        )
        cid, _ = classify(cfg, media_type="movie", tmdb_genres=["documentary"])
        assert cid == "movies_documentary"

    def test_tmdb_keyword_matches(self, test_config: Config) -> None:
        """tmdb_keyword rule matches when keyword is in tmdb_keywords list."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(tmdb_keyword=["stand-up-comedy"], category="standup"),
        )
        cid, reason = classify(
            cfg,
            media_type="movie",
            tmdb_keywords=["comedy", "stand-up-comedy"],
        )
        assert cid == "standup"
        assert reason == "category_rules[0]"

    def test_tmdb_keyword_no_match(self, test_config: Config) -> None:
        """tmdb_keyword rule does not match when keyword is absent."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(tmdb_keyword=["stand-up-comedy"], category="standup"),
        )
        cid, _ = classify(
            cfg,
            media_type="movie",
            tmdb_keywords=["comedy"],
        )
        assert cid != "standup"

    def test_first_match_wins(self, test_config: Config) -> None:
        """When multiple rules could match, the first one in list wins."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(path_contains="/standup/", category="standup"),
            CategoryRule(path_contains="/standup/", category="theater"),
        )
        cid, reason = classify(
            cfg,
            media_type="movie",
            path=Path("/media/standup/show.mkv"),
        )
        assert cid == "standup"
        assert reason == "category_rules[0]"

    def test_applies_to_movie_skips_tv(self, test_config: Config) -> None:
        """Rule with applies_to='movie' is not evaluated for TV media."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(
                path_contains="/standup/",
                category="standup",
                applies_to="movie",
            ),
        )
        cid, _ = classify(
            cfg,
            media_type="tv",
            path=Path("/media/standup/show.mkv"),
        )
        # Rule skipped for TV; falls to default_tv
        assert cid == "tv_shows"

    def test_applies_to_tv_skips_movie(self, test_config: Config) -> None:
        """Rule with applies_to='tv' is not evaluated for movie media."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(
                tmdb_genre_contains="animation",
                category="anime",
                applies_to="tv",
            ),
        )
        cid, _ = classify(
            cfg,
            media_type="movie",
            tmdb_genres=["Animation"],
        )
        # Rule skipped for movies; falls to genre_mapping tmdb_movies[16] if no IDs,
        # then default
        assert cid != "anime"

    def test_applies_to_both_matches_any_type(self, test_config: Config) -> None:
        """Rule with applies_to='both' (default) is evaluated for any media type."""
        cfg = self._config_with_rules(
            test_config,
            CategoryRule(path_contains="/standup/", category="standup", applies_to="both"),
        )
        for media_type in ("movie", "tv"):
            cid, reason = classify(
                cfg,
                media_type=media_type,  # type: ignore[arg-type]
                path=Path("/media/standup/s01.mkv"),
            )
            assert cid == "standup", f"Expected standup for media_type={media_type}"


# ---------------------------------------------------------------------------
# Tests: classify — Level 3 (anime_rule)
# ---------------------------------------------------------------------------


class TestClassifyAnimeRule:
    """Tests for classify() level 3: anime_rule."""

    def test_tv_anime_jp_with_genre_id(self, test_config: Config) -> None:
        """TV + Animation genre_id 16 + JP origin triggers anime_rule."""
        cid, reason = classify(
            test_config,
            media_type="tv",
            tmdb_genre_ids=[16],
            origin_country=["JP"],
        )
        assert cid == "anime"
        assert reason == "anime_rule"

    def test_tv_animation_non_jp_falls_through(self, test_config: Config) -> None:
        """TV + Animation genre_id 16 + non-JP origin does NOT trigger anime_rule."""
        cid, reason = classify(
            test_config,
            media_type="tv",
            tmdb_genre_ids=[16],
            origin_country=["US"],
        )
        # anime_rule skipped → falls to genre_mapping tmdb_tv[16] = tv_shows_animation
        assert cid == "tv_shows_animation"
        assert "genre_mapping" in reason

    def test_tv_animation_no_country_falls_through(self, test_config: Config) -> None:
        """TV + Animation genre_id 16 + no origin country does NOT trigger anime_rule."""
        cid, _ = classify(
            test_config,
            media_type="tv",
            tmdb_genre_ids=[16],
            origin_country=None,
        )
        assert cid == "tv_shows_animation"

    def test_disabled_anime_rule_is_skipped(self, test_config: Config) -> None:
        """When anime_rule.enabled is False, level 3 is entirely skipped."""
        cfg = test_config.model_copy(update={"anime_rule": AnimeRule(enabled=False, maps_to="anime")})
        cid, reason = classify(
            cfg,
            media_type="tv",
            tmdb_genre_ids=[16],
            origin_country=["JP"],
        )
        # anime_rule disabled → falls to genre_mapping tmdb_tv[16]
        assert cid == "tv_shows_animation"

    def test_applies_to_movie_only_skips_tv(self, test_config: Config) -> None:
        """anime_rule with applies_to='movie' is skipped for TV media."""
        cfg = test_config.model_copy(
            update={
                "anime_rule": AnimeRule(
                    enabled=True,
                    applies_to="movie",
                    maps_to="anime",
                )
            }
        )
        cid, _ = classify(
            cfg,
            media_type="tv",
            tmdb_genre_ids=[16],
            origin_country=["JP"],
        )
        # Rule skipped for TV → genre_mapping
        assert cid == "tv_shows_animation"

    def test_applies_to_movies_legacy_normalized(self, test_config: Config) -> None:
        """Legacy 'movies' (plural) is normalized to 'movie' for backward compat."""
        cfg = test_config.model_copy(
            update={
                "anime_rule": AnimeRule(
                    enabled=True,
                    applies_to="movies",  # type: ignore[arg-type]  # legacy plural, normalized by validator
                    requires_genre_id=16,
                    requires_origin_country=["JP"],
                    maps_to="anime",
                )
            }
        )
        # Rule fires for movie (would be a no-op before the normalization fix)
        cid, reason = classify(
            cfg,
            media_type="movie",
            tmdb_genre_ids=[16],
            origin_country=["JP"],
        )
        assert cid == "anime"
        assert reason == "anime_rule"

    def test_applies_to_both_fires_for_movie(self, test_config: Config) -> None:
        """anime_rule with applies_to='both' fires for movie + Animation + JP."""
        cfg = test_config.model_copy(
            update={
                "anime_rule": AnimeRule(
                    enabled=True,
                    applies_to="both",
                    requires_genre_id=16,
                    requires_origin_country=["JP"],
                    maps_to="anime",
                )
            }
        )
        cid, reason = classify(
            cfg,
            media_type="movie",
            tmdb_genre_ids=[16],
            origin_country=["JP"],
        )
        assert cid == "anime"
        assert reason == "anime_rule"


# ---------------------------------------------------------------------------
# Tests: classify — Level 4 (genre_mapping)
# ---------------------------------------------------------------------------


class TestClassifyGenreMapping:
    """Tests for classify() level 4: genre_mapping IDs."""

    # Movies

    def test_movie_tmdb_animation_id(self, test_config: Config) -> None:
        """TMDB movie genre_id 16 (Animation) → movies_animation."""
        cid, reason = classify(test_config, media_type="movie", tmdb_genre_ids=[16])
        assert cid == "movies_animation"
        assert "tmdb_movies[16]" in reason

    def test_movie_tmdb_documentary_id(self, test_config: Config) -> None:
        """TMDB movie genre_id 99 (Documentary) → movies_documentary."""
        cid, _ = classify(test_config, media_type="movie", tmdb_genre_ids=[99])
        assert cid == "movies_documentary"

    def test_movie_tmdb_first_match_wins(self, test_config: Config) -> None:
        """When multiple genre IDs present, first matching ID wins."""
        # Animation (16) comes before Documentary (99) in the list
        cid, _ = classify(test_config, media_type="movie", tmdb_genre_ids=[16, 99])
        assert cid == "movies_animation"

    def test_movie_unmapped_id_falls_to_default(self, test_config: Config) -> None:
        """Unmapped TMDB movie genre_id (e.g. Drama=18) falls to default_movies."""
        cid, reason = classify(test_config, media_type="movie", tmdb_genre_ids=[18])
        assert cid == "movies"
        assert reason == "default_movies"

    # TV — TMDB

    def test_tv_tmdb_animation_id(self, test_config: Config) -> None:
        """TMDB TV genre_id 16 (Animation, no JP) → tv_shows_animation."""
        cid, _ = classify(
            test_config,
            media_type="tv",
            tmdb_genre_ids=[16],
            origin_country=["US"],
        )
        assert cid == "tv_shows_animation"

    def test_tv_tmdb_documentary_id(self, test_config: Config) -> None:
        """TMDB TV genre_id 99 (Documentary) → tv_shows_documentary."""
        cid, reason = classify(test_config, media_type="tv", tmdb_genre_ids=[99])
        assert cid == "tv_shows_documentary"
        assert "tmdb_tv[99]" in reason

    def test_tv_tmdb_reality_id(self, test_config: Config) -> None:
        """TMDB TV genre_id 10764 (Reality) → tv_programs."""
        cid, _ = classify(test_config, media_type="tv", tmdb_genre_ids=[10764])
        assert cid == "tv_programs"

    def test_tv_tmdb_talk_id(self, test_config: Config) -> None:
        """TMDB TV genre_id 10767 (Talk) → tv_programs."""
        cid, _ = classify(test_config, media_type="tv", tmdb_genre_ids=[10767])
        assert cid == "tv_programs"

    def test_tv_tmdb_news_id(self, test_config: Config) -> None:
        """TMDB TV genre_id 10763 (News) → tv_programs."""
        cid, _ = classify(test_config, media_type="tv", tmdb_genre_ids=[10763])
        assert cid == "tv_programs"

    # TV — TVDB

    def test_tv_tvdb_anime_id(self, test_config: Config) -> None:
        """TVDB genre_id 27 (Anime) → anime."""
        cid, reason = classify(test_config, media_type="tv", tvdb_genre_ids=[27])
        assert cid == "anime"
        assert "tvdb[27]" in reason

    def test_tv_tvdb_animation_id(self, test_config: Config) -> None:
        """TVDB genre_id 17 (Animation) → tv_shows_animation."""
        cid, _ = classify(test_config, media_type="tv", tvdb_genre_ids=[17])
        assert cid == "tv_shows_animation"

    def test_tv_tvdb_documentary_id(self, test_config: Config) -> None:
        """TVDB genre_id 3 (Documentary) → tv_shows_documentary."""
        cid, _ = classify(test_config, media_type="tv", tvdb_genre_ids=[3])
        assert cid == "tv_shows_documentary"

    def test_tv_tvdb_beats_tmdb(self, test_config: Config) -> None:
        """TVDB IDs take priority over TMDB IDs for TV shows (level 4 ordering)."""
        # TVDB 27 (anime) should win over TMDB 99 (tv_shows_documentary)
        cid, reason = classify(
            test_config,
            media_type="tv",
            tvdb_genre_ids=[27],
            tmdb_genre_ids=[99],
        )
        assert cid == "anime"
        assert "tvdb" in reason

    def test_tv_tmdb_used_when_no_tvdb(self, test_config: Config) -> None:
        """When tvdb_genre_ids is None, TMDB TV IDs are used."""
        cid, reason = classify(
            test_config,
            media_type="tv",
            tvdb_genre_ids=None,
            tmdb_genre_ids=[99],
        )
        assert cid == "tv_shows_documentary"
        assert "tmdb_tv[99]" in reason


# ---------------------------------------------------------------------------
# Tests: classify — Level 5 (defaults) and Level 6 (no_match)
# ---------------------------------------------------------------------------


class TestClassifyDefaults:
    """Tests for classify() levels 5-6: defaults and no-match sentinel."""

    def test_movie_no_signals_returns_default_movies(self, test_config: Config) -> None:
        """Movie with no matching signals returns default_movies_category."""
        cid, reason = classify(test_config, media_type="movie")
        assert cid == "movies"
        assert reason == "default_movies"

    def test_tv_no_signals_returns_default_tv(self, test_config: Config) -> None:
        """TV show with no matching signals returns default_tv_category."""
        cid, reason = classify(test_config, media_type="tv")
        assert cid == "tv_shows"
        assert reason == "default_tv"

    def test_movie_empty_genre_ids_returns_default(self, test_config: Config) -> None:
        """Empty tmdb_genre_ids list (not None) still falls to default."""
        cid, reason = classify(test_config, media_type="movie", tmdb_genre_ids=[])
        assert cid == "movies"
        assert reason == "default_movies"

    def test_tv_empty_ids_returns_default(self, test_config: Config) -> None:
        """Empty genre ID lists still fall to default."""
        cid, reason = classify(
            test_config,
            media_type="tv",
            tmdb_genre_ids=[],
            tvdb_genre_ids=[],
        )
        assert cid == "tv_shows"
        assert reason == "default_tv"
