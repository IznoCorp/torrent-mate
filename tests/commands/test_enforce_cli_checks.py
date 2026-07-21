"""CLI tests for ``enforce --check`` and ``--list-checks`` flags.

Phase 6.2 — enforce uses CheckStage.STAGING. Tests are hermetic:
no real disk/network access.
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

from tests.commands._e2e_helpers import assert_no_python_traceback, run_cli

# The migrated verify/enforce commands take the lock + resolve settings via the
# ``cli_helpers.boundary`` decorator (thin command handles the pre-lock
# --list-checks / --check validation); patch that module's namespace, not
# ``personalscraper.cli.*``.
_BOUNDARY_MOD = importlib.import_module("personalscraper.cli_helpers.boundary")

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


# ── --list-checks ──


def test_enforce_list_checks_exits_zero(test_config) -> None:
    """Enforce --list-checks exits 0 and prints >=1 STAGING check."""
    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        result = run_cli(["enforce", "--list-checks"])

    assert result.exit_code == 0, result.output
    # STAGING checks — at least sort_process_coherence should be listed
    assert "sort_process_coherence" in result.output
    assert_no_python_traceback(result)


# ── --check bogus_name ──


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_check_bogus_name_exits_nonzero(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    test_config,
) -> None:
    """Enforce --check bogus_name exits != 0 with a hint."""
    from tests.fixtures.settings_stub import make_typed_settings_stub

    mock_settings.return_value = make_typed_settings_stub()

    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        result = run_cli(["enforce", "--check", "bogus_name"])

    assert result.exit_code != 0, result.output
    assert "bogus_name" in result.output
    assert_no_python_traceback(result)


# ── --check valid name (happy path) ──


@patch.object(_BOUNDARY_MOD, "get_settings")
@patch.object(_BOUNDARY_MOD, "release_lock")
@patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True)
@patch("personalscraper.enforce.run.run_enforce")
def test_enforce_check_known_name_forwards_only(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    test_config,
) -> None:
    """Enforce --check sort_process_coherence forwards only=frozenset to run_enforce."""
    from personalscraper.models import StepReport

    mock_run.return_value = StepReport(name="enforce")
    from tests.fixtures.settings_stub import make_typed_settings_stub

    mock_settings.return_value = make_typed_settings_stub()

    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        result = run_cli(["enforce", "--check", "sort_process_coherence"])

    assert result.exit_code == 0, result.output
    _, kwargs = mock_run.call_args
    assert kwargs.get("only") == frozenset({"sort_process_coherence"})
