"""The indexer command functions word their messages through the translation layer, unchanged."""

from __future__ import annotations

from collections.abc import Callable
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
    assert t(f"cli_library.{stem}.config_error", error=_ERROR) + "\n" in capsys.readouterr().err
