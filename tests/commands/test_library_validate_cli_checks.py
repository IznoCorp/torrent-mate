"""CLI tests for ``library-validate --check`` and ``--list-checks`` flags.

Phase 6.2 — library-validate uses CheckStage.DISPATCH. Tests are hermetic:
no real disk/network access.
"""

from __future__ import annotations

from unittest.mock import patch

from tests.commands._e2e_helpers import (
    assert_no_python_traceback,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


# ── --list-checks ──


def test_library_validate_list_checks_exits_zero(test_config) -> None:
    """library-validate --list-checks exits 0 and prints >=1 DISPATCH check."""
    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        result = run_cli(["library-validate", "--list-checks"])

    assert result.exit_code == 0, result.output
    # DISPATCH checks — at least nfo_present should be listed
    assert "nfo_present" in result.output
    assert_no_python_traceback(result)


# ── --check bogus_name ──


@patch("personalscraper.io_utils.write_json")
@patch("personalscraper.verify.library_checks.validate_library")
def test_library_validate_check_bogus_name_exits_nonzero(
    mock_validate,
    mock_write,
    test_config,
) -> None:
    """library-validate --check bogus_name exits != 0 with a hint."""
    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        result = run_cli(["library-validate", "--check", "bogus_name"])

    assert result.exit_code != 0, result.output
    assert "bogus_name" in result.output
    assert_no_python_traceback(result)


# ── --check valid name (happy path) ──


@patch("personalscraper.io_utils.write_json")
@patch("personalscraper.verify.library_checks.validate_library")
def test_library_validate_check_known_name_forwards_only(
    mock_validate,
    mock_write,
    test_config,
) -> None:
    """library-validate --check nfo_present forwards only=frozenset to validate_library."""
    from personalscraper.verify.library_checks import LibraryValidationResult

    mock_validate.return_value = LibraryValidationResult(
        validated_at="2026-01-01T00:00:00",
        disk_filter=None,
        category_filter=None,
        total_items=0,
        valid_count=0,
        fixed_count=0,
        issues_count=0,
        items=[],
    )

    with patch(_PATCH_LOAD_CONFIG, return_value=test_config):
        result = run_cli(["library-validate", "--check", "nfo_present"])

    assert result.exit_code == 0, result.output
    _, kwargs = mock_validate.call_args
    assert kwargs.get("only") == frozenset({"nfo_present"})


# ── --from-index --check <non-indexable> advisory note ──


def test_library_validate_from_index_non_indexable_check_warns(tmp_path, test_config) -> None:
    """--from-index --check dir_naming prints an advisory Note and exits 0.

    ``dir_naming`` is a DISPATCH check but not an IndexableCheck, so it produces
    nothing in DB-mode. The command must warn (not raise) and still complete.
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    # Ensure data_dir exists so write_json can write the output file.
    (tmp_path / ".data").mkdir(exist_ok=True)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-validate", "--from-index", "--check", "dir_naming"])

    assert result.exit_code == 0, result.output
    assert "Note:" in result.output
    assert "dir_naming" in result.output
    assert "--from-index" in result.output
    assert_no_python_traceback(result)
