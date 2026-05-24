"""E2E tests for ``personalscraper init-config`` — CLI-level harness.

Exercises the init-config Typer command (config bootstrap from template)
via CliRunner with real/minimal example directories. Follows the
8-section pattern.
"""

from __future__ import annotations

from pathlib import Path

from tests.commands._e2e_helpers import (
    assert_no_python_traceback,
    run_cli,
)


def _make_minimal_example(tmp_path: Path) -> Path:
    """Create a minimal config.example/ directory for testing."""
    example = tmp_path / "config.example"
    example.mkdir()
    (example / "config.json5").write_text('{\n  "version": "1.0",\n  "description": "Test config"\n}\n')
    (example / "paths.json5").write_text(
        '{\n  "paths": {\n    "torrent_complete_dir": "/tmp/torrents",\n'
        '    "staging_dir": "./staging/",\n'
        '    "data_dir": "./.data"\n  }\n}\n'
    )
    (example / "disks.json5").write_text('{\n  "disks": []\n}\n')
    (example / "categories.json5").write_text('{\n  "categories": {}\n}\n')
    return example


# ── 1. Smoke ──


def test_init_config_help_exits_zero() -> None:
    """``init-config --help`` exits 0 and mentions the command name."""
    result = run_cli(["init-config", "--help"])
    assert result.exit_code == 0, result.output
    assert "init-config" in result.output.lower()
    assert "--dry-run" in result.output


# ── 2. Realistic scenarios ──


def test_init_config_creates_config_from_example(tmp_path: Path) -> None:
    """Minimal example → files created at output, success message printed."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--yes",
            "--force",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 0, result.output
    assert output.is_dir()
    assert (output / "config.json5").is_file()
    assert (output / "paths.json5").is_file()
    assert "created" in result.output.lower()


def test_init_config_yes_flag_non_interactive(tmp_path: Path) -> None:
    """--yes flag delegates to init_config with interactive=False."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--yes",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 0, result.output
    assert output.is_dir()


def test_init_config_force_overwrites_existing(tmp_path: Path) -> None:
    """--force backs up existing config dir and writes new one."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"
    output.mkdir()
    (output / "old-file.json5").write_text("{}")

    result = run_cli(
        [
            "init-config",
            "--yes",
            "--force",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 0, result.output
    assert output.is_dir()
    assert (output / "config.json5").is_file()
    # The old file should be in the backup.
    bak = tmp_path / "config.bak"
    assert bak.exists()
    assert (bak / "old-file.json5").is_file()


# ── 3. Errors ──


def test_init_config_missing_example_exits_2(tmp_path: Path) -> None:
    """Nonexistent example dir → exit 2, friendly error message."""
    result = run_cli(
        [
            "init-config",
            "--yes",
            "--example",
            str(tmp_path / "nonexistent"),
            "--output",
            str(tmp_path / "config"),
        ]
    )

    assert result.exit_code == 2, result.output
    assert "not found" in result.output.lower()
    assert_no_python_traceback(result)


def test_init_config_output_exists_without_force(tmp_path: Path) -> None:
    """Existing output dir without --force → exit 2, friendly message."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"
    output.mkdir()

    result = run_cli(
        [
            "init-config",
            "--yes",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 2, result.output
    assert "already exists" in result.output.lower()
    assert_no_python_traceback(result)


# ── 4. Idempotence ──


def test_init_config_idempotent_with_force(tmp_path: Path) -> None:
    """Two consecutive --force runs both succeed."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"

    r1 = run_cli(
        [
            "init-config",
            "--yes",
            "--force",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )
    assert r1.exit_code == 0

    r2 = run_cli(
        [
            "init-config",
            "--yes",
            "--force",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )
    assert r2.exit_code == 0
    assert output.is_dir()


# ── 5. Dry-run ──


def test_init_config_dry_run_does_not_create_files(tmp_path: Path) -> None:
    """--dry-run exits 0 without creating any files at the output path."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--dry-run",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert not output.exists(), f"--dry-run must not create {output}"


def test_init_config_dry_run_reports_example_missing(tmp_path: Path) -> None:
    """--dry-run with missing example → WARNING, exit 0."""
    result = run_cli(
        [
            "init-config",
            "--dry-run",
            "--example",
            str(tmp_path / "nonexistent"),
            "--output",
            str(tmp_path / "config"),
        ]
    )

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert "WARNING" in result.output


def test_init_config_dry_run_warns_existing_output(tmp_path: Path) -> None:
    """--dry-run with existing output → warns about --force, exit 0."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"
    output.mkdir()

    result = run_cli(
        [
            "init-config",
            "--dry-run",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert "already exists" in result.output.lower()


# ── 6. Output ──


def test_init_config_no_traceback(tmp_path: Path) -> None:
    """Output is Rich-formatted, never a raw Python traceback."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--yes",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 0, result.output
    assert_no_python_traceback(result)


def test_init_config_next_steps_printed(tmp_path: Path) -> None:
    """Success output includes next steps guidance."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--yes",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 0, result.output
    assert "Next steps" in result.output


def test_init_config_error_output_user_friendly(tmp_path: Path) -> None:
    """Error output mentions the issue clearly, no traceback."""
    output = tmp_path / "config"
    output.mkdir()

    # Missing example with existing output → should mention both issues clearly.
    result = run_cli(
        [
            "init-config",
            "--yes",
            "--example",
            str(tmp_path / "nonexistent"),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 2, result.output
    assert_no_python_traceback(result)
    assert "not found" in result.output.lower()


# ── 7. Events ──

# N/A: init-config is a filesystem bootstrap operation that runs before any
# config or BDD exists. It has no EventBus — the command body constructs a
# Config-free AppContext only when a config is loaded, which is not the case
# for init-config (it runs before config exists). No pipeline events are
# relevant.

# ── 8. Closure-of-loop ──

# N/A: init-config creates config files from a template; there is no BDD
# cycle to close. The files are written once and verified by template-copy
# correctness at the module level (test_init_config.py). The E2E CLI harness
# verifies the contract: example dir read, output dir created, interactive
# mode delegated correctly.
