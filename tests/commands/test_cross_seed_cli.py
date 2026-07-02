"""CLI tests for ``personalscraper cross-seed`` commands.

Covers the ``--sweep`` and ``--hash`` sub-commands registered in
:mod:`personalscraper.commands.cross_seed`, including mutual-exclusion
gating, the ``--help`` output (ACC-5), and the "no compatible torrent
client" path.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.acquire.cross_seed import CrossSeedResult, SweepResult
from personalscraper.cli_state import AppCtx

runner = CliRunner()


def _make_app() -> Any:
    """Import the root CLI app, triggering ``cross-seed`` registration."""
    import personalscraper.cli as _cli  # noqa: F401
    from personalscraper.cli_app import app

    return app


def _invoke(args: list[str], *, cross_seed_service: Any = None) -> Any:
    """Invoke ``cross-seed`` with mocked ``per_step_boundary`` and ``get_settings``.

    Patches both so no real ``config/`` or torrent client is needed.  The
    autouse ``_mock_cli_config_load`` fixture in ``tests/commands/conftest.py``
    already patches ``load_config`` → ``test_config`` for CI safety; this
    helper replaces the context-manager boundary that would otherwise try to
    build a real :class:`~personalscraper.acquire.context.AcquireContext`.

    Args:
        args: CLI args (e.g. ``["cross-seed", "--sweep"]``).
        cross_seed_service: Mock :class:`CrossSeedService` to inject, or
            ``None`` to simulate "not configured"
            (``acquire.cross_seed is None``).

    Returns:
        The :class:`typer.testing.Result` from ``CliRunner.invoke``.
    """
    app = _make_app()

    mock_acquire = MagicMock()
    mock_acquire.cross_seed = cross_seed_service

    mock_app_context = MagicMock()
    mock_app_context.acquire = mock_acquire

    with (
        patch("personalscraper.commands.cross_seed.per_step_boundary") as mock_boundary,
        patch("personalscraper.commands.cross_seed.cli_compat.get_settings", return_value=MagicMock()),
    ):
        mock_boundary.return_value.__enter__ = MagicMock(return_value=mock_app_context)
        mock_boundary.return_value.__exit__ = MagicMock(return_value=False)

        obj = AppCtx(config=MagicMock(), config_override=None)
        result = runner.invoke(app, args, obj=obj)

    return result


# ── 1.  --sweep ────────────────────────────────────────────────────────────


def test_cross_seed_sweep_exits_zero() -> None:
    """``cross-seed --sweep`` exits 0 when the sweep completes successfully."""
    mock_service = MagicMock()
    mock_service.sweep.return_value = SweepResult(checked=0, injected=0, quota_exhausted=False)

    result = _invoke(["cross-seed", "--sweep"], cross_seed_service=mock_service)

    assert result.exit_code == 0, f"Expected exit 0; got {result.exit_code}:\n{result.output}"
    mock_service.sweep.assert_called_once()


# ── 2.  --hash ─────────────────────────────────────────────────────────────


def test_cross_seed_hash_exits_zero() -> None:
    """``cross-seed --hash H`` exits 0 when the check returns skipped."""
    mock_service = MagicMock()
    mock_service.check.return_value = CrossSeedResult(
        injected=[],
        rejected=[],
        skipped=True,
        skip_reason="disabled",
    )

    result = _invoke(["cross-seed", "--hash", "abc123"], cross_seed_service=mock_service)

    assert result.exit_code == 0, f"Expected exit 0; got {result.exit_code}:\n{result.output}"
    mock_service.check.assert_called_once_with("abc123")


# ── 3.  No args (mutual exclusion) ─────────────────────────────────────────


def test_cross_seed_no_args_exits_two() -> None:
    """``cross-seed`` with no args exits 2 — at least one flag required."""
    result = _invoke(["cross-seed"])

    assert result.exit_code == 2, f"Expected exit 2; got {result.exit_code}:\n{result.output}"


# ── 4.  Both --sweep and --hash (mutual exclusion) ─────────────────────────


def test_cross_seed_both_args_exits_two() -> None:
    """``cross-seed --sweep --hash H`` exits 2 — mutual exclusion."""
    result = _invoke(["cross-seed", "--sweep", "--hash", "abc123"])

    assert result.exit_code == 2, f"Expected exit 2; got {result.exit_code}:\n{result.output}"


# ── 5.  --help (ACC-5) ─────────────────────────────────────────────────────


def test_cross_seed_help_shows_options() -> None:
    """ACC-5: ``--sweep`` and ``--hash`` are documented in help output."""
    app = _make_app()
    result = runner.invoke(app, ["cross-seed", "--help"])

    assert result.exit_code == 0, result.output
    assert "--sweep" in result.output, f"Expected --sweep in help output; got:\n{result.output}"
    assert "--hash" in result.output, f"Expected --hash in help output; got:\n{result.output}"


# ── 6.  Service handle is None ─────────────────────────────────────────────


def test_cross_seed_service_none_exits_one() -> None:
    """When ``acquire.cross_seed is None``, exits 1 with clear message."""
    result = _invoke(["cross-seed", "--sweep"], cross_seed_service=None)

    assert result.exit_code == 1, f"Expected exit 1; got {result.exit_code}:\n{result.output}"
    assert "no compatible torrent client" in result.output.lower() or "not available" in result.output.lower(), (
        f"Expected 'not available' or 'no compatible torrent client' in output; got:\n{result.output}"
    )


# ── 7.  Sweep lister failure → exit 1 (sub-phase 10.7b) ───────────────────


def test_cross_seed_sweep_lister_failed_exits_one() -> None:
    """``cross-seed --sweep`` exits 1 when ``lister_failed`` is True."""
    mock_service = MagicMock()
    mock_service.sweep.return_value = SweepResult(
        checked=0,
        injected=0,
        quota_exhausted=False,
        lister_failed=True,
    )

    result = _invoke(["cross-seed", "--sweep"], cross_seed_service=mock_service)

    assert result.exit_code == 1, f"Expected exit 1 for lister_failed; got {result.exit_code}:\n{result.output}"
    assert "could not enumerate" in result.output.lower() or "failed" in result.output.lower(), (
        f"Expected red error about enumeration failure; got:\n{result.output}"
    )


# ── 8.  Sweep item_errors → yellow warning, total-failure exit (11.4) ────────


def test_sweep_item_errors_yellow_warning_exit_zero() -> None:
    """Item errors > 0 but checked > 0 → yellow warning, exit 0 (partial success)."""
    mock_service = MagicMock()
    mock_service.sweep.return_value = SweepResult(
        checked=5,
        injected=3,
        item_errors=2,
        quota_exhausted=False,
    )

    result = _invoke(["cross-seed", "--sweep"], cross_seed_service=mock_service)

    assert result.exit_code == 0, f"Expected exit 0 for partial success; got {result.exit_code}:\n{result.output}"
    assert "2 item error" in result.output.lower(), (
        f"Expected yellow warning about 2 item errors; got:\n{result.output}"
    )
    assert "Sweep complete" in result.output, (
        f"Expected green Sweep complete; got:\n{result.output}"
    )


def test_sweep_all_items_errored_exit_one() -> None:
    """All items errored (item_errors > 0, checked == 0) → exit 1 (total failure)."""
    mock_service = MagicMock()
    mock_service.sweep.return_value = SweepResult(
        checked=0,
        injected=0,
        item_errors=3,
        quota_exhausted=False,
    )

    result = _invoke(["cross-seed", "--sweep"], cross_seed_service=mock_service)

    assert result.exit_code == 1, f"Expected exit 1 for total failure; got {result.exit_code}:\n{result.output}"
    assert "all items raised errors" in result.output.lower() or "sweep failed" in result.output.lower(), (
        f"Expected red 'all items raised errors' or 'Sweep failed'; got:\n{result.output}"
    )
