"""``seed`` speaks through the translation layer: one representative line, in both languages."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.cli_state import AppCtx
from personalscraper.i18n import Language, t, use_language


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_no_client_refusal_comes_from_the_catalogue(language: Language) -> None:
    """The « no torrent client » refusal is the catalogue's text, each language shows its own text."""
    import personalscraper.cli as _cli  # noqa: F401
    from personalscraper.cli_app import app

    app_context = MagicMock()
    app_context.torrent_client = None
    with (
        use_language(language),
        patch("personalscraper.commands.seed.per_step_boundary") as boundary,
        patch("personalscraper.commands.seed.cli_helpers.get_settings", return_value=MagicMock()),
    ):
        boundary.return_value.__enter__ = MagicMock(return_value=app_context)
        boundary.return_value.__exit__ = MagicMock(return_value=False)
        result = CliRunner().invoke(app, ["seed", "mark", "abc"], obj=AppCtx(config=MagicMock(), config_override=None))

    assert result.exit_code == 1
    expected = t("cli_acquisition.seed.no_client", language=language)
    assert expected in result.output
    if language is Language.EN:
        assert expected == "No torrent client configured. Check config/torrent.json5."
    else:
        # The French side is its own text (not the English one) and keeps the values the command passes.
        assert expected != "No torrent client configured. Check config/torrent.json5."
        assert "config/torrent.json5" in expected
