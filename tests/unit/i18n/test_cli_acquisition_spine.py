"""The spine actions speak through the translation layer: one representative line, in both languages."""

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
def test_requeue_unknown_grab_line_comes_from_the_catalogue(
    test_config: Any, tmp_path: Path, language: Language
) -> None:
    """The « no provenance row » line is the catalogue's text, each language shows its own text."""
    acquire = test_config.acquire.model_copy(update={"db_path": tmp_path / "acquire.db"})
    cfg = test_config.model_copy(update={"acquire": acquire})

    with (
        use_language(language),
        patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/fake/config.json5")),
        patch("personalscraper.conf.loader.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["acquisition-requeue", "--hash", "nohash"])

    assert result.exit_code == 0, result.output
    expected = t("cli_acquisition.spine.requeue_no_provenance", info_hash="nohash", language=language)
    assert expected in result.output
    if language is Language.EN:
        assert expected == "No provenance row for grab nohash."
    else:
        # The French side is its own text (not the English one) and keeps the values the command passes.
        assert expected != "No provenance row for grab nohash."
        assert "nohash" in expected
