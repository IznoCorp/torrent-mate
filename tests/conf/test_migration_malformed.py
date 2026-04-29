"""Tests for personalscraper.conf.migration — malformed / edge-case inputs."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.conf.migration import (
    MigrationAlreadyDoneError,
    MigrationError,
    MigrationMalformedError,
    migrate_v1_to_v2,
)
from tests.conftest import make_cli_runner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_V1 = """\
{{
    config_version: 1,
    paths: {{
        torrent_complete_dir: "{complete}",
        staging_dir: "{staging}",
        data_dir: "{data}",
    }},
    disks: [
        {{
            id: "disk_a",
            path: "{disk_a}",
            categories: ["movies", "tv_shows"],
        }},
    ],
    staging_dirs: [
        {{ id: 1, name: "movies", file_type: "movie" }},
        {{ id: 2, name: "tvshows", file_type: "tvshow" }},
        {{ id: 3, name: "ebooks", file_type: "ebook" }},
        {{ id: 4, name: "audio", file_type: "audio" }},
        {{ id: 5, name: "apps", file_type: "app" }},
        {{ id: 6, name: "android", file_type: "app" }},
        {{ id: 97, name: "temp", file_type: null, role: "ingest" }},
        {{ id: 98, name: "autres", file_type: "other" }},
    ],
}}
"""


def _write_v1(tmp_path: Path) -> Path:
    """Write a minimal valid v1 config to tmp_path/config.json5.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Path to the written config.json5.
    """
    legacy = tmp_path / "config.json5"
    legacy.write_text(
        _MINIMAL_V1.format(
            complete=tmp_path / "complete",
            staging=tmp_path / "staging",
            data=tmp_path / ".data",
            disk_a=tmp_path / "disk_a",
        ),
        encoding="utf-8",
    )
    return legacy


# ---------------------------------------------------------------------------
# Missing / non-existent file
# ---------------------------------------------------------------------------


class TestMissingFile:
    """Legacy file is absent."""

    def test_raises_malformed_when_file_missing(self, tmp_path: Path) -> None:
        """MigrationMalformedError raised when legacy file does not exist."""
        with pytest.raises(MigrationMalformedError, match="not found"):
            migrate_v1_to_v2(tmp_path / "does_not_exist.json5", tmp_path / "config")


# ---------------------------------------------------------------------------
# Comments-only / empty file
# ---------------------------------------------------------------------------


class TestEmptyOrCommentsOnly:
    """Legacy file exists but contains no usable mapping."""

    def test_comments_only_raises_malformed(self, tmp_path: Path) -> None:
        """A file containing only JSON5 comments (no object) raises MigrationMalformedError."""
        legacy = tmp_path / "config.json5"
        # JSON5 allows bare comments but `json5.load` of a comment-only file
        # either returns None or raises — both are malformed for our purposes.
        legacy.write_text("// just a comment\n// nothing else\n", encoding="utf-8")
        with pytest.raises(MigrationMalformedError):
            migrate_v1_to_v2(legacy, tmp_path / "config")

    def test_empty_file_raises_malformed(self, tmp_path: Path) -> None:
        """An empty file raises MigrationMalformedError."""
        legacy = tmp_path / "config.json5"
        legacy.write_text("", encoding="utf-8")
        with pytest.raises(MigrationMalformedError):
            migrate_v1_to_v2(legacy, tmp_path / "config")


# ---------------------------------------------------------------------------
# Invalid JSON5 syntax
# ---------------------------------------------------------------------------


class TestInvalidJson5:
    """Legacy file has parse errors."""

    def test_invalid_json5_raises_malformed(self, tmp_path: Path) -> None:
        """Syntax error in legacy file raises MigrationMalformedError."""
        legacy = tmp_path / "config.json5"
        legacy.write_text("{this is not valid json5!!!", encoding="utf-8")
        with pytest.raises(MigrationMalformedError, match="JSON5 parse error"):
            migrate_v1_to_v2(legacy, tmp_path / "config")

    def test_trailing_comma_json5_accepted(self, tmp_path: Path) -> None:
        """JSON5 trailing commas (valid in JSON5) must parse without error."""
        # json5 library handles trailing commas natively — confirm migration succeeds.
        legacy = _write_v1(tmp_path)
        # _write_v1 already uses trailing commas in its template.
        target = tmp_path / "config"
        migrate_v1_to_v2(legacy, target)
        assert target.is_dir()

    def test_array_as_root_raises_malformed(self, tmp_path: Path) -> None:
        """A JSON5 array at the root level raises MigrationMalformedError."""
        legacy = tmp_path / "config.json5"
        legacy.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(MigrationMalformedError, match="JSON object"):
            migrate_v1_to_v2(legacy, tmp_path / "config")


# ---------------------------------------------------------------------------
# Missing staging_dirs
# ---------------------------------------------------------------------------


class TestMissingStagingDirs:
    """Legacy file is missing the required staging_dirs key."""

    def test_missing_staging_dirs_still_migrates(self, tmp_path: Path) -> None:
        """Missing staging_dirs migrates successfully (key is absent, not invalid)."""
        # staging_dirs is required by pydantic but the MIGRATION itself does not
        # validate against the pydantic schema — it just splits keys.  The
        # resulting v2 dir will fail to load via load_config_dir, but the
        # migration writer should not block on this.
        legacy = tmp_path / "config.json5"
        legacy.write_text(
            f"""{{
                config_version: 1,
                paths: {{
                    torrent_complete_dir: "{tmp_path / "complete"}",
                    staging_dir: "{tmp_path / "staging"}",
                    data_dir: "{tmp_path / ".data"}",
                }},
                disks: [
                    {{
                        id: "disk_a",
                        path: "{tmp_path / "disk_a"}",
                        categories: ["movies"],
                    }},
                ],
            }}""",
            encoding="utf-8",
        )
        target = tmp_path / "config"
        # Migration succeeds at the file-splitting level even if pydantic would
        # later reject the config (staging_dirs missing).
        migrate_v1_to_v2(legacy, target)
        assert target.is_dir()
        # patterns.json5 is empty (no staging_dirs key to split).
        import json5

        patterns = json5.loads((target / "patterns.json5").read_text(encoding="utf-8"))
        assert "staging_dirs" not in patterns


# ---------------------------------------------------------------------------
# version=2 already present
# ---------------------------------------------------------------------------


class TestVersionAlreadyV2:
    """The legacy file already contains the v2 marker (overlays key in master)."""

    def test_already_migrated_target_dir_raises(self, tmp_path: Path) -> None:
        """If target_dir/config.json5 has 'overlays' key, MigrationAlreadyDoneError raised."""
        target = tmp_path / "config"
        target.mkdir()
        master = target / "config.json5"
        master.write_text(
            '{ "config_version": 1, "overlays": ["paths.json5"] }',
            encoding="utf-8",
        )
        legacy = _write_v1(tmp_path)
        with pytest.raises(MigrationAlreadyDoneError, match="overlays"):
            migrate_v1_to_v2(legacy, target)

    def test_target_dir_without_overlays_key_proceeds(self, tmp_path: Path) -> None:
        """target_dir exists but master has no 'overlays' key → migration proceeds."""
        target = tmp_path / "config"
        target.mkdir()
        # A master without 'overlays' is not treated as already-migrated.
        master = target / "config.json5"
        master.write_text('{ "config_version": 1 }', encoding="utf-8")
        legacy = _write_v1(tmp_path)
        migrate_v1_to_v2(legacy, target)
        import json5

        new_master = json5.loads((target / "config.json5").read_text(encoding="utf-8"))
        assert "overlays" in new_master


# ---------------------------------------------------------------------------
# Partial failure leaves .in-progress/
# ---------------------------------------------------------------------------


class TestPartialFailureLeavesInProgress:
    """Simulated mid-write failure must leave .in-progress/ on disk."""

    def test_in_progress_dir_left_on_failure(self, tmp_path: Path) -> None:
        """.in-progress/ must be left when writing fails mid-way."""
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        in_progress = Path(str(target) + ".in-progress")

        # Patch _write_file to raise after the master has been written.
        write_call_count = 0
        original_write = __import__("personalscraper.conf.migration", fromlist=["_write_file"])._write_file

        def _failing_write(path: Path, content: str) -> None:
            nonlocal write_call_count
            write_call_count += 1
            if write_call_count >= 3:
                # Fail on the third write (first overlay file).
                raise OSError("simulated disk full")
            original_write(path, content)

        with patch("personalscraper.conf.migration._write_file", side_effect=_failing_write):
            with pytest.raises(MigrationError, match="in-progress"):
                migrate_v1_to_v2(legacy, target)

        # .in-progress/ must be present.
        assert in_progress.is_dir(), ".in-progress/ must be left after failure"
        # target_dir must NOT be present (rename never happened).
        assert not target.exists(), "target_dir must not exist after partial failure"

    def test_stale_in_progress_cleaned_before_retry(self, tmp_path: Path) -> None:
        """A stale .in-progress/ from a previous failure is removed before the new attempt."""
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        in_progress = Path(str(target) + ".in-progress")

        # Create a stale .in-progress/ to simulate a previous failure.
        in_progress.mkdir()
        (in_progress / "stale_file.txt").write_text("stale", encoding="utf-8")

        migrate_v1_to_v2(legacy, target)

        # Migration must succeed and the stale sentinel gone.
        assert target.is_dir()
        assert not in_progress.exists()

    def test_v1_bak_not_written_when_migration_fails(self, tmp_path: Path) -> None:
        """The .v1.bak rename must NOT happen when migration fails mid-write."""
        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        bak = Path(str(legacy) + ".v1.bak")

        write_call_count = 0
        original_write = __import__("personalscraper.conf.migration", fromlist=["_write_file"])._write_file

        def _failing_write(path: Path, content: str) -> None:
            nonlocal write_call_count
            write_call_count += 1
            if write_call_count >= 3:
                raise OSError("simulated error")
            original_write(path, content)

        with patch("personalscraper.conf.migration._write_file", side_effect=_failing_write):
            with pytest.raises(MigrationError):
                migrate_v1_to_v2(legacy, target)

        # Legacy file must still exist (not renamed to .bak).
        assert legacy.exists()
        assert not bak.exists()


# ---------------------------------------------------------------------------
# CLI integration via Typer test runner
# ---------------------------------------------------------------------------


class TestCliMigrateToV2:
    """Tests for the ``personalscraper config migrate-to-v2`` CLI command."""

    def test_cli_dry_run_exits_zero_no_files_written(self, tmp_path: Path) -> None:
        """--dry-run must exit 0 without writing any files."""
        from personalscraper.cli import app

        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"

        runner = make_cli_runner()
        result = runner.invoke(app, ["config", "migrate-to-v2", "--dry-run", str(legacy), str(target)])
        assert result.exit_code == 0, result.output
        assert not target.exists()

    def test_cli_dry_run_mentions_files(self, tmp_path: Path) -> None:
        """--dry-run output must mention the overlay filenames."""
        from personalscraper.cli import app

        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"

        runner = make_cli_runner()
        result = runner.invoke(app, ["config", "migrate-to-v2", "--dry-run", str(legacy), str(target)])
        assert "paths.json5" in result.output
        assert "disks.json5" in result.output

    def test_cli_migration_success(self, tmp_path: Path) -> None:
        """Real migration via CLI must create target_dir and exit 0."""
        from personalscraper.cli import app

        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"

        runner = make_cli_runner()
        result = runner.invoke(app, ["config", "migrate-to-v2", str(legacy), str(target)])
        assert result.exit_code == 0, result.output
        assert target.is_dir()

    def test_cli_missing_legacy_exits_nonzero(self, tmp_path: Path) -> None:
        """CLI must exit non-zero when legacy file is absent."""
        from personalscraper.cli import app

        runner = make_cli_runner()
        result = runner.invoke(
            app, ["config", "migrate-to-v2", str(tmp_path / "noexist.json5"), str(tmp_path / "config")]
        )
        assert result.exit_code != 0

    def test_cli_already_migrated_exits_zero(self, tmp_path: Path) -> None:
        """CLI must exit 0 with a message when target_dir is already migrated."""
        from personalscraper.cli import app

        legacy = _write_v1(tmp_path)
        target = tmp_path / "config"
        # First migration.
        migrate_v1_to_v2(legacy, target)

        # Write a second legacy file to try again.
        legacy2 = _write_v1(tmp_path)

        runner = make_cli_runner()
        result = runner.invoke(app, ["config", "migrate-to-v2", str(legacy2), str(target)])
        assert result.exit_code == 0
        assert "Already migrated" in result.output or "already" in result.output.lower()
