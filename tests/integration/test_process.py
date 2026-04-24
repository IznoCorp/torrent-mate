"""Integration tests for the process pipeline step.

Exercises reclean and dedup logic from ``personalscraper.process.run``
against a real ``tmp_path`` staging tree, asserting on observable filesystem
invariants.

Catalogue items covered:
    #5 — Reclean: polluted folder name is renamed to canonical ``Title (Year)`` form.
    #6 — Dedup: fuzzy-duplicate folders are merged; sparse duplicate is removed.
"""

from pathlib import Path

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, staging_path
from personalscraper.config import Settings
from personalscraper.process.run import run_clean
from personalscraper.sorter.file_type import FileType

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


def _movies_dir(integration_config: Config) -> Path:
    """Resolve the movies staging directory from integration_config.

    Args:
        integration_config: Config wired to fixture paths.

    Returns:
        Absolute path to the movies staging subdirectory.
    """
    return staging_path(integration_config, find_by_file_type(integration_config, FileType.MOVIE))


# ---------------------------------------------------------------------------
# Catalogue #5 — reclean removes pollution tokens
# ---------------------------------------------------------------------------


def test_reclean_removes_pollution(staging_tree: Path, integration_config: Config) -> None:
    """A polluted folder name is cleaned and renamed to ``Title (Year)`` form.

    Places ``The.Matrix.1999.1080p.BluRay.x264-RARBG/video.mkv`` in the movies
    staging directory, then runs ``run_clean`` (reclean+dedup combined).

    Asserts:
    - The folder is renamed to ``The Matrix (1999)``.
    - The ``video.mkv`` file is preserved inside the renamed folder.
    - No folder with the original polluted name remains.

    Args:
        staging_tree: Staging root under tmp_path.
        integration_config: Config wired to fixture paths.
    """
    movies_dir = _movies_dir(integration_config)

    # Place polluted folder with a stub video file.
    polluted = movies_dir / "The.Matrix.1999.1080p.BluRay.x264-RARBG"
    polluted.mkdir(parents=True, exist_ok=True)
    (polluted / "video.mkv").write_bytes(b"\x00" * 16)

    run_clean(_make_settings(), config=integration_config)

    clean_folder = movies_dir / "The Matrix (1999)"
    assert clean_folder.exists(), (
        f"Expected cleaned folder 'The Matrix (1999)' in {movies_dir}, "
        f"found: {[d.name for d in movies_dir.iterdir() if d.is_dir()]}"
    )
    assert (clean_folder / "video.mkv").exists(), "video.mkv should be preserved after reclean"

    # Original polluted folder must be gone.
    assert not polluted.exists(), f"Polluted folder {polluted.name!r} should have been renamed"


# ---------------------------------------------------------------------------
# Catalogue #6 — dedup merges fuzzy duplicates
# ---------------------------------------------------------------------------


def test_dedup_merges_fuzzy_duplicates(staging_tree: Path, integration_config: Config) -> None:
    """Fuzzy-duplicate folders are merged; the sparse folder is removed.

    Places ``Shrinking/`` (sparse — one small placeholder) and
    ``Shrinking (2023)/`` (complete — video + NFO) in the movies staging
    directory.  Runs ``run_clean`` (which always runs dedup).

    Asserts:
    - ``Shrinking/`` is removed (merged away as the less-complete folder).
    - ``Shrinking (2023)/`` still exists and retains its ``.nfo`` file.

    Args:
        staging_tree: Staging root under tmp_path.
        integration_config: Config wired to fixture paths.
    """
    movies_dir = _movies_dir(integration_config)

    # Sparse folder: only a tiny stub file (no NFO, no video).
    sparse = movies_dir / "Shrinking"
    sparse.mkdir(parents=True, exist_ok=True)
    (sparse / "placeholder.txt").write_bytes(b"sparse")

    # Complete folder: video + NFO so dedup picks it as the merge target.
    complete = movies_dir / "Shrinking (2023)"
    complete.mkdir(parents=True, exist_ok=True)
    (complete / "Shrinking.mkv").write_bytes(b"\x00" * 64)
    (complete / "Shrinking.nfo").write_text(
        '<?xml version="1.0"?><movie><title>Shrinking</title></movie>',
        encoding="utf-8",
    )

    run_clean(_make_settings(), config=integration_config)

    # Complete folder (the merge target) must survive.
    assert complete.exists(), "'Shrinking (2023)' should still exist after dedup"

    # Its NFO must be intact.
    assert (complete / "Shrinking.nfo").exists(), "Shrinking.nfo should be preserved in the merge target"

    # Sparse folder must be gone (merged into the complete one).
    assert not sparse.exists(), (
        f"Sparse 'Shrinking' folder should have been merged away, "
        f"found: {[d.name for d in movies_dir.iterdir() if d.is_dir()]}"
    )
