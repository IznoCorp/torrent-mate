"""Synthetic test config — 3 neutral disks, builtin IDs, generic labels.

Used across test modules as a stable, filesystem-agnostic Config fixture that
exercises all 11 builtin category IDs without depending on real disk paths.
"""

from pathlib import Path

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models import (
    AnimeRule,
    CategoryConfig,
    Config,
    DiskConfig,
    GenreMapping,
    PathConfig,
)


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Build a complete synthetic Config with 3 neutral disks.

    Covers all 11 builtin category IDs distributed across drive_a, drive_b,
    drive_c. Uses generic folder names ``cat_{id}`` for easy assertion.
    Genre mapping mirrors V14 GenreMapper IDs for equivalence testing.

    Args:
        tmp_path: Pytest temporary directory (unique per test).

    Returns:
        Validated Config instance with 3 disks and all 11 builtin categories.
    """
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
    )
