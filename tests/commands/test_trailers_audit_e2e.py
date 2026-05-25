"""E2E tests for ``personalscraper trailers audit`` — CLI-level harness.

Exercises the canonical ``trailers audit`` command (formerly ``trailers verify``,
renamed in 8.6 / SH-22 and the deprecated alias dropped pre-merge to honour the
"no rétro-compat shims before v1.0" rule) via CliRunner with mocked
``_audit_impl``. Follows the 4-section non-critical pattern
(Smoke / Realistic / Errors / Output).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.commands._e2e_helpers import assert_no_python_traceback, run_cli

# ── 1. Smoke ────────────────────────────────────────────────────────────────────


def test_trailers_audit_help_exits_zero() -> None:
    """``trailers audit --help`` exits 0 and mentions the canonical name."""
    result = run_cli(["trailers", "audit", "--help"])
    assert result.exit_code == 0, result.output
    assert "audit" in result.output.lower()


# ── 2. Realistic scenarios ──────────────────────────────────────────────────────


@patch("personalscraper.trailers.cli._audit_impl")
def test_trailers_audit_invokes_audit_impl(mock_audit_impl: MagicMock) -> None:
    """``trailers audit`` delegates exactly once to the shared ``_audit_impl``."""
    result = run_cli(["trailers", "audit"])

    assert result.exit_code == 0, result.output
    mock_audit_impl.assert_called_once()


@patch("personalscraper.trailers.cli._audit_impl")
def test_trailers_audit_forwards_args(mock_audit_impl: MagicMock) -> None:
    """Filter flags surface as kwargs on the ``_audit_impl`` call."""
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

    kwargs = mock_audit_impl.call_args.kwargs
    assert kwargs.get("disk") == "drive_a"
    assert kwargs.get("category") == "movies"
    assert kwargs.get("level") == "show"


# ── 3. Errors ───────────────────────────────────────────────────────────────────


@patch("personalscraper.trailers.cli._audit_impl")
def test_trailers_audit_impl_error_bubbles_up(mock_audit_impl: MagicMock) -> None:
    """When ``_audit_impl`` raises ``Exit(2)``, audit exits 2 with no traceback."""
    import typer  # noqa: PLC0415

    mock_audit_impl.side_effect = typer.Exit(code=2)

    result = run_cli(["trailers", "audit"])

    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}: {result.output}"
    assert_no_python_traceback(result)


# ── 4. Output (--format json) ────────────────────────────────────────────────────
# N/A — ``trailers audit`` does not support ``--format json``. It uses Rich
# console directly for the table of issues — JSON output would require an
# additional schema design that has not been scoped.
