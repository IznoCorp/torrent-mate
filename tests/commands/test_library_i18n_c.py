"""The scan, query, catalogue and phantom-row library commands speak through ``cli_library``.

What the tests hold is that the line the command prints IS the catalogue's text for its key, in each
language, and that the two languages differ.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.i18n import Language, t, use_language

runner = CliRunner()
_LANGUAGES = [Language.FR, Language.EN]


@pytest.mark.parametrize("language", _LANGUAGES)
def test_scan_db_path_line_comes_from_the_catalogue(test_config, language: Language) -> None:
    """``library-backfill-ids`` with no ``indexer.db_path`` prints the ``scan`` catalogue line."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with use_language(language), patch("personalscraper.conf.loader.load_config", return_value=cfg):
        result = runner.invoke(app, ["library-backfill-ids"])
        expected = t("cli_library.scan.db_path_not_configured", language=language)
    assert result.exit_code == 1
    assert expected in result.output


@pytest.mark.parametrize("language", _LANGUAGES)
def test_query_empty_search_line_comes_from_the_catalogue(
    capsys: pytest.CaptureFixture[str], language: Language
) -> None:
    """An empty search table prints the ``query`` catalogue line."""
    from personalscraper.commands.library.query import _print_search_table

    with use_language(language):
        _print_search_table([])
        expected = t("cli_library.query.no_results", language=language)
    assert capsys.readouterr().out.strip() == expected


@pytest.mark.parametrize("language", _LANGUAGES)
def test_catalogue_unconfigured_line_comes_from_the_catalogue(test_config, language: Language) -> None:
    """``library-catalogue-refresh`` with no db paths prints the ``catalogue`` catalogue line."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with use_language(language), patch("personalscraper.conf.loader.load_config", return_value=cfg):
        result = runner.invoke(app, ["library-catalogue-refresh"])
        expected = t("cli_library.catalogue.db_paths_not_configured", language=language)
    assert result.exit_code == 1
    assert expected in result.output


@pytest.mark.parametrize("language", _LANGUAGES)
def test_remove_phantom_rows_missing_database_line_comes_from_the_catalogue(tmp_path: Path, language: Language) -> None:
    """``library-remove-phantom-rows --db`` on a missing file prints the catalogue line with the path."""
    missing = tmp_path / "absent.db"
    with use_language(language):
        result = runner.invoke(app, ["library-remove-phantom-rows", "--db", str(missing)])
        expected = t("cli_library.remove_phantom_rows.database_not_found", language=language, path=missing)
    assert result.exit_code == 1
    assert expected in result.output


def test_query_empty_search_line_differs_between_the_languages(capsys: pytest.CaptureFixture[str]) -> None:
    """An empty search table prints French text under FR and English text under EN."""
    from personalscraper.commands.library.query import _print_search_table

    printed = {}
    for language in _LANGUAGES:
        with use_language(language):
            _print_search_table([])
        printed[language] = capsys.readouterr().out.strip()
    assert printed[Language.FR] == t("cli_library.query.no_results", language=Language.FR)
    assert printed[Language.EN] == t("cli_library.query.no_results", language=Language.EN)
    assert printed[Language.FR] != printed[Language.EN]


def test_scan_db_path_line_differs_between_the_languages(test_config) -> None:
    """``library-backfill-ids`` without ``indexer.db_path`` refuses in each language's own words."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    printed = {}
    for language in _LANGUAGES:
        with use_language(language), patch("personalscraper.conf.loader.load_config", return_value=cfg):
            printed[language] = runner.invoke(app, ["library-backfill-ids"]).output
    assert printed[Language.FR] != printed[Language.EN]
