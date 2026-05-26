"""Regression: every pipeline subcommand has @cli_telemetry applied.

DEV #1/#6 (Phase 12.5 / tech-debt 0.16.0) — only ``ingest`` was bracketed by
``@cli_telemetry``; ``sort``, ``verify``, and 7 other pipeline subcommands
produced zero ``cli.invoke.*`` / ``cli.complete.*`` events. The pipeline-monitor
host process couldn't capture a unified entry/exit pair per step.

Verification is via static inspection of the ``__wrapped__`` chain (the
"acceptable shortcut" from plan §12.5). Without ``@cli_telemetry``, the chain is
only 1 level deep (``@handle_cli_errors`` wraps the original function). With
``@cli_telemetry`` applied between ``@app.command()`` and ``@handle_cli_errors``,
the chain is 2 levels: ``cli_telemetry.wrapper`` → ``handle_cli_errors`` wrapper
→ original function.
"""

from __future__ import annotations

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

PIPELINE_COMMAND_NAMES: list[str] = [
    "ingest",
    "sort",
    "scrape",
    "verify",
    "enforce",
    "dispatch",
    "clean",
    "cleanup",
    "process",
    "run",
    "torrents_list",
]


def _wrapped_depth(fn: object) -> int:
    """Count how many times ``fn.__wrapped__`` chains before stopping."""
    depth = 0
    cur = fn
    while hasattr(cur, "__wrapped__"):
        cur = cur.__wrapped__
        depth += 1
    return depth


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cmd_fn_name", PIPELINE_COMMAND_NAMES)
def test_cli_telemetry_applied_via_wrapped_chain(cmd_fn_name: str) -> None:
    """Every pipeline command has @cli_telemetry (depth >= 2 via __wrapped__).

    Without ``@cli_telemetry``, the chain is only 1 level deep (``@handle_cli_errors``
    wraps the original). With ``@cli_telemetry`` applied between ``@app.command()``
    and ``@handle_cli_errors``, the chain depth is 2: cli_telemetry.wrapper →
    handle_cli_errors wrapper → original function.
    """
    from personalscraper.commands import pipeline  # noqa: PLC0415

    fn = getattr(pipeline, cmd_fn_name)
    depth = _wrapped_depth(fn)
    assert depth >= 2, (
        f"{cmd_fn_name}: expected __wrapped__ depth >= 2 "
        f"(both @cli_telemetry + @handle_cli_errors applied), got {depth}"
    )
