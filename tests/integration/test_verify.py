"""Integration tests for the verify pipeline step.

Catalogue #10 — verify gate invariants.

Tests that run_verify correctly identifies:
- A complete movie folder (NFO + poster + landscape) as "valid".
- A movie folder missing its poster as "blocked".
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.sorter.file_type import FileType
from personalscraper.verify.run import run_verify

# Minimum video size to avoid the "sample" warning check (100 MB).
_MIN_VIDEO_BYTES = 100 * 1024 * 1024 + 1


def _make_settings() -> Settings:
    """Return a minimal Settings with disk-space guards disabled.

    Returns:
        Settings instance suitable for integration tests (no real disk checks).
    """
    return Settings()


def _build_movie_dir(
    parent: Path,
    title: str = "TestMovie",
    year: int = 2024,
    with_poster: bool = True,
    with_landscape: bool = True,
) -> Path:
    """Create a minimal movie directory under *parent*.

    Creates the directory, a video file large enough to pass the sample check,
    a valid NFO with title/year/tmdb+imdb IDs, and optionally a poster and
    landscape artwork file.

    Args:
        parent: Parent directory where the movie folder is created.
        title: Movie title used for folder and file naming.
        year: Release year used in folder name and NFO.
        with_poster: When True, create ``{title}-poster.jpg``.
        with_landscape: When True, create ``{title}-landscape.jpg``.

    Returns:
        Path to the created movie directory.
    """
    movie_dir = parent / f"{title} ({year})"
    movie_dir.mkdir(parents=True, exist_ok=True)

    # Video file — must be > 100 MB to avoid "sample" warning.
    (movie_dir / f"{title}.mkv").write_bytes(b"\x00" * _MIN_VIDEO_BYTES)

    # NFO with required fields: title, year, tmdb+imdb IDs.
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    uid_tmdb = ET.SubElement(root, "uniqueid")
    uid_tmdb.set("type", "tmdb")
    uid_tmdb.text = "12345"
    uid_imdb = ET.SubElement(root, "uniqueid")
    uid_imdb.set("type", "imdb")
    uid_imdb.text = "tt9999999"
    ET.SubElement(root, "genre").text = "Action"
    # streamdetails block — verifier checks for its presence.
    fi = ET.SubElement(root, "fileinfo")
    sd = ET.SubElement(fi, "streamdetails")
    ET.SubElement(sd, "video")
    ET.ElementTree(root).write(movie_dir / f"{title}.nfo", encoding="unicode")

    if with_poster:
        (movie_dir / f"{title}-poster.jpg").write_bytes(b"\xff")

    if with_landscape:
        (movie_dir / f"{title}-landscape.jpg").write_bytes(b"\xff")

    return movie_dir


def test_verify_accepts_complete_folder(staging_tree: Path, integration_config: Config) -> None:
    """A movie folder with NFO, poster, and landscape should verify as 'valid'.

    Catalogue #10a — happy-path gate invariant.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        integration_config: Fully composed integration Config fixture.
    """
    movies_dir = staging_tree / folder_name(find_by_file_type(integration_config, FileType.MOVIE))

    _build_movie_dir(movies_dir, title="CompleteFilm", year=2024, with_poster=True, with_landscape=True)

    _report, results = run_verify(
        _make_settings(),
        integration_config,
        dry_run=False,
        fix=False,
        movies_only=True,
    )

    assert results, "run_verify returned no results — verify step did not run or produced no output"
    # Find the result for our movie folder — it must be present in the dispatchable list.
    movie_result = next((r for r in results if r.media_path.name == "CompleteFilm (2024)"), None)
    assert movie_result is not None, (
        f"CompleteFilm (2024) must appear in verify results. Got: {[r.media_path.name for r in results]}"
    )
    assert movie_result.status in ("valid", "fixed"), (
        f"Expected 'valid' or 'fixed', got '{movie_result.status}'. Errors: {movie_result.errors}"
    )


def test_verify_blocks_missing_poster(staging_tree: Path, integration_config: Config) -> None:
    """A movie folder missing its poster should verify as 'blocked'.

    Catalogue #10b — poster-absent gate invariant. Poster presence is a
    blocking (ERROR-severity) check in checker.py, so omitting it must
    produce status 'blocked'.

    Args:
        staging_tree: Staging root fixture (tmp_path/staging).
        integration_config: Fully composed integration Config fixture.
    """
    movies_dir = staging_tree / folder_name(find_by_file_type(integration_config, FileType.MOVIE))

    _build_movie_dir(movies_dir, title="NoPosterFilm", year=2024, with_poster=False, with_landscape=True)

    _report, _dispatchable = run_verify(
        _make_settings(),
        integration_config,
        dry_run=False,
        fix=False,
        movies_only=True,
    )

    # Blocked folders do NOT appear in the dispatchable list — verify via report.
    assert any("NoPosterFilm (2024)" in d and "[blocked]" in d for d in _report.details), (
        f"Expected [blocked] for NoPosterFilm (2024) in report details. Got: {_report.details}"
    )
    assert _report.error_count >= 1, f"Expected at least 1 error in report. Got error_count={_report.error_count}"
