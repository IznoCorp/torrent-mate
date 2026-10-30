"""``cross-seed`` speaks through the translation layer: one representative line, in both languages."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.cli_state import AppCtx
from personalscraper.i18n import Language, t, use_language


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_neither_flag_refusal_comes_from_the_catalogue(language: Language) -> None:
    """The « use --sweep or --hash » refusal is the catalogue's text, each language shows its own text."""
    import personalscraper.cli as _cli  # noqa: F401
    from personalscraper.cli_app import app

    with (
        use_language(language),
        patch("personalscraper.commands.cross_seed.cli_helpers.get_settings", return_value=MagicMock()),
    ):
        result = CliRunner().invoke(app, ["cross-seed"], obj=AppCtx(config=MagicMock(), config_override=None))

    assert result.exit_code == 2
    expected = t("cli_acquisition.cross_seed.need_flag", language=language)
    assert expected in result.output
    if language is Language.EN:
        assert expected == "Use --sweep or --hash"
    else:
        # The French side is its own text (not the English one) and keeps the values the command passes.
        assert expected != "Use --sweep or --hash"
        assert "--sweep" in expected
