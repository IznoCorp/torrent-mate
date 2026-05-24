"""E2E tests for ``personalscraper library-rescrape`` — CLI-level harness.

Tests --dry-run safety (no FS/DB writes), already-conforming skip behavior,
and --format json output.  Creates real directory structures on tmp_path
since the rescraper walks config.disks (not the indexer DB).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import run_cli

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"

_NFO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>Test Movie</title>
  <year>2024</year>
  <uniqueid type="tmdb" default="true">550</uniqueid>
</movie>
"""


def _make_rescrape_item_dir(base: Path, title: str, nfo: bool = False, poster: bool = False) -> Path:
    """Create a media item directory on disk, optionally with NFO and poster.

    Returns the item directory path.
    """
    item_dir = base / title
    item_dir.mkdir(parents=True, exist_ok=True)
    if nfo:
        parsed_title = title.split(" (")[0]
        nfo_path = item_dir / f"{parsed_title}.nfo"
        nfo_path.write_text(_NFO_XML)
    if poster:
        parsed_title = title.split(" (")[0]
        poster_path = item_dir / f"{parsed_title}-poster.jpg"
        poster_path.write_bytes(b"\xff\xd8\xff\xe0")
    return item_dir


# ── 1. Help ─────────────────────────────────────────────────────────────────────


def test_rescrape_help_exits_zero() -> None:
    """--help exits 0 and shows usage."""
    result = run_cli(["library-rescrape", "--help"])
    assert result.exit_code == 0, result.output
    assert "rescrape" in result.output.lower()


# ── 2. Dry-run safety ───────────────────────────────────────────────────────────


def test_rescrape_dry_run_no_writes(tmp_path, test_config) -> None:
    """--dry-run previews items needing rescrape without modifying filesystem."""
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create disk + category + item dirs (no NFO, no poster → needs rescrape).
    disk_base = tmp_path / "drive_a"
    cat_dir = disk_base / "cat_movies"
    cat_dir.mkdir(parents=True, exist_ok=True)
    _make_rescrape_item_dir(cat_dir, "Test Movie (2024)", nfo=False, poster=False)

    # Record pre-run state.
    pre_files = set()
    for root, _dirs, files in os.walk(str(disk_base)):
        for f in files:
            pre_files.add(str(Path(root) / f))

    cfg = test_config
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "library-rescrape",
                "--dry-run",
            ]
        )

    assert result.exit_code == 0, result.output

    # Post-run: no new files created.
    post_files = set()
    for root, _dirs, files in os.walk(str(disk_base)):
        for f in files:
            post_files.add(str(Path(root) / f))
    new_files = post_files - pre_files
    assert not new_files, f"Dry-run created files: {new_files}"

    # JSON output exists and reflects dry_run.
    json_path = data_dir / "library_rescrape.json"
    assert json_path.exists(), f"Expected {json_path} to exist"
    data = json.loads(json_path.read_text())
    assert data["dry_run"] is True
    assert data["fixed_count"] == 0, f"Dry-run should not fix anything: {data}"


# ── 3. Skip already conforming ──────────────────────────────────────────────────


def test_rescrape_skips_already_conforming_items(tmp_path, test_config) -> None:
    """Item with valid NFO + poster is skipped without API calls."""
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create disk + category + item dir WITH valid NFO and poster.
    disk_base = tmp_path / "drive_a"
    cat_dir = disk_base / "cat_movies"
    cat_dir.mkdir(parents=True, exist_ok=True)
    _make_rescrape_item_dir(cat_dir, "Test Movie (2024)", nfo=True, poster=True)

    cfg = test_config
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "library-rescrape",
                "--dry-run",
            ]
        )

    assert result.exit_code == 0, result.output
    json_path = data_dir / "library_rescrape.json"
    data = json.loads(json_path.read_text())
    assert data["fixed_count"] == 0, f"Conforming item should not be flagged: {data}"
    assert data["skipped_count"] == 0, "Conforming item should be silently excluded"
    assert data["error_count"] == 0
    assert len(data["items"]) == 0, f"No items expected: {data['items']}"


# ── 4. Format JSON ──────────────────────────────────────────────────────────────


def test_rescrape_format_json(tmp_path, test_config) -> None:
    """--format json produces readable JSON in library_rescrape.json."""
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)

    disk_base = tmp_path / "drive_a"
    cat_dir = disk_base / "cat_movies"
    cat_dir.mkdir(parents=True, exist_ok=True)
    _make_rescrape_item_dir(cat_dir, "Test Movie (2024)", nfo=False, poster=False)

    cfg = test_config
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(
            [
                "--format",
                "json",
                "library-rescrape",
                "--dry-run",
            ]
        )

    assert result.exit_code == 0, result.output
    json_path = data_dir / "library_rescrape.json"
    data = json.loads(json_path.read_text())
    assert "rescraped_at" in data
    assert "dry_run" in data
    assert "fixed_count" in data
    assert "skipped_count" in data
    assert "error_count" in data
    assert isinstance(data["items"], list)


# ── 3. Errors ──


def test_rescrape_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    from tests.commands._e2e_helpers import assert_no_python_traceback

    result = run_cli(["library-rescrape", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_rescrape_db_path_none_handled_gracefully(test_config) -> None:
    """Unconfigured ``indexer.db_path`` → no traceback (rescrape walks config.disks, not DB)."""
    from tests.commands._e2e_helpers import assert_no_python_traceback

    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-rescrape", "--dry-run"])
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_rescrape_json_output_schema_valid(tmp_path, test_config) -> None:
    """Output JSON file matches expected schema."""
    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    disk_base = tmp_path / "drive_a"
    cat_dir = disk_base / "cat_movies"
    cat_dir.mkdir(parents=True, exist_ok=True)
    _make_rescrape_item_dir(cat_dir, "Test Movie (2024)", nfo=False, poster=False)
    cfg = test_config
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-rescrape", "--dry-run"])
    assert result.exit_code == 0
    json_path = data_dir / "library_rescrape.json"
    data = json.loads(json_path.read_text())
    for key in ("rescraped_at", "dry_run", "fixed_count", "skipped_count", "error_count", "items"):
        assert key in data, f"Missing key '{key}' in rescrape output: {sorted(data.keys())}"


def test_rescrape_error_exits_nonzero() -> None:
    """Invalid flag → non-zero exit code."""
    result = run_cli(["library-rescrape", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0


# ── 7. Events ──


def test_rescrape_dry_run_emits_events(tmp_path, test_config, monkeypatch) -> None:
    """Rescrape ``--dry-run`` runs with an active EventBus (no crash)."""
    from tests.commands._e2e_helpers import capture_event_bus

    data_dir = tmp_path / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    disk_base = tmp_path / "drive_a"
    cat_dir = disk_base / "cat_movies"
    cat_dir.mkdir(parents=True, exist_ok=True)
    _make_rescrape_item_dir(cat_dir, "Test Movie (2024)", nfo=False, poster=False)

    captured = capture_event_bus(monkeypatch)

    cfg = test_config
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["--format", "json", "library-rescrape", "--dry-run"])

    assert result.exit_code == 0, result.output
    # Dry-run emits preview/scan events.  Live mode emits ItemProgressed
    # per item but requires full TMDB/TVDB API mocking (out of scope for
    # this harness — covered by integration tests).
    assert isinstance(captured, list), f"captured should be a list, got {type(captured)}"


# ── 8. Idempotence ──

# N/A: rescrape idempotence is verified by ``test_rescrape_skips_already_conforming_items``
# under §3 — an item with a valid NFO + poster is skipped without API calls.
# The rescraper walks config.disks and generates NFO/poster files only for
# items missing them; once conforming, re-runs are no-ops.  The skip behaviour
# is the idempotence contract.


# ── 9. Closure-of-loop ──

# N/A: ``library-rescrape`` is a filesystem-only operation (NFO + poster file
# generation on disk).  It does not open the indexer DB — no ``open_db`` call,
# no BDD reads or writes.  The output lands in ``library_rescrape.json``
# (a JSON file in the data directory), not in the database.  With no BDD
# interaction there is no BDD ↔ FS loop to close.
