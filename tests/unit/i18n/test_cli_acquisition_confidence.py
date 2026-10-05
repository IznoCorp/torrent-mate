"""The interactive match prompt speaks through the translation layer: representative lines, in both languages."""

from __future__ import annotations

import pytest

from personalscraper.i18n import Language, t, use_language
from personalscraper.scraper._match_score import MatchResult
from personalscraper.scraper.confidence import prompt_user_choice


@pytest.mark.parametrize("language", [Language.FR, Language.EN])
def test_prompt_lines_come_from_the_catalogue(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], language: Language
) -> None:
    """The heading and the « none of these » line are the catalogue's text, each language shows its own text."""
    prompts: list[str] = []

    def _input(prompt: str = "") -> str:
        prompts.append(prompt)
        return "0"

    monkeypatch.setattr("builtins.input", _input)
    results = [MatchResult(api_id=1, api_title="Alpha", api_year=2001, confidence=0.5, source="tmdb")]

    with use_language(language):
        assert prompt_user_choice(results, "Local") is None

    out = capsys.readouterr().out
    heading = t("cli_acquisition.confidence.heading", title="Local", language=language)
    assert heading in out
    if language is Language.EN:
        assert heading == "Matching: Local"
    else:
        # The French side is its own text (not the English one) and keeps the values the command passes.
        assert heading != "Matching: Local"
        assert "Local" in heading
    none_line = t("cli_acquisition.confidence.none_of_these", language=language)
    assert none_line in out
    assert prompts == ["\n" + t("cli_acquisition.confidence.choice_prompt", language=language)]
