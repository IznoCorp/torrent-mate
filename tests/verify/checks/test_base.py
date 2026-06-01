"""Unit tests for verify/checks/base.py — types, protocols, context."""

from personalscraper.verify.checks.base import (
    CheckResult,
    CheckSpec,
    CheckStage,
    FixAction,
    Severity,
)


def test_check_stage_values():
    """CheckStage enum has staging and dispatch values."""
    assert CheckStage.STAGING.value == "staging"
    assert CheckStage.DISPATCH.value == "dispatch"


def test_severity_values():
    """Severity enum has error and warning values."""
    assert Severity.ERROR.value == "error"
    assert Severity.WARNING.value == "warning"


def test_check_result_defaults():
    """CheckResult fixable defaults to False."""
    r = CheckResult(name="x", passed=True, severity=Severity.ERROR, message="")
    assert r.fixable is False


def test_fix_action_fields():
    """FixAction stores old_path, new_path, and description."""
    from pathlib import Path

    a = FixAction(description="renamed", old_path=Path("/a"), new_path=Path("/b"))
    assert a.new_path == Path("/b")


def test_check_spec_fields():
    """CheckSpec stores static metadata including indexable flag."""
    spec = CheckSpec(
        stage=CheckStage.DISPATCH,
        name="nfo_present",
        group="nfo",
        media_types=frozenset({"movie", "tvshow"}),
        default_severity=Severity.ERROR,
        fixable=False,
        indexable=True,
        description="NFO file must exist",
    )
    assert spec.indexable is True
