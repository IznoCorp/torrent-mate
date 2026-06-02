"""CLI tests for ``verify --check`` and ``--list-checks`` flags.

Phase 6.2 — verify uses CheckStage.DISPATCH. Tests are hermetic:
no real disk/network access.
"""

from __future__ import annotations

from unittest.mock import patch

from tests.commands._e2e_helpers import assert_no_python_traceback, run_cli

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


# ── --list-checks ──


def test_verify_list_checks_exits_zero(test_config) -> None:
    """Verify --list-checks exits 0 and prints >=1 DISPATCH check."""
    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        result = run_cli(["verify", "--list-checks"])

    assert result.exit_code == 0, result.output
    # DISPATCH checks — at least nfo_present should be listed
    assert "nfo_present" in result.output
    assert_no_python_traceback(result)


# ── --check bogus_name ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_check_bogus_name_exits_nonzero(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    test_config,
) -> None:
    """Verify --check bogus_name exits != 0 with a hint."""
    from tests.fixtures.settings_stub import make_typed_settings_stub

    mock_settings.return_value = make_typed_settings_stub()

    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        result = run_cli(["verify", "--check", "bogus_name"])

    assert result.exit_code != 0, result.output
    assert "bogus_name" in result.output
    assert_no_python_traceback(result)


# ── --check valid name (happy path) ──


@patch("personalscraper.cli.get_settings")
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.verify.run.run_verify")
def test_verify_check_known_name_forwards_only(
    mock_run,
    mock_lock,
    mock_release,
    mock_settings,
    test_config,
) -> None:
    """Verify --check nfo_present forwards only=frozenset to run_verify."""
    from personalscraper.models import StepReport

    mock_run.return_value = (StepReport(name="verify"), [])
    from tests.fixtures.settings_stub import make_typed_settings_stub

    mock_settings.return_value = make_typed_settings_stub()

    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        result = run_cli(["verify", "--check", "nfo_present"])

    assert result.exit_code == 0, result.output
    _, kwargs = mock_run.call_args
    assert kwargs.get("only") == frozenset({"nfo_present"})
