"""Shared fixtures for personalscraper.commands.* CLI tests.

Autouse-patches the eager config load in the Typer callback so individual
test files do not have to set up the config fixture themselves.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from personalscraper.conf import loader

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"

# Capture pristine loader callables BEFORE any patching, so tests that need
# to temporarily restore the real loader can do so without importlib.reload.
# reload() is forbidden because it rebinds every class in the loader module
# (ConfigNotFoundError, ConfigValidationError, ...), poisoning class-object
# identity for every other test on the same xdist worker that imported those
# classes before the reload.
_REAL_LOAD_CONFIG = loader.load_config
_REAL_RESOLVE_CONFIG_PATH = loader.resolve_config_path


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


@pytest.fixture
def real_loader():
    """Pristine loader callables captured at module import time.

    Use this fixture instead of ``importlib.reload()`` to temporarily restore
    the real loader in tests that must bypass the autouse patch.  ``reload()``
    is forbidden because it splits exception-class identity across the xdist
    worker (old class imported before reload ≠ new class after reload), causing
    ``pytest.raises(OldClass)`` failures when the reloaded function raises
    ``NewClass``.

    Returns:
        SimpleNamespace with ``load_config`` and ``resolve_config_path`` attrs.
    """
    return SimpleNamespace(
        load_config=_REAL_LOAD_CONFIG,
        resolve_config_path=_REAL_RESOLVE_CONFIG_PATH,
    )
