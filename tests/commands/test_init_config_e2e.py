"""E2E tests for ``personalscraper init-config`` — CLI-level harness.

Exercises the init-config Typer command (config bootstrap from template)
via CliRunner with real/minimal example directories. Follows the
8-section pattern.
"""

from __future__ import annotations

from pathlib import Path

import json5

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


# ── 7. --sync flag ──


def test_init_config_sync_dry_run_reports(tmp_path: Path) -> None:
    """``init-config --sync --dry-run`` exits 0, reports DRY-RUN, creates no files."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--sync",
            "--dry-run",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    # Dry-run must NOT create the target directory at all.
    assert not output.exists(), f"--sync --dry-run must not create {output}"


def test_init_config_sync_additive_apply(tmp_path: Path) -> None:
    """``init-config --sync`` copies missing files from example to target."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--sync",
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


def test_init_config_sync_and_force_mutually_exclusive(tmp_path: Path) -> None:
    """``init-config --sync --force`` exits 2 with a clear error message."""
    example = _make_minimal_example(tmp_path)
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--sync",
            "--force",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 2, result.output
    assert "mutually exclusive" in result.output.lower()
    assert_no_python_traceback(result)


# ── 8. Malformed JSON5 (F-C) ──


def test_init_config_sync_malformed_json5_clean_error(tmp_path: Path) -> None:
    """Malformed JSON5 in example → clean user error, exit 1, no traceback."""
    example = tmp_path / "config.example"
    example.mkdir()
    (example / "config.json5").write_text("{\n  valid: true\n}\n")
    (example / "broken.json5").write_text("not valid { json ~~~\n")
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--sync",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    assert result.exit_code == 1, result.output
    assert "broken.json5" in result.output
    assert_no_python_traceback(result)


# ── 8c. M8: non-iterable overlays guard ──


def test_init_config_sync_non_iterable_overlays_no_traceback(tmp_path: Path) -> None:
    """Non-iterable overlays (e.g. int 5) → clean report, exit 0, no traceback (M8).

    Before the fix, ``list(5)`` raised TypeError through the CLI as a raw
    Python traceback.  The guard (isinstance list check) catches it and emits
    a clean conflict report line instead.
    """
    example = tmp_path / "config.example"
    example.mkdir()
    (example / "config.json5").write_text(
        json5.dumps({"config_version": 1, "overlays": 5}, indent=2)
    )
    (example / "paths.json5").write_text('{"paths": {"staging_dir": "/s"}}')
    output = tmp_path / "config"

    result = run_cli(
        [
            "init-config",
            "--sync",
            "--example",
            str(example),
            "--output",
            str(output),
        ]
    )

    # Must exit cleanly (0).
    assert result.exit_code == 0, result.output
    # No raw traceback.
    assert_no_python_traceback(result)
    # Files were copied normally — the guard prevented the TypeError without
    # blocking the rest of the sync (no overlay names to register from int 5).
    assert "copy new file" in result.output.lower()


# ── 8b. F-G: --sync target resolution ──


def test_init_config_sync_no_output_no_env_fails(tmp_path: Path, monkeypatch) -> None:
    """``init-config --sync`` without --output and no env → exit 2, friendly message.

    Patches ``resolve_config_path`` to return a non-existent path so the guard
    fires (inside the repo the pkg_root/config fallback would prevent it).
    """
    from unittest.mock import patch

    monkeypatch.delenv("PERSONALSCRAPER_CONFIG", raising=False)
    example = _make_minimal_example(tmp_path)
    nonexistent = tmp_path / "nonexistent-config"

    with patch(
        "personalscraper.conf.loader.resolve_config_path",
        return_value=nonexistent,
    ):
        result = run_cli(
            [
                "init-config",
                "--sync",
                "--example",
                str(example),
            ]
        )

    assert result.exit_code == 2, result.output
    assert "not found" in result.output.lower()
    assert "PERSONALSCRAPER_CONFIG" in result.output
    assert_no_python_traceback(result)


def test_init_config_sync_with_env_works(tmp_path: Path, monkeypatch) -> None:
    """``init-config --sync`` with PERSONALSCRAPER_CONFIG → resolves target from env."""
    example = _make_minimal_example(tmp_path)
    target = tmp_path / "canonical"
    target.mkdir()

    monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(target))

    result = run_cli(
        [
            "init-config",
            "--sync",
            "--example",
            str(example),
        ]
    )

    assert result.exit_code == 0, result.output
    assert "Target config:" in result.output


def test_init_config_sync_output_explicit_wins(tmp_path: Path, monkeypatch) -> None:
    """``init-config --sync --output`` always wins over env or default."""
    example = _make_minimal_example(tmp_path)
    explicit = tmp_path / "my-config"
    explicit.mkdir()

    monkeypatch.setenv("PERSONALSCRAPER_CONFIG", str(tmp_path / "ignored"))

    result = run_cli(
        [
            "init-config",
            "--sync",
            "--example",
            str(example),
            "--output",
            str(explicit),
        ]
    )

    assert result.exit_code == 0, result.output


# ── 8c. F-J: sync commits the canonical mini-repo ──


def test_init_config_sync_commits_to_git_repo(tmp_path: Path) -> None:
    """``init-config --sync`` with git-initialized target creates a commit (F-J)."""
    import subprocess

    example = _make_minimal_example(tmp_path)
    target = tmp_path / "config"
    target.mkdir()

    # Init git repo + configure user.
    subprocess.run(
        ["git", "-C", str(target), "init"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "config", "user.email", "test@test"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "config", "user.name", "Test"],
        capture_output=True,
    )

    result = run_cli(
        [
            "init-config",
            "--sync",
            "--example",
            str(example),
            "--output",
            str(target),
        ]
    )

    assert result.exit_code == 0, result.output

    # Verify a commit was created.
    log = subprocess.run(
        ["git", "-C", str(target), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert "config_sync:" in log.stdout

    # ls-tree content assertion.
    ls = subprocess.run(
        ["git", "-C", str(target), "ls-tree", "-r", "HEAD", "--name-only"],
        capture_output=True,
        text=True,
    )
    files = ls.stdout.strip().splitlines()
    assert "config.json5" in files
    assert "paths.json5" in files


# ── 9. Events ──

# N/A: init-config is a filesystem bootstrap operation that runs before any
# config or BDD exists. It has no EventBus — the command body constructs a
# Config-free AppContext only when a config is loaded, which is not the case
# for init-config (it runs before config exists). No pipeline events are
# relevant.

# ── 9. Closure-of-loop ──

# N/A: init-config creates config files from a template; there is no BDD
# cycle to close. The files are written once and verified by template-copy
# correctness at the module level (test_init_config.py). The E2E CLI harness
# verifies the contract: example dir read, output dir created, interactive
# mode delegated correctly.
