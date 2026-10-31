"""The report's code sets are tied to the producers of the codes they word."""

from __future__ import annotations

from personalscraper.indexer.scanner._modes import _item_stage_types as stage_types
from personalscraper.insights import reporter
from personalscraper.verify.checks import registry


def _scanner_issue_codes() -> set[str]:
    """The ``ISSUE_*`` codes the library scanner emits."""
    return {value for name, value in vars(stage_types).items() if name.startswith("ISSUE_") and isinstance(value, str)}


def _registered_check_names() -> set[str]:
    """Every check name registered in the verify registry, whatever its stage."""
    return {spec.name for spec in registry.list_specs()}


def test_scan_issue_is_the_scanner_issue_set() -> None:
    """``ScanIssue`` words exactly the six codes the scanner emits: a new or renamed code leaves one side behind."""
    assert {member.value for member in reporter.ScanIssue} == _scanner_issue_codes()
    assert len(_scanner_issue_codes()) == 6


def test_every_validation_finding_is_a_registered_check() -> None:
    """Each ``ValidationFinding`` member is a check name the verify registry knows."""
    unknown = sorted(
        member.value for member in reporter.ValidationFinding if member.value not in _registered_check_names()
    )
    assert not unknown, f"validation findings no registered check produces: {unknown}"
