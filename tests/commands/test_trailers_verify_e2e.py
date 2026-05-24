"""E2E tests for ``personalscraper trailers verify`` — CLI-level harness.

Exercises the deprecated ``trailers verify`` alias (→ ``trailers audit`` per
8.6 / SH-22) via CliRunner with mocked ``_audit_impl``.  Follows the
4-section non-critical pattern (Smoke / Realistic / Errors / Output).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.commands._e2e_helpers import assert_no_python_traceback, run_cli

# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_trailers_verify_help_exits_zero() -> None:
    """``trailers verify --help`` exits 0 and mentions deprecation."""
    result = run_cli(["trailers", "verify", "--help"])
    assert result.exit_code == 0, result.output
    # The docstring mentions deprecation in the help text.
    assert "deprecated" in result.output.lower()
    assert "audit" in result.output


# ── 2. Realistic scenarios ──────────────────────────────────────────────────────


@patch("personalscraper.trailers.cli._audit_impl")
def test_trailers_verify_prints_deprecation_notice_on_stderr(
    mock_audit_impl: MagicMock,
) -> None:
    """Running ``trailers verify`` prints deprecation notice to stderr."""
    result = run_cli(["trailers", "verify"])

    # _audit_impl was called (exits 0 since we mock it to return None).
    assert result.exit_code == 0, result.output
    mock_audit_impl.assert_called_once()
    # Deprecation notice on stderr (Typer's mix_stderr behaviour).
    assert "DEPRECATED" in (result.stderr or "")


@patch("personalscraper.trailers.cli._audit_impl")
def test_trailers_verify_forwards_same_args_as_audit(
    mock_audit_impl: MagicMock,
) -> None:
    """Both ``trailers verify`` and ``trailers audit`` call ``_audit_impl`` identically."""
    # Call verify with specific args.
    run_cli(
        [
            "trailers",
            "verify",
            "--disk",
            "drive_a",
            "--category",
            "movies",
            "--level",
            "show",
        ]
    )
    verify_kwargs = mock_audit_impl.call_args.kwargs

    # Reset and call audit with the same args.
    mock_audit_impl.reset_mock()
    run_cli(
        [
            "trailers",
            "audit",
            "--disk",
            "drive_a",
            "--category",
            "movies",
            "--level",
            "show",
        ]
    )
    audit_kwargs = mock_audit_impl.call_args.kwargs

    # Strip ctx from both — it's a different CliRunner context each time.
    assert verify_kwargs == audit_kwargs, f"verify kwargs: {verify_kwargs}\naudit kwargs: {audit_kwargs}"


# ── 3. Errors ───────────────────────────────────────────────────────────────────


@patch("personalscraper.trailers.cli._audit_impl")
def test_trailers_verify_audit_impl_error_bubbles_up(
    mock_audit_impl: MagicMock,
) -> None:
    """When ``_audit_impl`` raises ``Exit(2)``, verify exits 2 + prints deprecation."""
    import typer

    mock_audit_impl.side_effect = typer.Exit(code=2)

    result = run_cli(["trailers", "verify"])

    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}: {result.output}"
    # Deprecation notice fires before delegation.
    assert "DEPRECATED" in (result.stderr or "")
    assert_no_python_traceback(result)


# ── 4. Output (--format json) ────────────────────────────────────────────────────
# N/A — ``trailers verify`` (and ``trailers audit``) do not support ``--format json``.
# Both use Rich console directly.
