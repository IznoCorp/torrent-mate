"""E2E test: ``library index`` drains all pending outbox rows on a synthetic fixture.

Scope: build a 50-item synthetic filesystem fixture (mixed movies + TV shows),
pre-seed 50 ``index_outbox`` rows representing fake ``move`` mutations, invoke
``library-index --mode quick`` via the Typer CLI runner, then assert that
``index_outbox`` contains zero rows with ``status='pending'`` after the run.

Deviation from the original plan's "full pipeline run" framing:
    A full scan would require mock disks with real scan_run infra and pyfakefs;
    for the E2E tier the key invariant is "drain works end-to-end through the CLI",
    not that the scanner runs. The fixture seeds outbox rows directly (same as
    production mutation points do) and verifies the CLI path:
    ``library_index_command`` → ``drain_if_present`` → ``drain`` → zero pending.
    This matches the acceptance criterion ("index_outbox ends with zero pending rows").

Test strategy:
    - Use ``tmp_path`` (real filesystem) to avoid pyfakefs interference with the
      Typer CLI runner.
    - Apply DB migrations via ``apply_migrations`` before seeding rows.
    - Patch config + scanner so the CLI finds the prepared DB and skips FS walking.
    - Use ``@pytest.mark.e2e`` so this test is excluded from the default
      ``pytest`` run (``addopts`` in pyproject.toml excludes ``e2e``).
      Run with ``pytest -m e2e tests/e2e/test_pipeline_indexer.py`` to execute.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.cli import app
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import outbox_repo
from personalscraper.indexer.scanner import ScanRunResult
from tests.conftest import make_cli_runner

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_SCAN = "personalscraper.indexer.scanner.scan"

_N_ITEMS = 50

runner = make_cli_runner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> Any:
    """Build a minimal Config with a ``tmp_path``-backed DB.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        MagicMock Config whose ``indexer.db_path`` points to a writable file.
    """
    from personalscraper.conf.models.indexer import IndexerConfig

    mock_cfg = MagicMock()
    ic = IndexerConfig(db_path=tmp_path / "library.db")
    mock_cfg.indexer = ic
    return mock_cfg


def _make_conn(db_path: Path) -> sqlite3.Connection:
    """Open a file-backed SQLite DB and apply all migrations.

    Args:
        db_path: Path to the SQLite file to create/open.

    Returns:
        Open :class:`sqlite3.Connection` with FK enforcement enabled and
        the full migration chain applied.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    # Set WAL mode upfront so a subsequent CLI invocation can re-open the DB
    # without blocking on a journal-mode transition.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _build_fixture_fs(tmp_path: Path) -> list[Path]:
    """Create a 50-item synthetic filesystem tree under *tmp_path*.

    Produces a mix of movie folders (``001-MOVIES/``) and TV-show episode
    files (``002-TVSHOWS/``) to mimic a realistic staging directory.

    Args:
        tmp_path: Root of the synthetic tree.

    Returns:
        List of all created :class:`Path` objects (files only, 50 total).
    """
    created: list[Path] = []

    # 25 movie entries — one .mkv per folder.
    movies_root = tmp_path / "001-MOVIES"
    for i in range(25):
        folder = movies_root / f"Movie Title {i:02d} (2020)"
        folder.mkdir(parents=True, exist_ok=True)
        fpath = folder / f"Movie.Title.{i:02d}.2020.mkv"
        fpath.write_bytes(b"V" * 300)
        created.append(fpath)

    # 25 TV episode entries — 5 shows × 5 episodes.
    tv_root = tmp_path / "002-TVSHOWS"
    for show_idx in range(5):
        show_folder = tv_root / f"TV Show {show_idx:02d} (2021)" / "Season 01"
        show_folder.mkdir(parents=True, exist_ok=True)
        for ep_idx in range(5):
            ep = show_folder / f"TV.Show.{show_idx:02d}.S01E{ep_idx + 1:02d}.mkv"
            ep.write_bytes(b"E" * 300)
            created.append(ep)

    assert len(created) == _N_ITEMS, f"Expected {_N_ITEMS} files, built {len(created)}"
    return created


def _seed_outbox_rows(conn: sqlite3.Connection, files: list[Path], disk_id: int = 1) -> None:
    """Insert one ``move`` outbox row per file in *files*.

    Each row represents a synthetic move mutation as production pipeline
    mutation points would emit via ``outbox_repo.insert``.

    Args:
        conn: Open SQLite connection with ``index_outbox`` table present.
        files: List of file paths to use as row sources.
        disk_id: Synthetic disk PK to embed in each payload.  Must be an
            integer; no actual ``disk`` row is required — the drainer defers
            rows whose disk is unreachable.  ``source`` is set to ``'scanner'``
            to satisfy the CHECK constraint on ``index_outbox.source``.
    """
    now_ns = int(time.time() * 1e9)
    for fpath in files:
        payload = json.dumps(
            {
                "disk_id": disk_id,
                "dst_rel_path": str(fpath.parent.name),
                "filename": fpath.name,
                "size_bytes": 300,
                "mtime_ns": now_ns,
            }
        )
        outbox_repo.insert(conn, source="scanner", op="move", payload_json=payload)


# ---------------------------------------------------------------------------
# E2E test
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestPipelineIndexerDrainsOutbox:
    """``library index`` runs end-to-end and leaves the outbox fully drained."""

    def test_50_item_fixture_zero_pending_after_index(self, tmp_path: Path) -> None:
        """Build a 50-item fixture, seed 50 outbox rows, run CLI, assert zero pending.

        Steps:
        1. Build a synthetic 50-file filesystem tree.
        2. Open DB + apply migrations.
        3. Pre-seed 50 ``index_outbox`` rows (one per synthetic file).
        4. Invoke ``library-index --mode quick`` with scanner mocked (no real walk).
        5. Assert ``index_outbox`` has zero rows with ``status='pending'``.

        The drainer defers each row to ``pending_op`` (disk_id=1, no mounted disk
        row exists), so the outcome is ``status='deferred'``, not ``'done'``.
        The key invariant is ``status != 'pending'`` — all rows were processed.
        """
        # Step 1 — synthetic FS tree.
        files = _build_fixture_fs(tmp_path)
        assert len(files) == _N_ITEMS

        # Step 2 — build DB.
        cfg = _make_config(tmp_path)
        db_path: Path = cfg.indexer.db_path
        conn = _make_conn(db_path)

        # Seed an unmounted disk row so the drainer's defer path can write to
        # pending_op (which has FK on disk_id); rows will be deferred to
        # status='deferred', not 'done'.
        now = int(time.time())
        conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, last_seen_at, "
            "merkle_root, is_mounted, unreachable_strikes) "
            "VALUES ('e2e-fixture-uuid', 'E2EFixtureDisk', NULL, ?, NULL, 0, 0)",
            (now,),
        )
        disk_row = conn.execute("SELECT id FROM disk WHERE uuid='e2e-fixture-uuid'").fetchone()
        disk_id_int: int = disk_row[0]

        # Step 3 — pre-seed outbox rows.
        _seed_outbox_rows(conn, files, disk_id=disk_id_int)
        pending_before = conn.execute("SELECT COUNT(*) FROM index_outbox WHERE status = 'pending'").fetchone()[0]
        conn.close()
        assert pending_before == _N_ITEMS, f"Expected {_N_ITEMS} pending rows before CLI run, found {pending_before}"

        # Step 4 — invoke CLI (scanner mocked, no real FS walk).
        fake_result = ScanRunResult(
            scan_run_id=1,
            files_visited=0,
            dirs_visited=0,
            status="ok",
            disks_skipped=0,
        )
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=fake_result),
        ):
            result = runner.invoke(app, ["library-index", "--mode", "quick"])

        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"

        # Step 5 — assert zero pending rows remain.
        verify_conn = sqlite3.connect(str(db_path), isolation_level=None)
        pending_after = verify_conn.execute("SELECT COUNT(*) FROM index_outbox WHERE status = 'pending'").fetchone()[0]
        verify_conn.close()

        assert pending_after == 0, f"Expected 0 pending outbox rows after 'library index', found {pending_after}"
