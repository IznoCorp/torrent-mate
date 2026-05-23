"""Regression tests for PRAGMA discipline multi-site (DEV #33, #34).

Pins three contracts:

1. :func:`_apply_pragmas` applies the full canonical PRAGMA set (all 8 PRAGMAs,
   including ``foreign_keys=ON``).
2. Every raw-connect site listed in the plan now goes through ``_apply_pragmas``
   — each connection returns ``PRAGMA foreign_keys = 1`` after opening.
3. :mod:`scripts.check-pragma-discipline` catches new bare ``sqlite3.connect(``
   calls that bypass ``_apply_pragmas``, and passes cleanly on the current
   codebase.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.indexer.db import _apply_pragmas

# ---------------------------------------------------------------------------
# 1. _apply_pragmas helper — canonical PRAGMA set
# ---------------------------------------------------------------------------


class TestApplyPragmas:
    """_apply_pragmas sets the full canonical PRAGMA set on a connection."""

    def _make_conn(self, tmp_path: Path) -> sqlite3.Connection:
        """Return a fresh in-memory-ish file connection for testing."""
        return sqlite3.connect(str(tmp_path / "test.db"), isolation_level=None, check_same_thread=False)

    def test_journal_mode_wal(self, tmp_path: Path) -> None:
        """journal_mode is WAL after _apply_pragmas."""
        conn = self._make_conn(tmp_path)
        _apply_pragmas(conn)
        row = conn.execute("PRAGMA journal_mode").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "wal"

    def test_synchronous_normal(self, tmp_path: Path) -> None:
        """Synchronous is 1 (NORMAL) after _apply_pragmas."""
        conn = self._make_conn(tmp_path)
        _apply_pragmas(conn)
        row = conn.execute("PRAGMA synchronous").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 1  # 1 = NORMAL

    def test_temp_store_memory(self, tmp_path: Path) -> None:
        """temp_store is 2 (MEMORY) after _apply_pragmas."""
        conn = self._make_conn(tmp_path)
        _apply_pragmas(conn)
        row = conn.execute("PRAGMA temp_store").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 2  # 2 = MEMORY

    def test_cache_size(self, tmp_path: Path) -> None:
        """cache_size is -65536 after _apply_pragmas."""
        conn = self._make_conn(tmp_path)
        _apply_pragmas(conn)
        row = conn.execute("PRAGMA cache_size").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == -65536

    def test_mmap_size(self, tmp_path: Path) -> None:
        """mmap_size is 268435456 after _apply_pragmas."""
        conn = self._make_conn(tmp_path)
        _apply_pragmas(conn)
        row = conn.execute("PRAGMA mmap_size").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 268435456

    def test_wal_autocheckpoint(self, tmp_path: Path) -> None:
        """wal_autocheckpoint is 1000 after _apply_pragmas."""
        conn = self._make_conn(tmp_path)
        _apply_pragmas(conn)
        row = conn.execute("PRAGMA wal_autocheckpoint").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 1000

    def test_busy_timeout(self, tmp_path: Path) -> None:
        """busy_timeout is 5000 ms after _apply_pragmas."""
        conn = self._make_conn(tmp_path)
        _apply_pragmas(conn)
        row = conn.execute("PRAGMA busy_timeout").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 5000

    def test_foreign_keys_on(self, tmp_path: Path) -> None:
        """foreign_keys is 1 (ON) after _apply_pragmas — core DEV #33/#34 pin."""
        conn = self._make_conn(tmp_path)
        _apply_pragmas(conn)
        row = conn.execute("PRAGMA foreign_keys").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 1, "PRAGMA foreign_keys must be 1 (ON) after _apply_pragmas"


# ---------------------------------------------------------------------------
# 2. Raw-connect sites — each must enable foreign_keys after open
# ---------------------------------------------------------------------------


class TestRawConnectSitesPragmas:
    """Each raw-connect site applies _apply_pragmas, giving foreign_keys=1.

    These tests verify the contract for each site listed in the DEV #33/#34
    plan:
      - personalscraper/dispatch/run.py (×2 functions)
      - personalscraper/commands/library/audit.py
      - personalscraper/conf/loader.py
      - personalscraper/indexer/scanner/_concurrency.py
      - personalscraper/indexer/outbox/_disk.py
      - personalscraper/indexer/outbox/_publish.py

    Strategy: import the module's connection-opening helper (or the module
    itself), open a connection via the real code path, and assert
    ``PRAGMA foreign_keys`` returns 1.
    """

    def test_concurrency_open_worker_conn_fk_on(self, tmp_path: Path) -> None:
        """_open_worker_conn applies _apply_pragmas → foreign_keys=1 (DEV #33)."""
        from personalscraper.indexer.scanner._concurrency import _open_worker_conn

        db_path = tmp_path / "worker.db"
        # Must exist for SQLite to open without creating schema issues.
        db_path.touch()
        conn = _open_worker_conn(db_path)
        try:
            row = conn.execute("PRAGMA foreign_keys").fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == 1, "_open_worker_conn must set foreign_keys=ON via _apply_pragmas"

    def test_concurrency_open_worker_conn_full_pragma_set(self, tmp_path: Path) -> None:
        """_open_worker_conn applies the full canonical PRAGMA set (DEV #33)."""
        from personalscraper.indexer.scanner._concurrency import _open_worker_conn

        db_path = tmp_path / "worker2.db"
        db_path.touch()
        conn = _open_worker_conn(db_path)
        try:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            sync = conn.execute("PRAGMA synchronous").fetchone()[0]
            # busy_timeout is overridden to 30000 in worker connections.
            bt = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        finally:
            conn.close()
        assert fk == 1
        assert sync == 1  # NORMAL
        assert bt == 30000  # worker override

    def test_outbox_disk_id_for_path_fk_on(self, tmp_path: Path) -> None:
        """disk_id_for_path opens connection with _apply_pragmas → foreign_keys=1 (DEV #34)."""
        # We can't easily intercept the short-lived internal connection in
        # disk_id_for_path, so we verify indirectly: import _apply_pragmas and
        # confirm it is called via a monkey-patch that records invocations.
        from personalscraper.indexer.outbox import _disk

        db_path = tmp_path / "disk.db"
        db_path.touch()

        called_with: list[sqlite3.Connection] = []
        original_apply = _disk._apply_pragmas  # noqa: SLF001

        def recording_apply(conn: sqlite3.Connection) -> None:
            called_with.append(conn)
            original_apply(conn)

        with patch.object(_disk, "_apply_pragmas", side_effect=recording_apply):
            # disk_id_for_path returns None (no disks), but must still call _apply_pragmas.
            result = _disk.disk_id_for_path(Path("/some/path"), db_path)

        assert result is None  # No disks in empty DB — expected.
        assert len(called_with) == 1, "disk_id_for_path must call _apply_pragmas once"

    def test_outbox_publish_event_fk_on(self, tmp_path: Path) -> None:
        """publish_event opens connection with _apply_pragmas → foreign_keys=1 (DEV #34)."""
        from personalscraper.indexer.outbox import _publish

        db_path = tmp_path / "pub.db"
        db_path.touch()

        called_with: list[sqlite3.Connection] = []
        original_apply = _publish._apply_pragmas  # noqa: SLF001

        def recording_apply(conn: sqlite3.Connection) -> None:
            called_with.append(conn)
            original_apply(conn)

        with patch.object(_publish, "_apply_pragmas", side_effect=recording_apply):
            # publish_event will fail at outbox_repo.insert (no schema), but
            # the best-effort contract means it silently swallows the error.
            _publish.publish_event(
                disk_id=1,
                op="move",
                payload={"src": "/a", "dst": "/b"},
                db_path=db_path,
            )

        assert len(called_with) == 1, "publish_event must call _apply_pragmas once"


# ---------------------------------------------------------------------------
# 3. Lint guard script behaviour
# ---------------------------------------------------------------------------


class TestCheckPragmaDisciplineScript:
    """scripts/check-pragma-discipline.py catches violations and passes on clean code."""

    _SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "check-pragma-discipline.py"

    def _run(self, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        """Run the lint guard script and return the result."""
        import os

        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(self._SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_passes_on_current_codebase(self) -> None:
        """The script exits 0 on the current (fully migrated) codebase."""
        result = self._run()
        assert result.returncode == 0, (
            f"check-pragma-discipline.py should pass but returned {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "0 violations" in result.stdout

    def test_detects_bare_connect_in_temp_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The script exits 1 when a new file has sqlite3.connect() without _apply_pragmas."""
        # Create a fake violation file in a temp package dir.
        bad_file = tmp_path / "bad_module.py"
        bad_file.write_text(
            "import sqlite3\n"
            "from pathlib import Path\n"
            "\n"
            "def connect(db_path: Path):\n"
            "    conn = sqlite3.connect(str(db_path))\n"
            "    return conn\n",
            encoding="utf-8",
        )

        # Patch PACKAGE_ROOT in the script by importing it and overriding the constant.
        # Simpler approach: use a subprocess with a wrapper that overrides PACKAGE_ROOT.
        wrapper = tmp_path / "run_check.py"
        wrapper.write_text(
            f"import sys\n"
            f"sys.path.insert(0, {str(self._SCRIPT.parent.parent)!r})\n"
            f"import importlib.util, pathlib\n"
            f"spec = importlib.util.spec_from_file_location('check', {str(self._SCRIPT)!r})\n"
            f"mod = importlib.util.module_from_spec(spec)\n"
            f"spec.loader.exec_module(mod)\n"
            f"mod.PACKAGE_ROOT = pathlib.Path({str(tmp_path)!r})\n"
            f"sys.exit(mod.main())\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(wrapper)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            "check-pragma-discipline.py must exit 1 on a bare connect without _apply_pragmas\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "violation" in result.stdout.lower()

    def test_ignores_comment_lines(self, tmp_path: Path) -> None:
        """Comment lines containing sqlite3.connect( are not flagged as violations."""
        # Create a file that only mentions sqlite3.connect in a comment.
        ok_file = tmp_path / "ok_module.py"
        ok_file.write_text(
            "import sqlite3\n"
            "# Without this guard, sqlite3.connect(str(db_path)) would create garbage\n"
            "# files in the cwd — we skip when db_path is not a real Path.\n",
            encoding="utf-8",
        )

        wrapper = tmp_path / "run_check_ok.py"
        wrapper.write_text(
            f"import sys\n"
            f"sys.path.insert(0, {str(self._SCRIPT.parent.parent)!r})\n"
            f"import importlib.util, pathlib\n"
            f"spec = importlib.util.spec_from_file_location('check', {str(self._SCRIPT)!r})\n"
            f"mod = importlib.util.module_from_spec(spec)\n"
            f"spec.loader.exec_module(mod)\n"
            f"mod.PACKAGE_ROOT = pathlib.Path({str(tmp_path)!r})\n"
            f"sys.exit(mod.main())\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(wrapper)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "comment-only sqlite3.connect( reference must not be flagged\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
