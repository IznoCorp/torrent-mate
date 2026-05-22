"""E2E test: drift mechanism wired into library-index CLI flow (DEV #18).

DEV #18 — pre tech-debt 0.16.0, ``personalscraper.indexer.drift.mark_missed_files``
was defined but NEVER called from production code (only from unit tests in
``tests/indexer/test_drift.py``). The function increments ``miss_strikes`` on
``media_file`` rows for files that were not visited by the current scan
generation. Without a production caller, ``miss_strikes`` stayed at 0
indefinitely, so ``apply_soft_deletes`` (which filters by
``miss_strikes >= n_strikes_for_softdelete``) could never tombstone anything.

Phase 1.1 of tech-debt 0.16.0 wires ``mark_missed_files`` into
``library_index_command`` (``personalscraper/indexer/commands/scan.py``) so the
drift mechanism becomes operational. This file pins the regression: the CLI
flow must invoke ``mark_missed_files`` once per visited disk when running in
``full`` mode and not in ``--dry-run``.

The test uses the existing ``test_cli.py`` harness pattern (CliRunner +
patched config + mocked scanner.scan for speed) and spies on
``mark_missed_files`` to assert it was called.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.cli import app
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.scanner import ScanRunResult
from tests.conftest import make_cli_runner

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_SCAN = "personalscraper.indexer.scanner.scan"

runner = make_cli_runner()


def _make_config(tmp_path: Path) -> Any:
    """Build a minimal Config whose ``indexer.db_path`` lives under *tmp_path*.

    Mirrors ``tests/indexer/test_cli.py::_make_config`` but kept private here
    to avoid coupling test_drift_e2e.py to a sibling test file's private helper.
    """
    from personalscraper.conf.models.indexer import IndexerConfig

    mock_cfg = MagicMock()
    ic = IndexerConfig(db_path=tmp_path / "library.db")
    mock_cfg.indexer = ic
    mock_cfg.paths.staging_dir = tmp_path / "staging"
    mock_cfg.all_category_ids = frozenset({"movies", "tv_shows", "anime", "standup"})
    return mock_cfg


def _make_conn(db_path: Path) -> sqlite3.Connection:
    """Open a real file-based SQLite DB with all migrations applied."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _fake_scan_result(scan_run_id: int = 1, files: int = 0, dirs: int = 0) -> ScanRunResult:
    """Synthetic scan result that lets the CLI proceed to post-walk steps."""
    return ScanRunResult(
        scan_run_id=scan_run_id,
        files_visited=files,
        dirs_visited=dirs,
        status="ok",
        disks_skipped=0,
    )


def test_library_index_full_mode_invokes_mark_missed_files(tmp_path: Path) -> None:
    """library-index --mode full DOIT appeler mark_missed_files par disk (DEV #18).

    Sans le fix Phase 1.1, mark_missed_files n'est jamais appelé depuis le
    flow CLI → miss_strikes reste à 0 pour les fichiers absents → apply_soft_deletes
    ne tombstone jamais. Ce test passe APRÈS le fix : mark_missed_files est
    invoqué une fois par disk visité (full mode only).
    """
    cfg = _make_config(tmp_path)
    db_path: Path = cfg.indexer.db_path
    conn = _make_conn(db_path)
    # Seed 2 disks so we can assert N calls = N disks
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("disk1-uuid", "Disk1", None, int(time.time()), None, 0, 0),
    )
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("disk2-uuid", "Disk2", None, int(time.time()), None, 0, 0),
    )
    conn.close()

    fake_result = _fake_scan_result(scan_run_id=1)

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_SCAN, return_value=fake_result),
        patch("personalscraper.indexer.drift.mark_missed_files", return_value=0) as spy,
    ):
        result = runner.invoke(app, ["library-index", "--mode", "full"])

    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
    assert spy.call_count == 2, (
        f"mark_missed_files must be called once per visited disk in full mode "
        f"(2 disks seeded → expected 2 calls, got {spy.call_count}). "
        f"This pins the DEV #18 fix wired in Phase 1.1."
    )
    # Verify args : (conn, disk_id, current_generation). Generations match next_gen=1.
    for call in spy.call_args_list:
        args, kwargs = call
        # mark_missed_files(conn, disk_id, current_generation) — positional or kw
        if kwargs:
            assert "disk_id" in kwargs or len(args) >= 2
            gen = kwargs.get("current_generation") or (args[2] if len(args) >= 3 else None)
        else:
            assert len(args) == 3, f"Expected 3 positional args, got {len(args)}: {args}"
            gen = args[2]
        assert gen == 1, f"Expected current_generation=1 (next_gen for empty DB), got {gen}"


def test_library_index_dry_run_does_not_invoke_mark_missed_files(tmp_path: Path) -> None:
    """--dry-run skips mark_missed_files (no mutation in dry-run by contract).

    The drift mechanism is a write operation. Dry-run mode must NEVER mutate
    miss_strikes — otherwise re-running the same dry-run twice would accumulate
    state, breaking dry-run idempotence.
    """
    cfg = _make_config(tmp_path)
    db_path: Path = cfg.indexer.db_path
    conn = _make_conn(db_path)
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("disk1-uuid", "Disk1", None, int(time.time()), None, 0, 0),
    )
    conn.close()

    fake_result = _fake_scan_result(scan_run_id=2)

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_SCAN, return_value=fake_result),
        patch("personalscraper.indexer.drift.mark_missed_files", return_value=0) as spy,
    ):
        result = runner.invoke(app, ["library-index", "--mode", "full", "--dry-run"])

    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
    assert spy.call_count == 0, (
        f"mark_missed_files must NOT be called in dry-run mode "
        f"(would mutate miss_strikes outside transaction). Got {spy.call_count} calls."
    )


def test_library_index_quick_mode_does_not_invoke_mark_missed_files(tmp_path: Path) -> None:
    """Quick mode skips mark_missed_files (no full walk → no accumulated strikes).

    Mark_missed_files compares scan_generation per file against the current
    generation. Quick mode uses Merkle short-circuit and does NOT visit every
    file, so bumping miss_strikes universally would incorrectly strike all
    unvisited files. Only full mode warrants the drift bump (matches plan
    Phase 1.1 conditions ``scan_mode in (ScanMode.full,)``).
    """
    cfg = _make_config(tmp_path)
    db_path: Path = cfg.indexer.db_path
    conn = _make_conn(db_path)
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, merkle_root, "
        "is_mounted, unreachable_strikes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("disk1-uuid", "Disk1", None, int(time.time()), None, 0, 0),
    )
    conn.close()

    fake_result = _fake_scan_result(scan_run_id=3)

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_SCAN, return_value=fake_result),
        patch("personalscraper.indexer.drift.mark_missed_files", return_value=0) as spy,
    ):
        result = runner.invoke(app, ["library-index", "--mode", "quick"])

    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}. Output:\n{result.output}"
    assert spy.call_count == 0, (
        f"mark_missed_files must NOT be called in quick mode "
        f"(no full walk → strikes would be wrong). Got {spy.call_count} calls."
    )
