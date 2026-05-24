"""E2E tests for ``personalscraper info`` — CLI-level harness.

Exercises the system info Typer command via CliRunner with the synthetic
test config.  Follows the 4-section non-critical pattern (Smoke /
Realistic / Errors / Output).  Events section is N/A — the info command
does not use ``@cli_telemetry`` (plan drift: §9.6 spec assumed
ACC-18 ``cli.invoke.info`` but the decorator was never applied).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tests.commands._e2e_helpers import (
    assert_json_schema,
    run_cli,
)

# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_info_help_exits_zero() -> None:
    """``info --help`` exits 0 and mentions the command."""
    result = run_cli(["info", "--help"])
    assert result.exit_code == 0, result.output
    assert "info" in result.output.lower()


# ── 2. Realistic scenarios ──────────────────────────────────────────────────────


def test_info_prints_version_and_config_and_disks() -> None:
    """``info`` prints app version, staging path, and per-disk status."""
    result = run_cli(["info"])

    assert result.exit_code == 0, result.output
    # Version header.
    assert "personalscraper" in result.output
    # Staging path section.
    assert "staging:" in result.output
    # Disks section — 3 disks from test_config.
    assert "Disks (3 configured)" in result.output
    assert "drive_a" in result.output
    assert "drive_b" in result.output
    assert "drive_c" in result.output


# ── 3. Errors ───────────────────────────────────────────────────────────────────


def test_info_collect_info_failure_exits_nonzero(monkeypatch) -> None:
    """When ``collect_info`` raises, info exits non-zero (no ``@handle_cli_errors``)."""
    monkeypatch.setattr(
        "personalscraper.info.run.collect_info",
        MagicMock(side_effect=RuntimeError("disk enumeration failed")),
    )

    result = run_cli(["info"])

    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}: {result.output}"
    # CliRunner stores unhandled exceptions; verify the cause is preserved.
    exc = getattr(result, "exception", None)
    assert exc is not None, "Expected exception to be captured by CliRunner"
    assert "disk enumeration failed" in str(exc)


# ── 4. Output (--format json) ────────────────────────────────────────────────────


def test_info_format_json_schema() -> None:
    """``--format json`` emits JSON with version/staging_path/disks keys."""
    result = run_cli(["--format", "json", "info"])

    assert result.exit_code == 0, result.output
    data = assert_json_schema(
        result,
        required_keys=["version", "staging_path", "disks"],
    )
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0
    assert isinstance(data["staging_path"], str)
    assert isinstance(data["disks"], list)
    assert len(data["disks"]) == 3

    # Each disk entry has expected keys.
    d0 = data["disks"][0]
    for key in ("name", "mounted", "total_bytes", "used_bytes"):
        assert key in d0, f"Missing key '{key}' in disk entry: {sorted(d0)}"
    assert isinstance(d0["name"], str)
    assert isinstance(d0["mounted"], bool)


# ── 5. Events ───────────────────────────────────────────────────────────────────
# N/A — ``info`` does not use ``@cli_telemetry`` (see module docstring).
