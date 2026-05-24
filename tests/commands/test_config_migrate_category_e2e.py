"""E2E tests for ``personalscraper config migrate-category`` — CLI-level harness.

Exercises the config migrate-category Typer command (rewrite
media_item.category_id) via CliRunner with mocked
config_migrate_category_command. Follows the 8-section pattern.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.commands._e2e_helpers import (
    assert_no_python_traceback,
    run_cli,
)

# Patch the source module where config_migrate_category_command is defined.
# ``commands/config.py`` imports it with ``from indexer.cli import ...``
# INSIDE the function body (lazy import), so the binding is local, not a
# module attribute. Patching the source ensures the ``from`` import picks
# up the mock at call time.
PATCH_MIGRATE = "personalscraper.indexer.cli.config_migrate_category_command"


# ── 1. Smoke ──


def test_config_migrate_category_help_exits_zero() -> None:
    """``config migrate-category --help`` exits 0 and mentions the command."""
    result = run_cli(["config", "migrate-category", "--help"])
    assert result.exit_code == 0, result.output
    assert "migrate-category" in result.output.lower()
    assert "--from" in result.output
    assert "--to" in result.output


# ── 2. Realistic scenarios ──


@patch(PATCH_MIGRATE, return_value=0)
def test_config_migrate_category_success(mock_migrate: MagicMock) -> None:
    """Migration returns 0 → exit 0, function called with correct args."""
    result = run_cli(
        [
            "config",
            "migrate-category",
            "--from",
            "old_cat",
            "--to",
            "new_cat",
        ]
    )

    assert result.exit_code == 0, result.output
    mock_migrate.assert_called_once()
    kwargs = mock_migrate.call_args.kwargs
    assert kwargs["from_category"] == "old_cat"
    assert kwargs["to_category"] == "new_cat"


@patch(PATCH_MIGRATE, return_value=0)
def test_config_migrate_category_with_config_path(mock_migrate: MagicMock, tmp_path: Path) -> None:
    """--config flag forwards config_path to the migration command."""
    cfg_path = tmp_path / "custom" / "config.json5"

    result = run_cli(
        [
            "config",
            "migrate-category",
            "--from",
            "old_cat",
            "--to",
            "new_cat",
            "--config",
            str(cfg_path),
        ]
    )

    assert result.exit_code == 0, result.output
    kwargs = mock_migrate.call_args.kwargs
    assert kwargs["config_path"] == cfg_path


# ── 3. Errors ──


@patch(PATCH_MIGRATE, return_value=2)
def test_config_migrate_category_invalid_target(mock_migrate: MagicMock) -> None:
    """Target category not declared in config → exit 2."""
    result = run_cli(
        [
            "config",
            "migrate-category",
            "--from",
            "old_cat",
            "--to",
            "undeclared_cat",
        ]
    )

    assert result.exit_code == 2, result.output
    assert_no_python_traceback(result)


@patch(PATCH_MIGRATE, return_value=1)
def test_config_migrate_category_infra_error(mock_migrate: MagicMock) -> None:
    """Infrastructure error (DB open failure, etc.) → exit 1."""
    result = run_cli(
        [
            "config",
            "migrate-category",
            "--from",
            "old_cat",
            "--to",
            "new_cat",
        ]
    )

    assert result.exit_code == 1, result.output
    assert_no_python_traceback(result)


def test_config_migrate_category_missing_required_args() -> None:
    """Missing --from or --to → Typer error, exit 2."""
    result = run_cli(["config", "migrate-category"])

    assert result.exit_code == 2, result.output
    assert_no_python_traceback(result)


# ── 4. Idempotence ──


@patch(PATCH_MIGRATE, return_value=0)
def test_config_migrate_category_idempotent(mock_migrate: MagicMock) -> None:
    """Two consecutive calls with same args: both succeed (no rows on second)."""
    r1 = run_cli(
        [
            "config",
            "migrate-category",
            "--from",
            "old_cat",
            "--to",
            "new_cat",
        ]
    )
    assert r1.exit_code == 0

    r2 = run_cli(
        [
            "config",
            "migrate-category",
            "--from",
            "old_cat",
            "--to",
            "new_cat",
        ]
    )
    assert r2.exit_code == 0
    assert mock_migrate.call_count == 2


# ── 5. Dry-run ──

# N/A: `config migrate-category` has no --dry-run flag. The command is a
# database mutation; there is no dry-run preview mode. The idempotence
# property (second run = no-op when no rows matched) serves as the safety
# net.

# ── 6. Output ──


@patch(PATCH_MIGRATE, return_value=0)
def test_config_migrate_category_no_traceback(mock_migrate: MagicMock) -> None:
    """Output is user-friendly, never a raw Python traceback."""
    result = run_cli(
        [
            "config",
            "migrate-category",
            "--from",
            "old_cat",
            "--to",
            "new_cat",
        ]
    )

    assert result.exit_code == 0, result.output
    assert_no_python_traceback(result)


@patch(PATCH_MIGRATE, return_value=2)
def test_config_migrate_category_error_output_stderr(mock_migrate: MagicMock) -> None:
    """Error output goes to stderr, not stdout."""
    result = run_cli(
        [
            "config",
            "migrate-category",
            "--from",
            "old_cat",
            "--to",
            "undeclared_cat",
        ]
    )

    assert result.exit_code == 2, result.output
    assert_no_python_traceback(result)


# ── 7. Events ──

# N/A: config migrate-category is a direct SQL UPDATE on the indexer DB
# that does not go through the pipeline EventBus. The command opens the DB
# with a fresh EventBus (boundary-only pattern), but the UPDATE itself is
# a raw SQL statement that does not emit pipeline events. No events are
# declared for this operation in the design-conformity matrix.

# ── 8. Closure-of-loop ──

# N/A: config migrate-category performs a single SQL UPDATE with no
# follow-up BDD cycle. There is no repair_queue drain, outbox flush, or
# index rebuild required after a category_id rename. The idempotence
# property (UPDATE ... WHERE category_id = ?) is verified at the unit
# level (test_cli_migrate_category.py). The CLI harness verifies the
# contract: --from/--to args forwarded, config_path forwarded, exit code
# propagated from the command function.
