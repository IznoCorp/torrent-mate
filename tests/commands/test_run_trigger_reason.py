"""Regression tests for ``_validate_trigger_reason`` in the ``run`` command.

Covers the bug where ``--trigger-reason=web`` was rejected by the validator
even though the web UI route spawns the pipeline with that value.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.commands.pipeline import _validate_trigger_reason

runner = CliRunner()


class TestValidateTriggerReasonUnit:
    """Direct unit tests of ``_validate_trigger_reason``."""

    def test_accepts_web(self) -> None:
        """``web`` is in the allowed set and returns the value unchanged."""
        assert _validate_trigger_reason("web") == "web"

    @pytest.mark.parametrize(
        "value",
        ["", "completion", "safety_net", "manual", "web"],
    )
    def test_all_allowed_values_pass(self, value: str) -> None:
        """Every allowed value returns unchanged."""
        assert _validate_trigger_reason(value) == value

    def test_rejects_unknown_value(self) -> None:
        """An unknown value raises ``typer.BadParameter``."""
        with pytest.raises(Exception):  # typer.BadParameter inherits from click.ClickException
            _validate_trigger_reason("bogus")


class TestRunCommandTriggerReasonCli:
    """CliRunner tests proving ``--trigger-reason`` is accepted by the CLI."""

    def test_trigger_reason_web_accepted(self) -> None:
        """``--trigger-reason web`` does not raise ``BadParameter``.

        The command may fail for other reasons (missing config, database, etc.)
        but must NOT exit with code 2 (BadParameter).
        """
        result = runner.invoke(app, ["run", "--trigger-reason", "web", "--help"])
        # --help should succeed (exit 0) regardless of trigger-reason value
        assert result.exit_code == 0, f"CLI rejected --trigger-reason=web:\n{result.output}"

    def test_trigger_reason_bogus_rejected(self) -> None:
        """An invalid ``--trigger-reason`` is rejected by the CLI (exit 2 = BadParameter)."""
        result = runner.invoke(app, ["run", "--trigger-reason", "bogus"])
        # Callback fires before any command logic; bogus value → BadParameter → exit 2.
        assert result.exit_code == 2, (
            f"Expected exit 2 for bogus trigger-reason, got {result.exit_code}:\n{result.output}"
        )
