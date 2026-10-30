"""``follow`` speaks through the translation layer: one representative line, in both languages."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from personalscraper.cli import app
from personalscraper.i18n import Language, t, use_language
from tests.conftest import make_cli_runner

runner = make_cli_runner()


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_add_without_an_id_line_comes_from_the_catalogue(test_config: Any, language: Language) -> None:
    """The « at least one id » refusal is the catalogue's text, each language shows its own text."""
    with (
        use_language(language),
        patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/fake/config.json5")),
        patch("personalscraper.conf.loader.load_config", return_value=test_config),
    ):
        result = runner.invoke(app, ["follow", "add"])

    assert result.exit_code == 2
    expected = t("cli_acquisition.follow.add.need_id", language=language)
    assert expected in result.output + result.stderr
    if language is Language.EN:
        assert expected == "Error: at least one of --tvdb, --tmdb, or --imdb is required."
    else:
        # The French side is its own text (not the English one) and keeps the values the command passes.
        assert expected != "Error: at least one of --tvdb, --tmdb, or --imdb is required."
        assert "--imdb" in expected
