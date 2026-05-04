"""Roundtrip E2E tests: disk → torrentify → guessit → match → compare.

For each scrapable media category, samples real folders from the storage
disks (read-only — disks are NEVER modified), converts their names to
realistic torrent-style filenames, then verifies that the matching
pipeline (guessit + TMDB/TVDB API) recovers the same media identity.

This validates the full name-cleaning and API-matching chain is stable:
if a movie correctly stored as "The Matrix (1999)" on disk cannot be
recovered from "The.Matrix.1999.MULTi.1080p.BluRay.x264-FiDELiO",
there is a bug in the pipeline.

TV show torrents deliberately omit the year (realistic: season packs
rarely include it), testing the pipeline's ability to match by title alone.

Requirements:
    - At least one storage disk mounted at /Volumes/Disk{1-4}/medias
    - TMDB_API_KEY set in .env (Bearer read access token)
    - TVDB_API_KEY set in .env
    - Network access to api.themoviedb.org and api4.thetvdb.com

Usage:
    pytest tests/e2e/test_roundtrip.py -m roundtrip -v -s
"""

import logging
from pathlib import Path

import guessit as guessit_module
import pytest

from personalscraper.api.metadata.tmdb import TMDBClient
from personalscraper.config import get_settings
from personalscraper.scraper.confidence import (
    LOW_CONFIDENCE,
    match_movie,
    match_tvshow,
    score_match,
)
from personalscraper.scraper.tvdb_client import TVDBClient
from tests.e2e.torrentifier import (
    parse_folder_name,
    torrentify_movie,
    torrentify_tvshow,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DISK_PATHS = {
    "Disk1": Path("/Volumes/Disk1/medias"),
    "Disk2": Path("/Volumes/Disk2/medias"),
    "Disk3": Path("/Volumes/Disk3/medias"),
    "Disk4": Path("/Volumes/Disk4/medias"),
}

# Categories that go through TMDB movie matching
MOVIE_CATEGORIES = [
    "films",
    "films animations",
    "films documentaires",
    "spectacles",
    "theatres",
]

# Categories that go through TVDB/TMDB TV show matching
TVSHOW_CATEGORIES = [
    "series",
    "series animations",
    "series documentaires",
    "series animes",
    "emissions",
]

# How many items to sample per category (evenly spaced)
SAMPLE_SIZE = 5

# Minimum fraction of items that must match successfully.
# Set to 0.6 (3/5) to allow for edge cases: French spectacles,
# titles with special characters, or niche emissions.
MIN_SUCCESS_RATE = 0.6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _discover_folders(category: str) -> list[str]:
    """Discover media folders for a category across all mounted disks.

    Scans all 4 disk paths, collects folders matching "Title (Year)" pattern,
    and returns deduplicated names sorted alphabetically. Disks are read-only.

    Args:
        category: Media category name (e.g. "films", "series animes").

    Returns:
        Sorted list of unique folder names.
    """
    seen: set[str] = set()
    for disk_path in DISK_PATHS.values():
        cat_dir = disk_path / category
        if not cat_dir.is_dir():
            continue
        try:
            for item in cat_dir.iterdir():
                if item.is_dir() and parse_folder_name(item.name):
                    seen.add(item.name)
        except PermissionError:
            continue
    return sorted(seen)


def _sample_evenly(items: list[str], n: int) -> list[str]:
    """Sample N items evenly spaced from a sorted list.

    Takes items at regular intervals to ensure diversity (beginning,
    middle, end of alphabetical range).

    Args:
        items: Sorted list of items.
        n: Number of items to sample.

    Returns:
        List of N evenly-spaced items.
    """
    if not items or n <= 0:
        return []
    if len(items) <= n or n == 1:
        return items[:n]
    step = (len(items) - 1) / (n - 1)
    return [items[round(i * step)] for i in range(n)]


def _parse_torrent_name(name: str) -> tuple[str, int | None]:
    """Parse a torrent name via guessit to extract title and year.

    Simulates what V2 sort does when processing raw torrent filenames.

    Args:
        name: Torrent-style filename.

    Returns:
        (title, year) tuple. Year may be None for TV shows.
    """
    info = guessit_module.guessit(name)
    title = info.get("title", "")
    year = info.get("year")
    return title, year


def _format_result(r: dict) -> str:
    """Format a single roundtrip result for display.

    Args:
        r: Result dict from a roundtrip test iteration.

    Returns:
        Formatted multi-line string.
    """
    status = "\u2713" if r["success"] else "\u2717"
    lines = [f"  {status} {r['folder']}"]
    lines.append(f"    torrent: {r['torrent']}")
    lines.append(f'    guessit: "{r["parsed_title"]}" year={r.get("parsed_year")}')
    if "error" in r:
        lines.append(f"    error: {r['error']}")
    else:
        source = r.get("source", "tmdb")
        lines.append(
            f"    \u2192 {r['api_title']} ({r['api_year']}) "
            f"[{source}, conf={r['confidence']:.2f}, roundtrip={r['roundtrip']:.2f}]"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def roundtrip_settings():
    """Load pipeline settings for API clients."""
    return get_settings()


@pytest.fixture(scope="module")
def tmdb(roundtrip_settings):
    """Create a TMDB client for roundtrip tests.

    Skips all tests in the module if the API key is not configured.
    """
    if not roundtrip_settings.tmdb_api_key:
        pytest.skip("TMDB API key not configured")
    return TMDBClient(api_key=roundtrip_settings.tmdb_api_key)


@pytest.fixture(scope="module")
def tvdb(roundtrip_settings):
    """Create a TVDB client for roundtrip tests.

    Skips all tests in the module if the API key is not configured.
    """
    if not roundtrip_settings.tvdb_api_key:
        pytest.skip("TVDB API key not configured")
    return TVDBClient(api_key=roundtrip_settings.tvdb_api_key)


# ---------------------------------------------------------------------------
# Movie roundtrip tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.roundtrip
class TestRoundtripMovies:
    """Roundtrip tests for movie categories (films, animations, documentaires).

    For each category, samples real folders from the storage disks,
    converts them to torrent-style names, parses with guessit, matches
    via TMDB, and verifies the API result corresponds to the original.
    """

    @pytest.mark.parametrize("category", MOVIE_CATEGORIES)
    def test_movie_roundtrip(self, category: str, tmdb: TMDBClient) -> None:
        """Verify roundtrip matching for a movie category.

        Args:
            category: Movie category to test.
            tmdb: TMDB client fixture.
        """
        all_folders = _discover_folders(category)
        if not all_folders:
            pytest.skip(f"No data for '{category}' on any mounted disk")

        sample = _sample_evenly(all_folders, SAMPLE_SIZE)
        results: list[dict] = []

        for folder_name in sample:
            parsed = parse_folder_name(folder_name)
            assert parsed is not None, f"Could not parse folder: {folder_name}"
            orig_title, orig_year = parsed

            # Step 1: Torrentify the clean name
            torrent_name = torrentify_movie(orig_title, orig_year)

            # Step 2: Parse with guessit (simulates V2 sort)
            parsed_title, parsed_year = _parse_torrent_name(torrent_name)

            result: dict = {
                "folder": folder_name,
                "torrent": torrent_name,
                "parsed_title": parsed_title,
                "parsed_year": parsed_year,
                "success": False,
            }

            # Step 3: Match via TMDB (simulates V3 scrape)
            try:
                match = match_movie(tmdb, parsed_title, parsed_year)
            except Exception as e:
                result["error"] = f"{type(e).__name__}: {e}"
                results.append(result)
                continue

            if match is None:
                result["error"] = "No match found"
                results.append(result)
                continue

            # Step 4: Verify roundtrip — API match should correspond to original
            roundtrip = score_match(
                orig_title,
                orig_year,
                match.api_title,
                match.api_year,
            )
            result.update(
                {
                    "api_title": match.api_title,
                    "api_year": match.api_year,
                    "confidence": match.confidence,
                    "roundtrip": roundtrip,
                    "success": (match.confidence >= LOW_CONFIDENCE and roundtrip >= LOW_CONFIDENCE),
                }
            )
            results.append(result)

        # Report and assert
        if not results:
            pytest.skip(f"No processable samples for '{category}'")
        successes = sum(1 for r in results if r["success"])
        rate = successes / len(results)

        header = f"\n{'=' * 60}"
        header += f"\nRoundtrip [{category}]: {successes}/{len(results)} passed ({rate:.0%})"
        header += f"\n{'=' * 60}"
        detail_lines = [header] + [_format_result(r) for r in results]
        report = "\n".join(detail_lines)

        # Print for -s output even on success
        print(report)

        assert rate >= MIN_SUCCESS_RATE, report


# ---------------------------------------------------------------------------
# TV show roundtrip tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.roundtrip
class TestRoundtripTVShows:
    """Roundtrip tests for TV show categories.

    For each TV category (series, animations, documentaires, animes,
    emissions), samples real folders from the storage disks, converts
    them to torrent-style season pack names, parses with guessit,
    matches via TVDB/TMDB, and verifies the result matches the original.
    """

    @pytest.mark.parametrize("category", TVSHOW_CATEGORIES)
    def test_tvshow_roundtrip(
        self,
        category: str,
        tmdb: TMDBClient,
        tvdb: TVDBClient,
    ) -> None:
        """Verify roundtrip matching for a TV show category.

        Args:
            category: TV show category to test.
            tmdb: TMDB client fixture.
            tvdb: TVDB client fixture.
        """
        all_folders = _discover_folders(category)
        if not all_folders:
            pytest.skip(f"No data for '{category}' on any mounted disk")

        sample = _sample_evenly(all_folders, SAMPLE_SIZE)
        results: list[dict] = []

        for folder_name in sample:
            parsed = parse_folder_name(folder_name)
            assert parsed is not None, f"Could not parse folder: {folder_name}"
            orig_title, orig_year = parsed

            # Step 1: Torrentify as a season pack (S01)
            torrent_name = torrentify_tvshow(orig_title, orig_year)

            # Step 2: Parse with guessit (simulates V2 sort)
            parsed_title, parsed_year = _parse_torrent_name(torrent_name)

            result: dict = {
                "folder": folder_name,
                "torrent": torrent_name,
                "parsed_title": parsed_title,
                "parsed_year": parsed_year,
                "success": False,
            }

            # Step 3: Match via TVDB/TMDB (simulates V3 scrape)
            try:
                match = match_tvshow(tvdb, tmdb, parsed_title, parsed_year)
            except Exception as e:
                result["error"] = f"{type(e).__name__}: {e}"
                results.append(result)
                continue

            if match is None:
                result["error"] = "No match found"
                results.append(result)
                continue

            # Step 4: Verify roundtrip
            roundtrip = score_match(
                orig_title,
                orig_year,
                match.api_title,
                match.api_year,
            )
            result.update(
                {
                    "api_title": match.api_title,
                    "api_year": match.api_year,
                    "confidence": match.confidence,
                    "roundtrip": roundtrip,
                    "source": match.source,
                    "success": (match.confidence >= LOW_CONFIDENCE and roundtrip >= LOW_CONFIDENCE),
                }
            )
            results.append(result)

        # Report and assert
        if not results:
            pytest.skip(f"No processable samples for '{category}'")
        successes = sum(1 for r in results if r["success"])
        rate = successes / len(results)

        header = f"\n{'=' * 60}"
        header += f"\nRoundtrip [{category}]: {successes}/{len(results)} passed ({rate:.0%})"
        header += f"\n{'=' * 60}"
        detail_lines = [header] + [_format_result(r) for r in results]
        report = "\n".join(detail_lines)

        print(report)

        assert rate >= MIN_SUCCESS_RATE, report
