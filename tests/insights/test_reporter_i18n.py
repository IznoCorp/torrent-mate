"""The library report words its lines through the translation layer, unchanged."""

from __future__ import annotations

import pytest

from personalscraper.i18n import Language, t, t_code, use_language
from personalscraper.insights.reporter import LibraryReport, ScanIssue, ValidationFinding, format_report_text


def _full_report() -> LibraryReport:
    """Return a report with every section populated.

    Returns:
        A report whose text holds each section header and each code explanation.
    """
    return LibraryReport(
        generated_at="2026-01-01T00:00:00+00:00",
        total_items=200,
        total_size_gb=10.0,
        items_per_disk={"d1": 200},
        size_per_disk_gb={"d1": 10.0},
        scan_issues={"actors_dir_present": 3, "unknown_issue_code": 1},
        validation_valid=1,
        validation_issues=1,
        validation_errors={"nfo_present": 1, "zzz_unknown": 1},
        validation_warnings={"episode_nfo": 1},
        analysis_item_count=10,
        analysis_file_count=20,
        recommendation_count=1,
        top_largest=[("Big (2020)", 9.0)],
        rescrape_fixed=1,
        rescrape_skipped=1,
    )


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
@pytest.mark.parametrize(
    ("key", "params"),
    [
        ("cli_library.reporter.title", {}),
        ("cli_library.reporter.scan_heading", {}),
        ("cli_library.reporter.validation_heading", {}),
        ("cli_library.reporter.analysis_heading", {}),
        ("cli_library.reporter.recommendations_heading", {}),
        ("cli_library.reporter.top_heading", {}),
        ("cli_library.reporter.rescrape_heading", {}),
        ("cli_library.reporter.actions_heading", {}),
    ],
)
def test_section_headers_come_from_the_catalogue(key, params, language) -> None:
    """Each section header of the report is the catalogue's text, in either language (equal until translated).

    Args:
        key: The header's catalogue key.
        params: Its placeholder values.
        language: The language the report is rendered in.
    """
    with use_language(language):
        text = format_report_text(_full_report())
        assert t(key, **params) in text


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_scan_issue_explanation_comes_from_the_code_set(language) -> None:
    """A scan issue's explanation is the catalogue's text for its code.

    Args:
        language: The language the report is rendered in.
    """
    with use_language(language):
        text = format_report_text(_full_report())
        assert t_code("cli_library.issue", ScanIssue.ACTORS_DIR_PRESENT) in text


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_validation_explanation_comes_from_the_code_set(language) -> None:
    """A validation finding's explanation is the catalogue's text for its code.

    Args:
        language: The language the report is rendered in.
    """
    with use_language(language):
        text = format_report_text(_full_report())
        assert t_code("cli_library.validation", ValidationFinding.NFO_PRESENT) in text


def test_an_unknown_code_renders_unchanged() -> None:
    """A code outside the closed sets is shown as itself, as before."""
    text = format_report_text(_full_report())
    assert "      → unknown_issue_code" in text
    assert "        → zzz_unknown" in text
