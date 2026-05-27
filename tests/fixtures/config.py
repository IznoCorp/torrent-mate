"""Synthetic test config — 3 neutral disks, builtin IDs, generic labels.

Used across test modules as a stable, filesystem-agnostic Config fixture that
exercises all 11 builtin category IDs without depending on real disk paths.
"""

from pathlib import Path

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models.categories import (
    AnimeRule,
    CategoryConfig,
    CategoryRule,
    GenreMapping,
)
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.conf.models.staging import StagingDirConfig

# ---------------------------------------------------------------------------
# Shared staging_dirs constant — import this in any test file that builds
# a Config() directly so that the now-required staging_dirs field is satisfied.
# ---------------------------------------------------------------------------

CANONICAL_STAGING_DIRS: list[StagingDirConfig] = [
    StagingDirConfig(id=1, name="movies", file_type="movie"),
    StagingDirConfig(id=2, name="tvshows", file_type="tvshow"),
    StagingDirConfig(id=3, name="ebooks", file_type="ebook"),
    StagingDirConfig(id=4, name="audio", file_type="audio"),
    StagingDirConfig(id=5, name="apps", file_type="app"),
    StagingDirConfig(id=6, name="android", file_type="app"),
    StagingDirConfig(id=97, name="temp", file_type=None, role="ingest"),
    StagingDirConfig(id=98, name="autres", file_type="other"),
]


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Build a complete synthetic Config with 3 neutral disks.

    Covers all 11 builtin category IDs distributed across drive_a, drive_b,
    drive_c. Uses generic folder names ``cat_{id}`` for easy assertion.
    Genre mapping mirrors V14 GenreMapper IDs for equivalence testing.

    String-based category_rules mirror V14 GenreMapper string-fallback branches
    (used when TMDB/TVDB return genre names but no IDs). Rules are media-type
    scoped via ``applies_to`` to avoid cross-type collisions (e.g. "animation"
    mapping to movies_animation for movies vs tv_shows_animation for TV).

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        Validated Config instance with 3 disks, all 11 builtin categories,
        and string-based category_rules for V14 equivalence.
    """
    # Rules for movies: string-based genre name matching (V14 string fallback)
    _movie_rules: list[CategoryRule] = [
        CategoryRule(
            tmdb_genre_contains="animation",
            category=CID.MOVIES_ANIMATION,
            applies_to="movie",
        ),
        CategoryRule(
            tmdb_genre_contains="documentary",
            category=CID.MOVIES_DOCUMENTARY,
            applies_to="movie",
        ),
        # French TMDB variant "Documentaire" (case-insensitive, "documentaire" in "documentaire")
        CategoryRule(
            tmdb_genre_contains="documentaire",
            category=CID.MOVIES_DOCUMENTARY,
            applies_to="movie",
        ),
    ]

    # Rules for TV: string-based genre name matching (V14 string fallback).
    # Order matters: "anime" must precede "animation" so genre name "anime"/"Anime"
    # is caught before the broader "animation" rule (though "anime" is not a
    # substring of "animation", the ordering documents intent clearly).
    # Animation + JP origin is handled by anime_rule (level 3), so the "animation"
    # rule here only fires for non-JP cases (anime_rule fires first for JP).
    _tv_rules: list[CategoryRule] = [
        # Genre name "anime" / "Anime" → anime (no origin_country needed)
        CategoryRule(
            tmdb_genre_contains="anime",
            category=CID.ANIME,
            applies_to="tv",
        ),
        # "Animation" string, non-JP → tv_shows_animation
        # (JP case: anime_rule fires at level 3 before these rules reach level 2,
        #  BUT only when genre_ids are present; for string-only+JP, anime_rule's
        #  str_match branch handles it before level 2 category_rules apply)
        CategoryRule(
            tmdb_genre_contains="animation",
            category=CID.TV_SHOWS_ANIMATION,
            applies_to="tv",
        ),
        CategoryRule(
            tmdb_genre_contains="documentary",
            category=CID.TV_SHOWS_DOCUMENTARY,
            applies_to="tv",
        ),
        # French TMDB variant "Documentaire"
        CategoryRule(
            tmdb_genre_contains="documentaire",
            category=CID.TV_SHOWS_DOCUMENTARY,
            applies_to="tv",
        ),
        # "Reality", "Talk", "Talk Show", "News" → tv_programs (English variants)
        CategoryRule(
            tmdb_genre_contains="reality",
            category=CID.TV_PROGRAMS,
            applies_to="tv",
        ),
        # "talk" matches both "talk" and "talk show" (substring)
        CategoryRule(
            tmdb_genre_contains="talk",
            category=CID.TV_PROGRAMS,
            applies_to="tv",
        ),
        CategoryRule(
            tmdb_genre_contains="news",
            category=CID.TV_PROGRAMS,
            applies_to="tv",
        ),
        # French TMDB variants: "Émission" (contains "mission"), "Divertissement"
        CategoryRule(
            tmdb_genre_contains="mission",
            category=CID.TV_PROGRAMS,
            applies_to="tv",
        ),
        CategoryRule(
            tmdb_genre_contains="divertissement",
            category=CID.TV_PROGRAMS,
            applies_to="tv",
        ),
    ]

    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents_complete",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[
            DiskConfig(
                id="drive_a",
                path=tmp_path / "drive_a",
                categories=[CID.MOVIES, CID.TV_SHOWS, CID.ANIME],
            ),
            DiskConfig(
                id="drive_b",
                path=tmp_path / "drive_b",
                categories=[CID.MOVIES_ANIMATION, CID.TV_SHOWS_ANIMATION],
            ),
            DiskConfig(
                id="drive_c",
                path=tmp_path / "drive_c",
                categories=[
                    CID.MOVIES_DOCUMENTARY,
                    CID.TV_SHOWS_DOCUMENTARY,
                    CID.AUDIOBOOKS,
                    CID.STANDUP,
                    CID.THEATER,
                    CID.TV_PROGRAMS,
                ],
            ),
        ],
        categories={cid: CategoryConfig(folder_name=f"cat_{cid}") for cid in CID.BUILTIN_CATEGORY_IDS},
        category_rules=_movie_rules + _tv_rules,
        genre_mapping=GenreMapping(
            tmdb_movies={
                16: CID.MOVIES_ANIMATION,
                99: CID.MOVIES_DOCUMENTARY,
            },
            tmdb_tv={
                16: CID.TV_SHOWS_ANIMATION,
                99: CID.TV_SHOWS_DOCUMENTARY,
                10764: CID.TV_PROGRAMS,
                10767: CID.TV_PROGRAMS,
                10763: CID.TV_PROGRAMS,
            },
            tvdb={
                27: CID.ANIME,
                17: CID.TV_SHOWS_ANIMATION,
                3: CID.TV_SHOWS_DOCUMENTARY,
                8: CID.TV_PROGRAMS,
                10: CID.TV_PROGRAMS,
                11: CID.TV_PROGRAMS,
            },
        ),
        anime_rule=AnimeRule(
            enabled=True,
            requires_genre_id=16,
            requires_origin_country=["JP"],
            maps_to=CID.ANIME,
            applies_to="tv",
        ),
        staging_dirs=CANONICAL_STAGING_DIRS,
        # Minimal valid ProvidersConfig so ``ProviderRegistry`` (built at the
        # CLI boundary by ``_build_app_context`` since feat/registry sub-phase
        # 3.1) does not raise ``RegistryConfigError`` for empty chain
        # capabilities. Tests that need finer control over provider chains
        # can build their own Config and override ``providers=`` explicitly.
        providers=ProvidersConfig(
            Searchable={"tvdb": 1, "tmdb": 2},
            MovieDetailsProvider={"tmdb": 1, "tvdb": 2},
            TvDetailsProvider={"tvdb": 1, "tmdb": 2},
            EpisodeFetcher={"tvdb": 1, "tmdb": 2},
            ArtworkProvider={"tmdb": 1, "tvdb": 2},
            KeywordProvider={"tmdb": 1},
            VideoProvider={"tmdb": 1, "tvdb": 2},
        ),
    )
