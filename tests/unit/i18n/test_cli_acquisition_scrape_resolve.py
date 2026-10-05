"""``scrape-resolve`` speaks through the translation layer: one representative line, in both languages."""

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
def test_invalid_provider_line_comes_from_the_catalogue(test_config: Any, tmp_path: Path, language: Language) -> None:
    """The « invalid provider » refusal is the catalogue's text, each language shows its own text."""
    staging = tmp_path / "staging" / "item"
    staging.mkdir(parents=True)

    with (
        use_language(language),
        patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/fake/config.json5")),
        patch("personalscraper.conf.loader.load_config", return_value=test_config),
    ):
        result = runner.invoke(app, ["scrape-resolve", str(staging), "--provider", "imdb", "--id", "1"])

    assert result.exit_code == 2
    expected = t(
        "cli_acquisition.scrape_resolve.invalid_provider", provider="imdb", valid="tmdb, tvdb", language=language
    )
    assert expected in result.output
    if language is Language.EN:
        assert expected == "Invalid provider 'imdb'. Must be one of: tmdb, tvdb."
    else:
        # The French side is its own text (not the English one) and keeps the values the command passes.
        assert expected != "Invalid provider 'imdb'. Must be one of: tmdb, tvdb."
        assert "imdb" in expected
