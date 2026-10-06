"""Unit tests for :func:`personalscraper.app.supervisor.execution.rescrape_item`.

The run row is the REAL ``cli_run_row`` over a migrated indexer DB in ``tmp_path``: what is
asserted is the ``pipeline_run`` row a failed rescrape leaves behind, not a call on a fake.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from personalscraper.app.supervisor.execution import rescrape_item
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.indexer import migrations
from personalscraper.indexer.db import apply_migrations


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
