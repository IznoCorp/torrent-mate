"""The OpenAPI export builds its synthetic config in every environment.

``scripts/export-openapi.py`` builds a ``Config`` over a temporary data directory. The
isolation guard refuses an unmarked data directory outside prod, so an agent checkout
whose ``.env`` sets ``PERSONALSCRAPER_ENV=dev`` could not run ``make openapi``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from _repo_paths import ROOT

from personalscraper.conf.environment import ENV_VAR, Environment
from personalscraper.conf.isolation import read_marker

SCRIPT = ROOT / "scripts" / "export-openapi.py"


def _load_export():  # noqa: ANN202 - a script module has no importable name
    """Import ``scripts/export-openapi.py`` (its file name is not an identifier).

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location("export_openapi", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("environment", [Environment.PROD, Environment.DEV, Environment.STAGING])
def test_export_config_builds_in_every_environment(
    environment: Environment, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The minimal config validates whatever environment the process runs in."""
    monkeypatch.setenv(ENV_VAR, environment.value)
    config = _load_export()._build_minimal_config(tmp_path)
    expected = None if environment is Environment.PROD else environment
    assert read_marker(config.paths.data_dir) is expected
