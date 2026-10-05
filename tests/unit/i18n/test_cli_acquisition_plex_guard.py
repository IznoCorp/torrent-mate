"""``plex-guard`` speaks through the translation layer: one representative line, in both languages."""

from __future__ import annotations

import inspect
import io
from types import SimpleNamespace

import pytest
from rich.console import Console

from personalscraper.cli_state import state
from personalscraper.commands.plex_guard import plex_guard
from personalscraper.i18n import Language, t, use_language


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_no_token_line_comes_from_the_catalogue(monkeypatch: pytest.MonkeyPatch, language: Language) -> None:
    """The « no Plex token » refusal is the catalogue's text, the same in both languages until translated."""
    buffer = io.StringIO()
    monkeypatch.setitem(state, "console", Console(file=buffer, width=200, color_system=None))
    bundle = SimpleNamespace(indexer_conn=object(), settings=SimpleNamespace(plex_token=""))
    command = inspect.unwrap(plex_guard)

    with use_language(language), pytest.raises(Exception) as stopped:
        command(None, repair=False, item_id=None, bundle=bundle)

    assert getattr(stopped.value, "exit_code", None) == 1
    expected = t("cli_acquisition.plex_guard.no_token", language=language)
    assert expected in buffer.getvalue()
    assert "No Plex token configured" in expected
