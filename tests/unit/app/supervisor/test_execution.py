"""Unit tests for :func:`personalscraper.app.supervisor.execution.rescrape_item`.

The run row is the REAL ``cli_run_row`` over a migrated indexer DB in ``tmp_path``: what is
asserted is the ``pipeline_run`` row a failed rescrape leaves behind, not a call on a fake.
"""

from __future__ import annotations

import io
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from personalscraper.app.supervisor.execution import rescrape_item
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.i18n import t
from personalscraper.indexer import migrations
from personalscraper.indexer.db import IndexerInvalidPathError, apply_migrations
from personalscraper.maintenance.rescraper import LibraryRescrapeResult


@contextmanager
def _step_boundary(config: object, settings: object):
    """Stand-in for ``per_step_boundary``: an application context holding only what the rescrape reads."""
    yield SimpleNamespace(event_bus=MagicMock(), provider_registry=MagicMock())


def _run_rows(db_path: Path) -> list[tuple[str, str, str | None]]:
    """The ``(command, outcome, error)`` of every ``pipeline_run`` row."""
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT command, outcome, error FROM pipeline_run").fetchall()


def test_an_item_that_is_not_found_leaves_its_run_row_as_an_error(test_config, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed repair is recorded ``error`` on a self-owned row (CLI / cron), not ``success``."""
    monkeypatch.delenv("PERSONALSCRAPER_RUN_UID", raising=False)
    db_path = test_config.indexer.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        apply_migrations(conn, Path(migrations.__file__).parent)

    code = rescrape_item(
        test_config,
        MagicMock(),
        999_999,
        console=Console(quiet=True),
        run_row=cli_run_row,
        step_boundary=_step_boundary,
    )

    assert code == 1
    assert _run_rows(db_path) == [("library-rescrape-item", "error", "1")]


def _migrated_index(test_config) -> Path:
    """Create the configured indexer DB, migrated, and return its path."""
    db_path = test_config.indexer.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        apply_migrations(conn, Path(migrations.__file__).parent)
    return db_path


def test_a_rescrape_records_its_counts_on_the_run_row(test_config, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fixed / skipped / errors / artwork counters reach the row's recorder."""
    _migrated_index(test_config)
    recorder = MagicMock()

    @contextmanager
    def run_row(config: object, command: str):
        yield recorder

    result = LibraryRescrapeResult(
        rescraped_at="2026",
        disk_filter=None,
        category_filter=None,
        only_filter=None,
        dry_run=False,
        fixed_count=2,
        skipped_count=1,
        error_count=3,
        candidate_count=6,
    )
    monkeypatch.setattr("personalscraper.maintenance.rescraper.rescrape_library", lambda *a, **kw: result)

    code = rescrape_item(
        test_config,
        MagicMock(),
        42,
        console=Console(quiet=True),
        run_row=run_row,
        step_boundary=_step_boundary,
    )

    assert code == 0
    recorder.record_counts.assert_called_once_with({"fixed": 2, "skipped": 1, "errors": 3, "artwork_recovered": 0})


def test_an_index_that_cannot_be_opened_returns_1_and_records_an_error(
    test_config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DB-open failure is a failed run (exit 1, row ``error``), never a success."""
    db_path = _migrated_index(test_config)
    monkeypatch.delenv("PERSONALSCRAPER_RUN_UID", raising=False)

    def refuse(*args: object, **kwargs: object) -> None:
        raise IndexerInvalidPathError(db_path, Path("/Volumes/unreachable"))

    # ``open_db`` is bound at module level in ``execution``: the patch targets that binding.
    monkeypatch.setattr("personalscraper.app.supervisor.execution.open_db", refuse)
    output = io.StringIO()

    code = rescrape_item(
        test_config,
        MagicMock(),
        42,
        console=Console(file=output, width=200, color_system=None),
        run_row=cli_run_row,
        step_boundary=_step_boundary,
    )

    assert code == 1
    assert _run_rows(db_path) == [("library-rescrape-item", "error", "1")]
    # An item that is merely not found leaves the same row: the open-failure label tells the two apart.
    assert t("cli_library.analyze.open_failed_label") in output.getvalue()


def test_an_index_newer_than_the_code_returns_1_untouched(test_config) -> None:
    """A store past the last migration takes the open-failure path (exit 1), not a traceback."""
    db_path = _migrated_index(test_config)
    newer = max(int(p.name.split("_")[0]) for p in Path(migrations.__file__).parent.glob("*.sql")) + 1
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"PRAGMA user_version = {newer}")
    conn.close()

    @contextmanager
    def run_row(config: object, command: str):
        yield MagicMock()

    code = rescrape_item(
        test_config,
        MagicMock(),
        42,
        console=Console(quiet=True),
        run_row=run_row,
        step_boundary=_step_boundary,
    )

    assert code == 1
    with sqlite3.connect(db_path) as check:
        assert check.execute("PRAGMA user_version").fetchone()[0] == newer
    check.close()
