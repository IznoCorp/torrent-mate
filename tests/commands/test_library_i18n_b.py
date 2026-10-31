"""The library analysis and maintenance commands word their output through the translation layer.

Each representative line is the catalogue's, looked up per language, not an inline literal, and the two
languages read differently.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.i18n import Language, t, use_language

runner = CliRunner()


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_analyze_invalid_sort_line_comes_from_the_catalogue(language: Language) -> None:
    """``library-recommend --sort bogus`` prints ``analyze.invalid_sort`` in the current language."""
    with use_language(language):
        result = runner.invoke(app, ["library-recommend", "--sort", "bogus"])
        expected = t("cli_library.analyze.invalid_sort", value="bogus", valid="codec, priority, size")
    assert result.exit_code == 1
    assert expected in result.output


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_maintenance_clean_exclusive_line_comes_from_the_catalogue(language: Language) -> None:
    """``library-clean --dry-run --apply`` prints ``maintenance.clean_exclusive`` in the current language."""
    with use_language(language):
        result = runner.invoke(app, ["library-clean", "--dry-run", "--apply"])
        expected = t("cli_library.maintenance.clean_exclusive")
    assert result.exit_code == 1
    assert expected in result.output


def test_analyze_and_maintenance_lines_differ_between_the_languages() -> None:
    """The same invocations print French text under FR and English text under EN."""
    invocations = [
        (["library-recommend", "--sort", "bogus"], "cli_library.analyze.invalid_sort"),
        (["library-clean", "--dry-run", "--apply"], "cli_library.maintenance.clean_exclusive"),
    ]
    for argv, key in invocations:
        printed = {}
        for language in (Language.FR, Language.EN):
            with use_language(language):
                printed[language] = runner.invoke(app, argv).output
        assert printed[Language.FR] != printed[Language.EN], key
        for language in (Language.FR, Language.EN):
            line = t(key, language=language, value="bogus", valid="codec, priority, size")
            assert line in printed[language], (key, language)
