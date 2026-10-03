"""Tests for ``personalscraper library catalogue-refresh``."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.acquire.catalogue import CatalogueRefreshReport
from personalscraper.cli import app

runner = CliRunner()
_MODULE = "personalscraper.commands.library_catalogue"


def test_help_lists_max() -> None:
    """The command is mounted under ``library`` and documents ``--max``."""
    result = runner.invoke(app, ["library", "catalogue-refresh", "--help"])
    assert result.exit_code == 0, result.output
    assert "--max" in result.output


def test_run_passes_max_and_prints_the_report(tmp_path: Path, test_config) -> None:
    """``--max`` reaches the refresh and the report is printed as JSON."""
    index = tmp_path / "library.db"
    sqlite3.connect(str(index)).close()
    test_config.acquire.db_path = tmp_path / "acquire.db"
    test_config.indexer.db_path = index

    @contextmanager
    def fake_boundary(*_a, **_k):
        yield SimpleNamespace(provider_registry=MagicMock())

    refresh = MagicMock(return_value=CatalogueRefreshReport(refreshed=2, failed=1, skipped=0, remaining=4))
    with (
        patch(f"{_MODULE}.per_step_boundary", fake_boundary),
        patch(f"{_MODULE}.refresh_catalogue", refresh),
        patch("personalscraper.cli_helpers.get_settings"),
        patch("personalscraper.cli.load_config", return_value=test_config, create=True),
    ):
        result = runner.invoke(app, ["library", "catalogue-refresh", "--max", "7"])

    assert result.exit_code == 0, result.output
    assert refresh.call_args.kwargs["max_shows"] == 7
    line = next(ln for ln in result.output.splitlines() if ln.startswith("{"))
    assert json.loads(line) == {"refreshed": 2, "failed": 1, "skipped": 0, "remaining": 4}
