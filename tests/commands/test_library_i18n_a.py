"""The library audit, doctor and de-duplication commands speak through the translation layer.

Nothing is translated yet, so a representative line is the same text in both languages; the point is
that it is read from the ``cli_library`` catalogue (a missing key raises under the strict test mode).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.i18n import Language, t, use_language

runner = CliRunner()


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_duplicates_by_id_reports_a_missing_database(language: Language, tmp_path: Path) -> None:
    """``library-duplicates-by-id`` words its missing-database refusal through the catalogue."""
    missing = tmp_path / "absent.db"
    with use_language(language):
        result = runner.invoke(app, ["library-duplicates-by-id", "--db", str(missing)])
        expected = t("cli_library.duplicates_by_id.db_not_found", path=str(missing))
    assert result.exit_code == 1
    assert expected in result.output


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_dedup_titles_reports_a_missing_database(language: Language, tmp_path: Path, test_config) -> None:
    """``library-dedup-titles`` words its missing-database refusal through the catalogue."""
    missing = tmp_path / "absent.db"
    with use_language(language), patch("personalscraper.conf.loader.load_config", return_value=test_config):
        result = runner.invoke(app, ["library-dedup-titles", "--db", str(missing)])
        expected = t("cli_library.dedup_titles.db_not_found", path=str(missing))
    assert result.exit_code == 1
    assert expected in result.output


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_doctor_reports_an_unconfigured_database(language: Language, test_config) -> None:
    """``library-doctor`` words its unconfigured-database refusal through the catalogue."""
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with use_language(language), patch("personalscraper.conf.loader.load_config", return_value=cfg):
        result = runner.invoke(app, ["library-doctor"])
        expected = t("cli_library.doctor.db_path_not_configured")
    assert result.exit_code == 1
    assert expected in result.output


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_audit_reconcile_refuses_conflicting_modes(language: Language) -> None:
    """``library-reconcile`` words its mutual-exclusion refusal through the catalogue."""
    with use_language(language):
        result = runner.invoke(app, ["library-reconcile", "--enqueue-repairs", "--read-only"])
        expected = t("cli_library.audit.reconcile_modes_exclusive")
    assert result.exit_code == 1
    assert expected in result.output


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_audit_ghost_audit_reports_clean_disks(language: Language) -> None:
    """``library-ghost-audit`` words its summary line through the catalogue."""
    with use_language(language):
        result = runner.invoke(app, ["library-ghost-audit", "--disk", "nonexistent_id"])
        expected = t("cli_library.audit.ghost_all_clean")
    assert result.exit_code == 0
    assert expected in result.output
