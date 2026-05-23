"""Tests for the library-* audit Typer commands.

Covers ``library-reconcile``, ``library-ghost-audit``, and ``library-relink``.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()


# ── library-reconcile ────────────────────────────────────────────────────────


class TestLibraryReconcile:
    """Tests for the library-reconcile Typer command."""

    def test_help(self) -> None:
        """library-reconcile --help should display usage."""
        result = runner.invoke(app, ["library-reconcile", "--help"])
        assert result.exit_code == 0
        assert "--scope" in result.output
        assert "--enqueue-repairs" in result.output

    def test_default_invocation(self) -> None:
        """Default invocation runs every detector and exits 0."""
        with patch(
            "personalscraper.indexer.cli.library_reconcile_command",
            return_value=0,
        ) as mock_cmd:
            result = runner.invoke(app, ["library-reconcile"])
        assert result.exit_code == 0
        mock_cmd.assert_called_once()
        _, kwargs = mock_cmd.call_args
        assert kwargs["scopes"] is None
        assert kwargs["enqueue_repairs"] is False

    def test_scope_option_passes_list(self) -> None:
        """--scope flags must aggregate into a list and reach the command."""
        with patch(
            "personalscraper.indexer.cli.library_reconcile_command",
            return_value=0,
        ) as mock_cmd:
            result = runner.invoke(
                app,
                ["library-reconcile", "--scope", "merkle", "--scope", "enrich"],
            )
        assert result.exit_code == 0
        _, kwargs = mock_cmd.call_args
        assert kwargs["scopes"] == ["merkle", "enrich"]

    def test_enqueue_repairs(self) -> None:
        """--enqueue-repairs forwards True."""
        with patch(
            "personalscraper.indexer.cli.library_reconcile_command",
            return_value=0,
        ) as mock_cmd:
            result = runner.invoke(app, ["library-reconcile", "--enqueue-repairs"])
        assert result.exit_code == 0
        _, kwargs = mock_cmd.call_args
        assert kwargs["enqueue_repairs"] is True

    def test_non_zero_rc_propagates(self) -> None:
        """Underlying command returning non-zero must propagate as Typer exit."""
        with patch(
            "personalscraper.indexer.cli.library_reconcile_command",
            return_value=3,
        ):
            result = runner.invoke(app, ["library-reconcile"])
        assert result.exit_code == 3


# ── library-ghost-audit ──────────────────────────────────────────────────────


class TestLibraryGhostAudit:
    """Tests for the library-ghost-audit Typer command."""

    def test_help(self) -> None:
        """library-ghost-audit --help should display usage."""
        result = runner.invoke(app, ["library-ghost-audit", "--help"])
        assert result.exit_code == 0
        assert "--disk" in result.output

    def test_clean_run(self) -> None:
        """All disks not mounted prints 'not mounted' and exits 0."""
        # Default test_config disks point to tmp_path/drive_a etc. which do
        # not exist; the command should print "not mounted" and exit 0.
        result = runner.invoke(app, ["library-ghost-audit"])
        assert result.exit_code == 0
        assert "not mounted" in result.output
        assert "All disks clean" in result.output

    def test_disk_filter_skips_other_disks(self) -> None:
        """--disk filter restricts the loop to the requested disk only."""
        result = runner.invoke(app, ["library-ghost-audit", "--disk", "nonexistent_id"])
        # nonexistent_id matches no disk, so the loop body never runs;
        # total_ghosts stays 0 and the command prints "All disks clean".
        assert result.exit_code == 0
        assert "All disks clean" in result.output

    def test_clean_disk_reported_clean(self, tmp_path) -> None:
        """A mounted disk with no ghost dirents reports as clean."""
        # Make drive_a actually exist on disk so the loop runs the walk.
        (tmp_path / "drive_a").mkdir(parents=True, exist_ok=True)
        (tmp_path / "drive_a" / "a.mkv").write_text("data")
        result = runner.invoke(app, ["library-ghost-audit", "--disk", "drive_a"])
        assert result.exit_code == 0
        assert "clean" in result.output

    def test_ghost_detected_exits_1(self, tmp_path) -> None:
        """A FileNotFoundError on stat reports the entry as ghost and exits 1."""
        import os as _real_os

        (tmp_path / "drive_a").mkdir(parents=True, exist_ok=True)

        # Fake walk yields a phantom filename that doesn't exist on disk.
        # Stat will raise FileNotFoundError for the phantom, marking it ghost.
        fake_walk = [(str(tmp_path / "drive_a"), [], ["ghost.mkv"])]
        original_stat = _real_os.stat

        def fake_stat(path, *a, **kw):  # type: ignore[no-untyped-def]
            if "ghost.mkv" in str(path):
                raise FileNotFoundError(path)
            return original_stat(path, *a, **kw)

        with (
            patch("os.walk", return_value=iter(fake_walk)),
            patch("os.stat", side_effect=fake_stat),
        ):
            result = runner.invoke(app, ["library-ghost-audit", "--disk", "drive_a"])

        assert result.exit_code == 1
        assert "ghost dirent" in result.output

    def test_walk_oserror_handled(self, tmp_path) -> None:
        """OSError from os.walk is caught and printed as 'walk error'."""
        (tmp_path / "drive_a").mkdir(parents=True, exist_ok=True)
        with patch("os.walk", side_effect=OSError("boom")):
            result = runner.invoke(app, ["library-ghost-audit", "--disk", "drive_a"])
        assert result.exit_code == 0
        assert "walk error" in result.output


# ── library-relink ───────────────────────────────────────────────────────────


class TestLibraryRelink:
    """Tests for the library-relink Typer command."""

    def test_help(self) -> None:
        """library-relink --help should display usage."""
        result = runner.invoke(app, ["library-relink", "--help"])
        assert result.exit_code == 0
        assert "--apply" in result.output

    def _build_conn_with_disks(
        self,
        rows_disks: list[tuple[str, str]],
        rows_orphans: list[tuple[int, str, str, str]],
    ) -> sqlite3.Connection:
        """Build an in-memory sqlite3 connection that fakes the relink schema."""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE disk (id TEXT, mount_path TEXT, is_mounted INTEGER)")
        for d_id, mp in rows_disks:
            conn.execute("INSERT INTO disk (id, mount_path, is_mounted) VALUES (?, ?, 1)", (d_id, mp))
        conn.execute(
            "CREATE TABLE path (id INTEGER, disk_id TEXT, rel_path TEXT)",
        )
        conn.execute(
            "CREATE TABLE media_file (id INTEGER, filename TEXT, release_id INTEGER, deleted_at TEXT, path_id INTEGER)",
        )
        for mf_id, filename, disk_id, rel_path in rows_orphans:
            conn.execute(
                "INSERT INTO path (id, disk_id, rel_path) VALUES (?, ?, ?)",
                (mf_id, disk_id, rel_path),
            )
            conn.execute(
                "INSERT INTO media_file (id, filename, release_id, deleted_at, path_id) VALUES (?, ?, NULL, NULL, ?)",
                (mf_id, filename, mf_id),
            )
        conn.commit()
        return conn

    def test_no_mounted_disks_exits_0(self) -> None:
        """No rows in disk table → 'No mounted disks' and exit 0."""
        conn = self._build_conn_with_disks([], [])
        with patch("sqlite3.connect", return_value=conn):
            result = runner.invoke(app, ["library-relink"])
        assert result.exit_code == 0
        assert "No mounted disks" in result.output

    def test_no_orphans_exits_0(self, tmp_path) -> None:
        """Mounted disks but zero orphan rows → 'fully linked' and exit 0."""
        conn = self._build_conn_with_disks([("drive_a", str(tmp_path))], [])
        with patch("sqlite3.connect", return_value=conn):
            result = runner.invoke(app, ["library-relink"])
        assert result.exit_code == 0
        assert "fully linked" in result.output

    def test_dry_run_default(self, tmp_path) -> None:
        """Default invocation is dry-run: prints 'DRY-RUN' and rolls back."""
        conn = self._build_conn_with_disks(
            [("drive_a", str(tmp_path))],
            [(1, "movie.mkv", "drive_a", "Movies/Test")],
        )
        with (
            patch("sqlite3.connect", return_value=conn),
            patch(
                "personalscraper.indexer.release_linker.link_file_to_release",
                return_value={"matched": True},
            ),
        ):
            result = runner.invoke(app, ["library-relink"])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output
        assert "link=1" in result.output

    def test_apply_commits(self, tmp_path) -> None:
        """--apply commits and prints 'Applied'."""
        conn = self._build_conn_with_disks(
            [("drive_a", str(tmp_path))],
            [(1, "movie.mkv", "drive_a", "Movies/Test")],
        )
        with (
            patch("sqlite3.connect", return_value=conn),
            patch(
                "personalscraper.indexer.release_linker.link_file_to_release",
                return_value=None,  # unmatched
            ),
        ):
            result = runner.invoke(app, ["library-relink", "--apply"])
        assert result.exit_code == 0
        assert "Applied" in result.output
        assert "unmatched=1" in result.output

    def test_link_exception_counted_as_error(self, tmp_path) -> None:
        """An exception in link_file_to_release is counted as an error, not raised."""
        conn = self._build_conn_with_disks(
            [("drive_a", str(tmp_path))],
            [(1, "movie.mkv", "drive_a", "Movies/Test")],
        )
        with (
            patch("sqlite3.connect", return_value=conn),
            patch(
                "personalscraper.indexer.release_linker.link_file_to_release",
                side_effect=RuntimeError("link fail"),
            ),
        ):
            result = runner.invoke(app, ["library-relink"])
        assert result.exit_code == 0
        assert "errors=1" in result.output

    def test_explicit_dry_run_flag_recognised(self) -> None:
        """--dry-run flag is recognised by Typer (help check)."""
        result = runner.invoke(app, ["library-relink", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output

    def test_explicit_dry_run_is_no_op(self, tmp_path) -> None:
        """--dry-run is equivalent to the default: rolls back, prints DRY-RUN."""
        conn = self._build_conn_with_disks(
            [("drive_a", str(tmp_path))],
            [(1, "movie.mkv", "drive_a", "Movies/Test")],
        )
        with (
            patch("sqlite3.connect", return_value=conn),
            patch(
                "personalscraper.indexer.release_linker.link_file_to_release",
                return_value={"matched": True},
            ),
        ):
            result = runner.invoke(app, ["library-relink", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output

    def test_dry_run_and_apply_mutually_exclusive(self, tmp_path) -> None:
        """--dry-run and --apply together exit 1 with an error message."""
        result = runner.invoke(app, ["library-relink", "--dry-run", "--apply"])
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output
