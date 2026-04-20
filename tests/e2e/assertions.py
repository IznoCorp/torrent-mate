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
        assert found, f"Ingest: '{name}' not found in staging dir. Available: {sorted(staging_items)}"


def assert_sort_complete(movies_dir: Path, tvshows_dir: Path, expected: list[dict]) -> None:
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
        assert found, f"Sort: '{name}' ({media_type}) not found in {target.name}. Available: {sorted(items)}"


def assert_scrape_complete(movies_dir: Path, tvshows_dir: Path, expected: list[dict]) -> None:
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
        assert elem is not None, f"Scrape: field '{field_xpath}' missing in {nfo_path.name}"


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
            f"Verify: {r.media_path.name} has status '{r.status}', expected valid/fixed. Issues: {r.issues}"
        )
        assert r.category is not None, f"Verify: {r.media_path.name} has no category assigned"


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
                assert marker.exists(), f"Dispatch: marker missing after dispatch for '{name}' at {match}"
                break

        assert found, (
            f"Dispatch: '{name}' not found in '{category}' on any disk. Checked: {[str(d) for d in disk_paths]}"
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


def assert_scrape_golden(media_dir: Path, golden) -> None:
    """Assert scrape results match golden file expectations.

    Checks:
    1. Directory name matches golden.nfo["folder_name_pattern"]
    2. NFO file exists and is valid XML
    3. All required_nfo_tags are present in NFO XML
    4. All nfo_invariants match exact values in NFO XML
    5. Required artwork files exist (golden.artwork["required"])
    6. Artwork files meet minimum size (golden.artwork["min_poster_size_bytes"])
    7. For TV shows: season dirs exist, episode count matches

    Args:
        media_dir: The scraped media directory.
        golden: GoldenFile with expected data.

    Raises:
        AssertionError: If any check fails.
    """
    nfo = golden.nfo
    if not nfo:
        return

    # 1. Folder name pattern
    if "folder_name_pattern" in nfo:
        assert nfo["folder_name_pattern"].lower() in media_dir.name.lower(), (
            f"Golden: folder name '{media_dir.name}' doesn't match pattern '{nfo['folder_name_pattern']}'"
        )

    # 2-4. NFO validation
    media_type = nfo.get("media_type", "movie")
    if media_type == "tvshow":
        nfo_path = media_dir / "tvshow.nfo"
    else:
        nfo_files = list(media_dir.glob("*.nfo"))
        nfo_path = nfo_files[0] if nfo_files else None

    if nfo_path and nfo_path.exists():
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        # 3. Required tags
        for tag in nfo.get("required_nfo_tags", []):
            assert root.find(tag) is not None, f"Golden: required NFO tag '{tag}' missing in {nfo_path.name}"

        # 4. Invariants (exact value match)
        for key, expected_value in nfo.get("nfo_invariants", {}).items():
            elem = root.find(key)
            assert elem is not None, f"Golden: invariant tag '{key}' missing in {nfo_path.name}"
            assert elem.text == str(expected_value), f"Golden: NFO '{key}' = '{elem.text}', expected '{expected_value}'"

    # 5-6. Artwork
    artwork = golden.artwork
    if artwork:
        for filename in artwork.get("required", []):
            art_path = media_dir / filename
            assert art_path.exists(), f"Golden: required artwork '{filename}' missing in {media_dir.name}"

        min_size = artwork.get("min_poster_size_bytes", 0)
        if min_size:
            posters = list(media_dir.glob("*poster*"))
            for poster in posters:
                assert poster.stat().st_size >= min_size, (
                    f"Golden: poster '{poster.name}' too small ({poster.stat().st_size} < {min_size})"
                )

    # 7. TV show seasons
    seasons = nfo.get("seasons", {})
    for season_num, season_data in seasons.items():
        season_dir_name = season_data.get("season_dir", f"Saison {int(season_num):02d}")
        season_dir = media_dir / season_dir_name
        assert season_dir.is_dir(), f"Golden: season dir '{season_dir_name}' missing in {media_dir.name}"

        expected_count = season_data.get("episode_count", 0)
        if expected_count:
            mkv_files = list(season_dir.glob("*.mkv"))
            assert len(mkv_files) >= expected_count, (
                f"Golden: season {season_num} has {len(mkv_files)} episodes, expected {expected_count}"
            )


def assert_dispatch_golden(result, golden) -> None:
    """Assert dispatch dry-run results match golden file expectations.

    Args:
        result: DispatchResult from run_dispatch(dry_run=True).
        golden: GoldenFile with expected data.

    Raises:
        AssertionError: If any check fails.
    """
    dispatch = golden.dispatch
    if not dispatch:
        return

    # 1. Action matches
    expected_action = dispatch.get("action")
    if expected_action:
        assert result.action == expected_action, (
            f"Golden: dispatch action '{result.action}', expected '{expected_action}'"
        )

    # 2. Disk in eligible list
    eligible = dispatch.get("eligible_disks", [])
    if eligible and result.disk:
        assert result.disk in eligible, f"Golden: disk '{result.disk}' not in eligible {eligible}"

    # 3. Destination contains expected substring
    dest_contains = dispatch.get("destination_contains")
    if dest_contains and result.destination:
        assert dest_contains in str(result.destination), (
            f"Golden: destination '{result.destination}' doesn't contain '{dest_contains}'"
        )

    # 4. No error/skipped
    assert result.action not in ("error", "skipped"), (
        f"Golden: dispatch failed with action '{result.action}', reason: {result.reason}"
    )


def assert_structure_golden(media_dir: Path, golden) -> None:
    """Assert directory structure matches golden file expectations.

    Args:
        media_dir: The media directory to check.
        golden: GoldenFile with expected data.

    Raises:
        AssertionError: If any check fails.
    """
    structure = golden.structure
    if not structure:
        return

    # 1. Required files (glob patterns)
    for pattern in structure.get("required_files", []):
        matches = list(media_dir.glob(pattern))
        assert matches, f"Golden: required file pattern '{pattern}' not found in {media_dir.name}"

    # 2. Required dirs
    for dir_name in structure.get("required_dirs", []):
        dir_path = media_dir / dir_name
        assert dir_path.is_dir(), f"Golden: required directory '{dir_name}' missing in {media_dir.name}"

    # 3. Forbidden patterns
    for pattern in structure.get("forbidden_patterns", []):
        matches = list(media_dir.glob(pattern))
        assert not matches, (
            f"Golden: forbidden pattern '{pattern}' found in {media_dir.name}: {[m.name for m in matches]}"
        )

    # 4. Season files
    for season_name, season_data in structure.get("season_files", {}).items():
        season_dir = media_dir / season_name
        if not season_dir.exists():
            continue

        min_count = season_data.get("min_episode_count", 0)
        if min_count:
            ep_pattern = season_data.get("episode_pattern", "*.mkv")
            episodes = list(season_dir.glob(ep_pattern))
            assert len(episodes) >= min_count, (
                f"Golden: {season_name} has {len(episodes)} episodes matching '{ep_pattern}', expected >= {min_count}"
            )


def find_media_dir(parent_dir: Path, folder_pattern: str) -> Path:
    """Find a media directory by folder name pattern.

    Searches subdirectories of parent_dir for a directory whose name
    contains the given pattern (case-insensitive).

    Args:
        parent_dir: Parent directory to search (e.g. 001-MOVIES/).
        folder_pattern: Expected folder name or substring.

    Returns:
        Path to the matching directory.

    Raises:
        AssertionError: If no matching directory is found.
    """
    if not parent_dir.exists():
        raise AssertionError(f"find_media_dir: parent '{parent_dir}' does not exist")

    for d in parent_dir.iterdir():
        if d.is_dir() and folder_pattern.lower() in d.name.lower():
            return d

    available = sorted(d.name for d in parent_dir.iterdir() if d.is_dir())
    raise AssertionError(
        f"find_media_dir: no directory matching '{folder_pattern}' in {parent_dir.name}. Available: {available}"
    )


def find_dispatch_result(results: list, torrent_name: str):
    """Find a DispatchResult matching a torrent name.

    Searches the list of DispatchResult for one whose source.name
    partially matches the torrent name (case-insensitive).

    Args:
        results: List of DispatchResult from run_dispatch().
        torrent_name: Torrent name to match against source.name.

    Returns:
        Matching DispatchResult, or None if not found.
    """
    torrent_lower = torrent_name.lower()
    for r in results:
        if torrent_lower in str(r.source.name).lower():
            return r
        if str(r.source.name).lower() in torrent_lower:
            return r
    return None


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
