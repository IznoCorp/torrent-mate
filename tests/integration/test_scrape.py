"""Integration tests for the scrape pipeline step.

Exercises ``personalscraper.scraper.run.run_scrape`` against a real
``tmp_path`` staging tree with an in-memory FakeTMDB stub, asserting on
observable filesystem invariants (NFO written / not written).

Catalogue items covered:
    #7 — Scrape hit:  TMDB match produces an NFO with a tmdb uniqueid element.
    #8 — Scrape miss: no TMDB results leaves the folder untouched (no NFO).
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, staging_path
from personalscraper.config import Settings
from personalscraper.scraper.run import run_scrape
from personalscraper.sorter.file_type import FileType
from tests.integration.conftest import FakeTMDB

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_settings() -> Settings:
    """Return a minimal Settings with disk-space guards disabled.

    Returns:
        Settings instance with disk-space threshold cleared so the check never
        blocks tests on machines with a small ``/tmp`` partition.
    """
    return Settings()


def _movies_dir(integration_config: Config) -> Path:
    """Resolve the movies staging directory from integration_config.

    Args:
        integration_config: Config wired to fixture paths.

    Returns:
        Absolute path to the movies staging subdirectory.
    """
    return staging_path(integration_config, find_by_file_type(integration_config, FileType.MOVIE))


# ---------------------------------------------------------------------------
# Catalogue #7 — scrape writes NFO on TMDB hit
# ---------------------------------------------------------------------------


def test_scrape_writes_nfo_on_tmdb_hit(
    staging_tree: Path,
    fake_tmdb: FakeTMDB,
    integration_config: Config,
) -> None:
    """A TMDB hit produces an NFO file containing a tmdb uniqueid element.

    Seeds ``fake_tmdb`` with:
    - A ``search/movie`` response returning one result for "Shrinking" (2023).
    - A ``movie/1020053`` response with full movie details (from the fixture).

    Asserts:
    - ``Shrinking.nfo`` is written inside the folder after ``run_scrape``.
    - The NFO XML contains ``<uniqueid type="tmdb">1020053</uniqueid>``.
    - The original ``Shrinking.mkv`` is preserved.

    Args:
        staging_tree: Staging root under tmp_path.
        fake_tmdb: In-memory TMDB stub (monkeypatched, fixture pre-seeded).
        integration_config: Config wired to fixture paths.
    """
    movies_dir = _movies_dir(integration_config)

    folder = movies_dir / "Shrinking (2023)"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Shrinking.mkv").write_bytes(b"\x00" * 64)

    # Seed search results so search_movie("/search/movie") returns a hit.
    fake_tmdb.seed(
        "search/movie",
        {"results": [{"id": 1020053, "title": "Shrinking", "release_date": "2023-01-27"}]},
    )
    # Seed detail response so get_movie(1020053) returns the full fixture payload.
    # The pre-seeded key "movie_shrinking" does not match "/movie/1020053";
    # we add the explicit fragment here.
    fake_tmdb.seed(
        "movie/1020053",
        {
            "id": 1020053,
            "title": "Shrinking",
            "original_title": "Shrinking",
            "release_date": "2023-01-27",
            "runtime": 35,
            "overview": "A grieving therapist starts breaking the rules.",
            "genres": [{"id": 35, "name": "Comédie"}, {"id": 18, "name": "Drame"}],
            "vote_average": 8.1,
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt15677150", "tvdb_id": None},
            "release_dates": {"results": []},
        },
    )

    run_scrape(_make_settings(), config=integration_config)

    # After a successful scrape the scraper may rename the folder to match the
    # resolved API title; locate the NFO by scanning for any .nfo file.
    nfo_files = list(movies_dir.rglob("*.nfo"))
    assert nfo_files, (
        f"Expected an NFO file under {movies_dir} after scrape, found none. "
        f"movies_dir contents: {[p.name for p in movies_dir.rglob('*')]}"
    )

    nfo_path = nfo_files[0]
    tree = ET.parse(nfo_path)
    root = tree.getroot()

    tmdb_uniqueid = next(
        (el for el in root.findall("uniqueid") if el.get("type") == "tmdb"),
        None,
    )
    assert tmdb_uniqueid is not None, (
        f"No <uniqueid type='tmdb'> element found in {nfo_path.name}. "
        f"XML: {ET.tostring(root, encoding='unicode')[:500]}"
    )
    assert tmdb_uniqueid.text == "1020053", f"Expected tmdb uniqueid '1020053', got {tmdb_uniqueid.text!r}"

    # The video file must survive (scraper renames it, not deletes it).
    video_files = list(movies_dir.rglob("*.mkv"))
    assert video_files, "Shrinking.mkv (or renamed equivalent) should still exist after scrape"


# ---------------------------------------------------------------------------
# Catalogue #8 — scrape leaves folder untouched on TMDB miss
# ---------------------------------------------------------------------------


def test_scrape_leaves_folder_on_tmdb_miss(
    staging_tree: Path,
    fake_tmdb: FakeTMDB,
    integration_config: Config,
) -> None:
    """No TMDB results leaves the folder intact — no NFO written, no files lost.

    The ``fake_tmdb`` stub is NOT seeded with a ``search/movie`` entry, so
    ``search_movie`` returns the default empty list ``{"results": []}``.

    Asserts:
    - No NFO file is created under the movies directory.
    - ``Shrinking.mkv`` is still present (no destructive fallback).

    Args:
        staging_tree: Staging root under tmp_path.
        fake_tmdb: In-memory TMDB stub (monkeypatched, returns empty by default).
        integration_config: Config wired to fixture paths.
    """
    movies_dir = _movies_dir(integration_config)

    folder = movies_dir / "Shrinking (2023)"
    folder.mkdir(parents=True, exist_ok=True)
    video_file = folder / "Shrinking.mkv"
    video_file.write_bytes(b"\x00" * 64)

    # Do NOT seed search/movie — default stub returns {"results": []}.
    run_scrape(_make_settings(), config=integration_config)

    # No NFO should have been written.
    nfo_files = list(movies_dir.rglob("*.nfo"))
    assert not nfo_files, f"No NFO should be written on TMDB miss, found: {[p.name for p in nfo_files]}"

    # Original video file must be preserved.
    assert video_file.exists(), (
        f"Shrinking.mkv should still be present after a TMDB miss, "
        f"folder contents: {[p.name for p in folder.iterdir()]}"
    )
