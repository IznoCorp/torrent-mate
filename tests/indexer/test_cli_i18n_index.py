"""The indexer command functions word their messages through the translation layer, in French and in English."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from personalscraper.conf.loader import ConfigNotFoundError
from personalscraper.core.event_bus import EventBus
from personalscraper.i18n import Language, t, use_language
from personalscraper.indexer.cli import (
    config_migrate_category_command,
    library_index_command,
    library_repair_command,
    library_status_command,
)
from personalscraper.indexer.db import apply_migrations

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"
_ERROR = "no config here"


def _run_status(bus: EventBus) -> Any:
    """Calls ``library_status_command`` with an empty config path."""
    return library_status_command(None, event_bus=bus)


def _run_migrate(bus: EventBus) -> Any:
    """Calls ``config_migrate_category_command`` with two category ids."""
    return config_migrate_category_command(from_category="a", to_category="b", event_bus=bus)


def _run_repair(bus: EventBus) -> Any:
    """Calls ``library_repair_command`` with its defaults."""
    return library_repair_command(event_bus=bus)


def _run_index(bus: EventBus) -> Any:
    """Calls ``library_index_command`` with its defaults."""
    return library_index_command(event_bus=bus)


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
@pytest.mark.parametrize(
    ("stem", "run"),
    [
        ("indexer_query", _run_status),
        ("indexer_diagnose", _run_migrate),
        ("indexer_repair", _run_repair),
        ("indexer_scan", _run_index),
    ],
)
def test_config_error_line_comes_from_the_catalogue(
    stem: str, run: Callable[[EventBus], Any], language: Language, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing config prints the catalogue's line for the module, under each language, exit code 1."""
    with (
        use_language(language),
        patch("personalscraper.conf.loader.load_config", side_effect=ConfigNotFoundError(_ERROR)),
    ):
        rc = run(EventBus())
    assert rc == 1
    # A logging handler left by an earlier test may add noise to stderr: search the line, do not compare whole.
    assert t(f"cli_library.{stem}.config_error", language=language, error=_ERROR) + "\n" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("stem", "run"),
    [
        ("indexer_query", _run_status),
        ("indexer_diagnose", _run_migrate),
        ("indexer_repair", _run_repair),
        ("indexer_scan", _run_index),
    ],
)
def test_config_error_line_differs_between_the_languages(
    stem: str, run: Callable[[EventBus], Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """The same failing call prints a French line under FR and an English one under EN."""
    printed = {}
    for language in (Language.FR, Language.EN):
        with (
            use_language(language),
            patch("personalscraper.conf.loader.load_config", side_effect=ConfigNotFoundError(_ERROR)),
        ):
            run(EventBus())
        printed[language] = capsys.readouterr().err
    fr = t(f"cli_library.{stem}.config_error", language=Language.FR, error=_ERROR)
    en = t(f"cli_library.{stem}.config_error", language=Language.EN, error=_ERROR)
    assert fr in printed[Language.FR] and en in printed[Language.EN]
    assert fr != en


def _status_json(tmp_path: Path, language: Language, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    """Runs ``library_status_command --format json`` on a DB holding one never-seen disk, under *language*.

    Args:
        tmp_path: Directory holding the (empty) database file the command's drift guard looks at.
        language: Language pinned around the call.
        capsys: Capture fixture; its stdout is parsed.

    Returns:
        The decoded JSON payload.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    apply_migrations(conn, MIGRATIONS_DIR)
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES ('u1', 'DiskA', '/x', NULL, 1, 0)"
    )
    db_file = tmp_path / "library.db"
    db_file.touch()
    cfg = SimpleNamespace(indexer=SimpleNamespace(db_path=db_file), all_category_ids=frozenset())

    @contextmanager
    def _open(*_args: Any, **_kwargs: Any) -> Iterator[sqlite3.Connection]:
        yield conn

    with (
        use_language(language),
        patch("personalscraper.conf.loader.load_config", return_value=cfg),
        patch("personalscraper.conf.loader.resolve_config_path", return_value=tmp_path),
        patch("personalscraper.indexer.commands._ceremony.open_indexer_db", _open),
    ):
        library_status_command(None, event_bus=EventBus(), output_format="json")
    out = capsys.readouterr().out
    return json.loads(out[out.index("{") :])


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_status_json_payload_is_not_translated(
    language: Language, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ``--format json`` payload carries the machine value ``never`` whatever the language."""
    payload = _status_json(tmp_path, language, capsys)
    assert payload["disks"][0]["last_seen"] == "never"
