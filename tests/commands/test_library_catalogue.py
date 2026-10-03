"""Tests for ``personalscraper library-catalogue-refresh``."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.acquire.catalogue import CatalogueRefreshReport
from personalscraper.api.metadata.registry._errors import UnknownProviderError
from personalscraper.cli import app

runner = CliRunner()
_MODULE = "personalscraper.commands.library.catalogue"


def test_help_lists_max() -> None:
    """The command is a flat ``library-*`` command and documents ``--max``."""
    result = runner.invoke(app, ["library-catalogue-refresh", "--help"])
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
        result = runner.invoke(app, ["library-catalogue-refresh", "--max", "7"])

    assert result.exit_code == 0, result.output
    assert refresh.call_args.kwargs["max_shows"] == 7
    line = next(ln for ln in result.output.splitlines() if ln.startswith("{"))
    assert json.loads(line) == {"refreshed": 2, "failed": 1, "skipped": 0, "remaining": 4}


def test_an_unregistered_provider_skips_its_shows_instead_of_failing_the_run(tmp_path: Path, test_config) -> None:
    """A registry with no TVDB nor TMDB (unconfigured) completes the run, shows counted skipped."""
    index = tmp_path / "library.db"
    conn = sqlite3.connect(str(index))
    conn.execute(
        "CREATE TABLE media_item (id INTEGER PRIMARY KEY, kind TEXT, canonical_provider TEXT, external_ids_json TEXT)"
    )
    conn.execute(
        "INSERT INTO media_item (kind, canonical_provider, external_ids_json) VALUES ('show', 'tvdb', ?)",
        (json.dumps({"tvdb": {"series_id": "10", "episode_id": None}}),),
    )
    conn.commit()
    conn.close()
    test_config.acquire.db_path = tmp_path / "acquire.db"
    test_config.indexer.db_path = index

    registry = MagicMock()
    registry.get.side_effect = UnknownProviderError("tvdb")

    @contextmanager
    def fake_boundary(*_a, **_k):
        yield SimpleNamespace(provider_registry=registry)

    with (
        patch(f"{_MODULE}.per_step_boundary", fake_boundary),
        patch("personalscraper.cli_helpers.get_settings"),
        patch("personalscraper.cli.load_config", return_value=test_config, create=True),
    ):
        result = runner.invoke(app, ["library-catalogue-refresh"])

    assert result.exit_code == 0, result.output
    line = next(ln for ln in result.output.splitlines() if ln.startswith("{"))
    assert json.loads(line) == {"refreshed": 0, "failed": 0, "skipped": 1, "remaining": 0}
