"""Shared fixtures for personalscraper.commands.* CLI tests.

Autouse-patches the eager config load in the Typer callback so individual
test files do not have to set up the config fixture themselves.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"


@pytest.fixture(autouse=True)
def _mock_cli_config_load(request, test_config):
    """Patch the eager config load in the CLI callback for command tests.

    Mirrors the equivalent fixture in tests/conftest.py (which only runs for
    ``test_cli.py``/``test_logger_cli.py``) so command-module tests can drive
    the Typer CLI without needing a real config.json5 on disk.
    """
    # Skip when the test file does not exercise the CLI callback (e.g.
    # test_init_config.py calls init_config() directly).
    if request.fspath.basename == "test_init_config.py":
        yield
        return

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=test_config),
    ):
        yield
