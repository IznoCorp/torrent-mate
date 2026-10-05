"""Every acquisition CLI key reads in both languages, and the two sides differ where the words do."""

from __future__ import annotations

import pytest

from personalscraper.i18n import Language, t

# Keys that were French-only before T-acq, with the English text they now show.
_FRENCH_ORIGIN_EN = {
    "cli_acquisition.search.reconcile_label": "Reconciliation:",
    "cli_acquisition.grab.reswitch_label": "Switch:",
    "cli_acquisition.follow.detect.cell_film_acquired": "acquired — removed from follows",
    "cli_acquisition.follow.backfill.field_title": "title",
    "cli_acquisition.confidence.none_of_these": "  [0] None of these results",
    "cli_acquisition.confidence.choice_prompt": "Choice: ",
}


@pytest.mark.parametrize(("key", "english"), sorted(_FRENCH_ORIGIN_EN.items()))
def test_french_origin_keys_have_an_english_side(key: str, english: str) -> None:
    """A key written in French first now reads in English, and still differs from its French side."""
    assert t(key, language=Language.EN) == english
    assert t(key, language=Language.FR) != english


def test_the_french_backfill_labels_are_french_words() -> None:
    """The backfill field labels that used English words in the French side are French now."""
    fr = {
        f: t(f"cli_acquisition.follow.backfill.field_{f}", language=Language.FR) for f in ("poster", "overview", "year")
    }
    assert fr == {"poster": "affiche", "overview": "synopsis", "year": "année"}
