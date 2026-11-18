"""Test helper — a library whose second disk is frozen to ``["audiobooks"]`` yet holds media.

Production's second disk takes no NEW media (its ``categories`` gate dispatch
eligibility only) but still holds films and series, and new episodes of those
series keep landing there. The commands that find a disk's EXISTING media must
see that media whatever the disk's ``categories`` say; these helpers build the
tree and the config that reproduce it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from personalscraper.conf.models.categories import CategoryConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.conf.models.scraper import ScraperConfig
from tests._media_files import write_placeholder_media
from tests.fixtures.config import CANONICAL_STAGING_DIRS

FROZEN_DISK_ID = "medias2"
FROZEN_MOVIE = "Frozen Film (2020)"
FROZEN_SHOW = "Frozen Show (2019)"


@dataclass(frozen=True)
class FrozenLibrary:
    """The paths of the media seeded on the frozen disk.

    Attributes:
        movie_dir: The film folder on the frozen disk.
        show_dir: The series folder on the frozen disk.
    """

    movie_dir: Path
    show_dir: Path


def frozen_disk_config(tmp_path: Path) -> Config:
    """Build a two-disk Config whose second disk is frozen to audiobooks.

    Args:
        tmp_path: pytest tmp_path fixture.

    Returns:
        A populated Config; ``medias1`` accepts films and series, ``medias2``
        only audiobooks.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "complete",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[
            DiskConfig(id="medias1", path=tmp_path / "medias1", categories=["movies", "tv_shows"]),
            DiskConfig(id=FROZEN_DISK_ID, path=tmp_path / FROZEN_DISK_ID, categories=["audiobooks"]),
        ],
        categories={
            "movies": CategoryConfig(folder_name="films"),
            "tv_shows": CategoryConfig(folder_name="series"),
            "audiobooks": CategoryConfig(folder_name="audiobooks"),
        },
        staging_dirs=CANONICAL_STAGING_DIRS,
        scraper=ScraperConfig(),
        # Minimal valid chains so the CLI boundary's provider registry builds.
        providers=ProvidersConfig(
            Searchable={"tvdb": 1, "tmdb": 2},
            MovieDetailsProvider={"tmdb": 1, "tvdb": 2},
            TvDetailsProvider={"tvdb": 1, "tmdb": 2},
            EpisodeFetcher={"tvdb": 1, "tmdb": 2},
            ArtworkProvider={"tmdb": 1, "tvdb": 2},
            KeywordProvider={},
            VideoProvider={"tmdb": 1, "tvdb": 2},
        ),
    )


def seed_frozen_library(tmp_path: Path) -> FrozenLibrary:
    """Create the film and the series (each with a junk file) on the frozen disk, plus the first disk's folders.

    Args:
        tmp_path: pytest tmp_path fixture, the root :func:`frozen_disk_config` uses.

    Returns:
        The seeded film and series folders.
    """
    (tmp_path / "medias1" / "films").mkdir(parents=True)
    (tmp_path / "medias1" / "series").mkdir(parents=True)
    (tmp_path / FROZEN_DISK_ID / "audiobooks").mkdir(parents=True)

    movie_dir = tmp_path / FROZEN_DISK_ID / "films" / FROZEN_MOVIE
    movie_dir.mkdir(parents=True)
    write_placeholder_media(movie_dir / "Frozen Film.mkv", 200 * 1024 * 1024)
    (movie_dir / ".DS_Store").write_bytes(b"\0" * 16)

    show_dir = tmp_path / FROZEN_DISK_ID / "series" / FROZEN_SHOW
    (show_dir / "Saison 01").mkdir(parents=True)
    write_placeholder_media(show_dir / "Saison 01" / "Frozen Show - S01E01.mkv", 200 * 1024 * 1024)
    (show_dir / ".DS_Store").write_bytes(b"\0" * 16)
    return FrozenLibrary(movie_dir=movie_dir, show_dir=show_dir)
