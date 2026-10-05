"""The fix-* and gc library commands word their messages through the translation layer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from personalscraper.i18n import Language, t, use_language
from tests.commands._e2e_helpers import run_cli

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"

_COMMANDS = [
    ("gc", "library-gc"),
    ("fix_nfo", "library-fix-nfo"),
    ("fix_orphan_files", "library-fix-orphan-files"),
    ("fix_season_counts", "library-fix-season-counts"),
    ("fix_canonical_provider", "library-fix-canonical-provider"),
]


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
@pytest.mark.parametrize(("module", "command"), _COMMANDS)
def test_unconfigured_db_path_message_comes_from_the_catalogue(test_config, module, command, language) -> None:
    """The « db_path is not configured » line is the catalogue's, in either language (equal until translated).

    Args:
        test_config: The shared test configuration.
        module: The command module's file stem, the key's second segment.
        command: The Typer command name.
        language: The language the line is rendered in.
    """
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
    with use_language(language), patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli([command])
        expected = t(f"cli_library.{module}.db_path_not_configured")
    assert result.exit_code == 1
    assert expected in result.output
