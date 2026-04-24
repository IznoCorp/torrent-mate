"""Integration tests for the sort pipeline step.

Exercises ``personalscraper.sorter.run.run_sort`` against a real ``tmp_path``
staging tree, asserting on observable filesystem invariants.

Catalogue items covered:
    #3 — Sort routing: movie, episode, unknown type each land in the correct dir.
    #4 — Sort fuzzy reuse: a file matches an existing folder via fuzzy matching.
"""

from pathlib import Path

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, staging_path
from personalscraper.config import Settings
from personalscraper.sorter.file_type import FileType
from personalscraper.sorter.run import run_sort

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_settings() -> Settings:
    """Return a minimal Settings with disk-space guards disabled.

    Returns:
        Settings instance with disk-space threshold cleared so the check never
        blocks tests on machines with a small ``/tmp`` partition.
    """
    return Settings(min_free_space_staging_gb=0, min_free_space_disk_gb=0)


def _ingest_dir(staging_tree: Path) -> Path:
    """Return the 097-TEMP ingest directory within staging_tree.

    Args:
        staging_tree: Root staging directory fixture.

    Returns:
        Path to ``staging_tree / "097-TEMP"``.
    """
    return staging_tree / "097-TEMP"


# ---------------------------------------------------------------------------
# Catalogue #3 — sort routing by file type
# ---------------------------------------------------------------------------


def test_sort_routes_by_file_type(staging_tree: Path, integration_config: Config) -> None:
    """Movie, episode, and unknown files each land in the correct staging dir.

    Populates ``097-TEMP`` with three items and calls ``run_sort``.

    Asserts:
    - ``Movie.2023.mkv`` is routed to the movies staging dir.
    - ``Show.S01E01.mp4`` is routed to the TV shows staging dir.
    - ``readme.txt`` is routed to the ``other``-role staging dir
      (resolved dynamically from ``integration_config.staging_dirs``).

    Args:
        staging_tree: Staging root under tmp_path.
        integration_config: Config wired to fixture paths.
    """
    ingest = _ingest_dir(staging_tree)

    # Place one file of each expected type in the ingest directory.
    (ingest / "Movie.2023.mkv").write_bytes(b"\x00" * 8)
    (ingest / "Show.S01E01.mp4").write_bytes(b"\x00" * 8)
    (ingest / "readme.txt").write_bytes(b"junk")

    run_sort(_make_settings(), staging_dir=staging_tree, config=integration_config)

    # Resolve expected destination directories from config — no hardcoding.
    movies_dir = staging_path(integration_config, find_by_file_type(integration_config, FileType.MOVIE))
    tvshows_dir = staging_path(integration_config, find_by_file_type(integration_config, FileType.TVSHOW))
    other_entry = next(e for e in integration_config.staging_dirs if e.file_type == "other")
    other_dir = staging_path(integration_config, other_entry)

    # Movie: sorter creates a sub-folder "Movie (2023)" and places the file inside.
    movie_files = list(movies_dir.rglob("Movie.2023.mkv"))
    assert movie_files, f"Movie.2023.mkv not found under {movies_dir}"

    # Episode: sorter creates a sub-folder for the show and places the file inside.
    episode_files = list(tvshows_dir.rglob("Show.S01E01.mp4"))
    assert episode_files, f"Show.S01E01.mp4 not found under {tvshows_dir}"

    # Unknown: txt file goes to the other/default dir (flat, no sub-folder).
    other_file = other_dir / "readme.txt"
    assert other_file.exists(), f"readme.txt not found at {other_file}"


# ---------------------------------------------------------------------------
# Catalogue #4 — fuzzy reuse of an existing folder
# ---------------------------------------------------------------------------


def test_sort_reuses_existing_folder_via_fuzzy(staging_tree: Path, integration_config: Config) -> None:
    """A year-less movie file merges into an existing year-tagged folder via fuzzy match.

    Pre-creates ``001-MOVIES/Shrinking (2023)/`` and drops ``Shrinking.mkv``
    (no year in name) in 097-TEMP.  The sorter must route the file into the
    pre-existing ``Shrinking (2023)/`` folder rather than creating a bare
    ``Shrinking/`` folder.

    The no-year fixture is intentional: the fuzzy year guard requires ±1 year
    tolerance when both sides carry a year.  A year-less query triggers the
    one-sided-year re-score path (``fuzzy_match_score`` strips the year from
    the candidate) and scores 100, well above the short-title threshold of 95.

    Asserts:
    - ``Shrinking.mkv`` lands inside the existing ``Shrinking (2023)/`` folder.
    - No new bare ``Shrinking`` folder is created.

    Args:
        staging_tree: Staging root under tmp_path.
        integration_config: Config wired to fixture paths.
    """
    movies_dir = staging_path(integration_config, find_by_file_type(integration_config, FileType.MOVIE))

    # Pre-create the existing folder that the sorter should reuse.
    existing_folder = movies_dir / "Shrinking (2023)"
    existing_folder.mkdir(parents=True, exist_ok=True)

    # Drop a year-less file in the ingest directory so the fuzzy re-score path
    # is taken (one side has a year, the other does not → stripped comparison).
    ingest = _ingest_dir(staging_tree)
    (ingest / "Shrinking.mkv").write_bytes(b"\x00" * 8)

    run_sort(_make_settings(), staging_dir=staging_tree, config=integration_config)

    # The file must have landed inside the pre-existing folder.
    moved_file = existing_folder / "Shrinking.mkv"
    assert moved_file.exists(), (
        f"Shrinking.mkv should be inside {existing_folder}, "
        f"but was not found there. "
        f"movies_dir contents: {list(movies_dir.iterdir())}"
    )

    # No new bare "Shrinking" folder should have been created.
    new_folders = [d for d in movies_dir.iterdir() if d.is_dir() and d.name == "Shrinking"]
    assert not new_folders, f"Unexpected bare Shrinking folder created: {new_folders}"
