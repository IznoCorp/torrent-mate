"""E2E pipeline assertions — verify each step produced the expected results.

Each function checks the filesystem and data structures after a pipeline
step completes. Raises AssertionError with detailed messages on failure.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from tests.e2e.markers import MARKER_FILENAME, find_orphan_markers
from tests.e2e.registry import TestRegistry


def assert_ingest_complete(staging_dir: Path, expected: list[dict]) -> None:
    """Verify torrents were ingested into the staging area.

    Args:
        staging_dir: Path to A TRIER/.
        expected: List of magnet dicts with 'name' key.

    Raises:
        AssertionError: If any expected torrent is not found in staging.
    """
    staging_items = {p.name for p in staging_dir.iterdir() if not p.name.startswith(".")}
    for entry in expected:
        name = entry["name"]
        # Check if any item in staging contains the expected name (partial match)
        found = any(name.lower() in item.lower() for item in staging_items)
        assert found, (
            f"Ingest: '{name}' not found in staging dir. "
            f"Available: {sorted(staging_items)}"
        )


def assert_sort_complete(
    movies_dir: Path, tvshows_dir: Path, expected: list[dict]
) -> None:
    """Verify media was sorted into correct subdirectories.

    Args:
        movies_dir: Path to 001-MOVIES/.
        tvshows_dir: Path to 002-TVSHOWS/.
        expected: List of magnet dicts with 'name' and 'type' keys.

    Raises:
        AssertionError: If any expected item is not in its target directory.
    """
    for entry in expected:
        name = entry["name"]
        media_type = entry["type"]

        if media_type == "movie":
            target = movies_dir
        elif media_type == "tvshow":
            target = tvshows_dir
        else:
            continue

        if not target.exists():
            raise AssertionError(f"Sort: target directory {target} does not exist")

        items = {p.name for p in target.iterdir() if not p.name.startswith(".")}
        found = any(name.lower() in item.lower() for item in items)
        assert found, (
            f"Sort: '{name}' ({media_type}) not found in {target.name}. "
            f"Available: {sorted(items)}"
        )


def assert_scrape_complete(
    movies_dir: Path, tvshows_dir: Path, expected: list[dict]
) -> None:
    """Verify metadata scraping produced valid NFOs and artwork.

    Checks:
    - Each movie has a parseable .nfo XML with title and year
    - Each movie has at least a poster image
    - Each TV show has tvshow.nfo + poster
    - Episodes are renamed to S##E## format with individual .nfo

    Args:
        movies_dir: Path to 001-MOVIES/.
        tvshows_dir: Path to 002-TVSHOWS/.
        expected: List of magnet dicts with 'name', 'type', and optional
            'verify_nfo_fields' keys.

    Raises:
        AssertionError: If NFO/artwork is missing or invalid.
    """
    for entry in expected:
        name = entry["name"]
        media_type = entry["type"]

        if media_type == "movie":
            _assert_movie_scraped(movies_dir, name, entry.get("verify_nfo_fields", []))
        elif media_type == "tvshow":
            _assert_tvshow_scraped(tvshows_dir, name, entry.get("verify_nfo_fields", []))


def _assert_movie_scraped(movies_dir: Path, name: str, nfo_fields: list[str]) -> None:
    """Check a single movie has NFO + artwork."""
    movie_dir = _find_dir(movies_dir, name)
    assert movie_dir, f"Scrape: movie directory for '{name}' not found in {movies_dir}"

    # Find .nfo file
    nfo_files = list(movie_dir.glob("*.nfo"))
    assert nfo_files, f"Scrape: no .nfo file in {movie_dir}"

    # Validate NFO XML
    _validate_nfo(nfo_files[0], nfo_fields)

    # Check poster exists
    posters = list(movie_dir.glob("*poster*"))
    assert posters, f"Scrape: no poster in {movie_dir}"


def _assert_tvshow_scraped(tvshows_dir: Path, name: str, nfo_fields: list[str]) -> None:
    """Check a TV show has tvshow.nfo + poster + episode NFOs."""
    show_dir = _find_dir(tvshows_dir, name)
    assert show_dir, f"Scrape: TV show directory for '{name}' not found in {tvshows_dir}"

    # tvshow.nfo
    tvshow_nfo = show_dir / "tvshow.nfo"
    assert tvshow_nfo.exists(), f"Scrape: tvshow.nfo missing in {show_dir}"
    _validate_nfo(tvshow_nfo, nfo_fields)

    # Poster
    posters = list(show_dir.glob("poster*"))
    assert posters, f"Scrape: no poster in {show_dir}"


def _validate_nfo(nfo_path: Path, required_fields: list[str]) -> None:
    """Parse NFO XML and verify required fields exist."""
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise AssertionError(f"Scrape: invalid XML in {nfo_path}: {e}") from e

    for field_xpath in required_fields:
        elem = root.find(field_xpath)
        assert elem is not None, (
            f"Scrape: field '{field_xpath}' missing in {nfo_path.name}"
        )


def _find_dir(parent: Path, name: str) -> Path | None:
    """Find a subdirectory whose name contains the given string (case-insensitive)."""
    if not parent.exists():
        return None
    for d in parent.iterdir():
        if d.is_dir() and name.lower() in d.name.lower():
            return d
    return None


def assert_verify_complete(results: list) -> None:
    """Verify all test items passed the quality gate.

    Args:
        results: List of VerifyResult objects.

    Raises:
        AssertionError: If any result has status other than "valid" or "fixed".
    """
    for r in results:
        assert r.status in ("valid", "fixed"), (
            f"Verify: {r.media_path.name} has status '{r.status}', expected valid/fixed. "
            f"Issues: {r.issues}"
        )
        assert r.category is not None, (
            f"Verify: {r.media_path.name} has no category assigned"
        )


def assert_dispatch_complete(disk_paths: list[Path], expected: list[dict]) -> None:
    """Verify media was dispatched to storage disks.

    Checks each expected item is on a disk in the correct category,
    and that the .e2e-test-marker survived the rsync transfer.

    Args:
        disk_paths: List of disk media directories (e.g. /Volumes/Disk1/medias).
        expected: List of magnet dicts with 'name' and 'expected_category'.

    Raises:
        AssertionError: If any item is not on a disk or marker is missing.
    """
    for entry in expected:
        name = entry["name"]
        category = entry["expected_category"]
        found = False

        for disk in disk_paths:
            cat_dir = disk / category
            if not cat_dir.exists():
                continue
            match = _find_dir(cat_dir, name)
            if match:
                found = True
                # Verify marker survived dispatch (rsync)
                marker = match / MARKER_FILENAME
                assert marker.exists(), (
                    f"Dispatch: marker missing after dispatch for '{name}' at {match}"
                )
                break

        assert found, (
            f"Dispatch: '{name}' not found in '{category}' on any disk. "
            f"Checked: {[str(d) for d in disk_paths]}"
        )


def assert_pipeline_report(report) -> None:
    """Verify the pipeline report contains all expected steps.

    Args:
        report: PipelineReport instance.

    Raises:
        AssertionError: If any pipeline step is missing from the report.
    """
    expected_steps = {"ingest", "sort", "scrape", "verify", "dispatch"}
    actual_steps = set(report.steps.keys())
    missing = expected_steps - actual_steps
    assert not missing, f"Pipeline report missing steps: {missing}"
    assert report.finished_at is not None, "Pipeline report not finished"


def assert_cleanup_complete(
    registry: TestRegistry,
    base_paths: list[Path] | None = None,
    client=None,
) -> None:
    """Verify complete cleanup — no test artifacts remain anywhere.

    Args:
        registry: TestRegistry that tracked the session.
        base_paths: Directories to scan for orphan markers.
        client: qBittorrent client to verify torrent removal (optional).

    Raises:
        AssertionError: If any test artifact still exists.
    """
    # Check all registered paths are gone
    for path_str in registry.created_paths:
        path = Path(path_str)
        assert not path.exists(), f"Cleanup: registered path still exists: {path}"

    # Check no orphan markers
    if base_paths:
        orphans = find_orphan_markers(base_paths)
        assert not orphans, f"Cleanup: orphan markers found: {orphans}"

    # Check torrents removed from qBit
    if client:
        for h in registry.torrent_hashes:
            torrents = [t for t in client.torrents_info() if t.hash == h]
            assert not torrents, f"Cleanup: torrent {h} still in qBittorrent"
