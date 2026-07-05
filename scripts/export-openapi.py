#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to ``frontend/openapi.json``.

Boots the TorrentMate web application via :func:`create_app` with a minimal
in-memory configuration (no real config/ directory, no network, no Redis) and
writes ``app.openapi()`` to disk.

Usage::

    python scripts/export-openapi.py

The output is deterministic: the same set of routes produces byte-identical
JSON (``sort_keys=True``, ``indent=2``).

This script exists so that the frontend can generate typed API bindings from
the committed schema without a running server.  CI verifies freshness via
``git diff --exit-code frontend/openapi.json``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

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
from personalscraper.config import Settings
from personalscraper.web.app import create_app

# Matches tests/fixtures/config.py — same canonical staging layout so the
# Config validates cleanly.
_CANONICAL_STAGING_DIRS: list[StagingDirConfig] = [
    StagingDirConfig(id=1, name="movies", file_type="movie"),
    StagingDirConfig(id=2, name="tvshows", file_type="tvshow"),
    StagingDirConfig(id=3, name="ebooks", file_type="ebook"),
    StagingDirConfig(id=4, name="audio", file_type="audio"),
    StagingDirConfig(id=5, name="apps", file_type="app"),
    StagingDirConfig(id=6, name="android", file_type="app"),
    StagingDirConfig(id=97, name="temp", file_type=None, role="ingest"),
    StagingDirConfig(id=98, name="autres", file_type="other"),
]


def _build_minimal_config(tmpdir: Path) -> Config:
    """Build a minimal synthetic ``Config`` suitable for OpenAPI export.

    Mirrors the ``test_config`` fixture from ``tests/fixtures/config.py``:
    tempdir-backed paths, one neutral disk, all 11 builtin category IDs,
    and a valid-but-minimal ``ProvidersConfig`` so the registry boot does
    not raise ``RegistryConfigError``.

    Args:
        tmpdir: A temporary directory to use as the root for all
            synthetic filesystem paths.

    Returns:
        A validated ``Config`` instance ready for ``create_app``.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmpdir / "torrents_complete",
            staging_dir=tmpdir / "staging",
            data_dir=tmpdir / ".data",
        ),
        disks=[
            DiskConfig(
                id="drive_a",
                path=tmpdir / "drive_a",
                categories=list(CID.BUILTIN_CATEGORY_IDS),
            ),
        ],
        categories={
            cid: CategoryConfig(folder_name=f"cat_{cid}")
            for cid in CID.BUILTIN_CATEGORY_IDS
        },
        category_rules=[
            CategoryRule(
                tmdb_genre_contains="animation",
                category=CID.MOVIES_ANIMATION,
                applies_to="movie",
            ),
            CategoryRule(
                tmdb_genre_contains="animation",
                category=CID.TV_SHOWS_ANIMATION,
                applies_to="tv",
            ),
        ],
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
        staging_dirs=_CANONICAL_STAGING_DIRS,
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


def main() -> None:
    """Export the OpenAPI schema to ``frontend/openapi.json``."""
    repo_root = Path(__file__).resolve().parent.parent
    output_path = repo_root / "frontend" / "openapi.json"

    with tempfile.TemporaryDirectory(prefix="openapi_export_") as tmpdir:
        config = _build_minimal_config(Path(tmpdir))
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        app = create_app(config, settings)
        schema = app.openapi()

    output_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI schema written to {output_path}")


if __name__ == "__main__":
    main()
