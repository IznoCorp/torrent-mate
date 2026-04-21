"""Behavioral equivalence test: V14 GenreMapper ↔ V15 classifier.

For each case in the golden table (tests/equivalence/golden/classifier_cases.json):
1. Assert that V14 GenreMapper produces the expected label (regression guard).
2. Assert that V15 classifier.classify() produces the equivalent category_id
   (via V14_LABEL_TO_ID mapping).

This test is SKIPPED until Phase 2 implements personalscraper.conf.classifier.
Once the classifier is implemented, remove the skip decorator and ensure all
57 golden cases pass.

Golden table: tests/equivalence/golden/classifier_cases.json
  - 57 cases covering 8 of 11 V14 categories (spectacles/theatres/livres audios
    are .category-file-only in V14 and will be handled via category_rules in V15).
"""

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "classifier_cases.json"


def _load_golden() -> list[dict]:
    """Load golden table cases from JSON file.

    Returns:
        List of test case dicts from classifier_cases.json.
    """
    with _GOLDEN_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# V14 regression guard (active — ensures golden table stays valid)
# ---------------------------------------------------------------------------


class TestV14GoldenRegression:
    """Verify that V14 GenreMapper still produces the expected labels.

    This test class is ACTIVE: it protects against unintended V14 regressions.
    If genre_mapper.py is modified, this will catch any behavioral changes.
    """

    @pytest.mark.parametrize(
        "case",
        _load_golden(),
        ids=[c["scenario"] for c in _load_golden()],
    )
    def test_v14_produces_expected_label(self, case: dict) -> None:
        """V14 GenreMapper must produce the expected label for each golden case.

        Args:
            case: A golden table entry with media_type, genres, genre_ids,
                origin_country, source, and expected_v14_label.
        """
        from personalscraper.genre_mapper import GenreMapper

        gm = GenreMapper()
        genres = case["genres"]
        genre_ids = case["genre_ids"] if case["genre_ids"] else None
        origin_country = case.get("origin_country")
        source = case.get("source", "tmdb")
        expected = case["expected_v14_label"]

        if case["media_type"] == "movie":
            result = gm.categorize_movie(genres, genre_ids)
        else:
            result = gm.categorize_tvshow(
                genres,
                genre_ids,
                origin_country=origin_country,
                source=source,
            )

        assert result == expected, (
            f"V14 regression in scenario '{case['scenario']}': expected '{expected}', got '{result}'"
        )


# ---------------------------------------------------------------------------
# V15 equivalence (skipped — Phase 2 will implement classifier)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Phase 2 will implement classifier")
class TestV15ClassifierEquivalence:
    """Verify V15 classifier.classify() is behaviorally equivalent to V14 GenreMapper.

    Activate by removing the @pytest.mark.skip decorator once Phase 2 lands.
    """

    @pytest.mark.parametrize(
        "case",
        _load_golden(),
        ids=[c["scenario"] for c in _load_golden()],
    )
    def test_v15_equivalent_to_v14(self, test_config: object, case: dict) -> None:
        """V15 classifier must produce category_id equivalent to V14 label.

        Args:
            test_config: Shared Config fixture (injected by conftest.py).
            case: A golden table entry.
        """
        from personalscraper.conf.classifier import classify  # type: ignore[import]

        from personalscraper.conf.migration import V14_LABEL_TO_ID

        expected_v14_label = case["expected_v14_label"]
        expected_v15_id = V14_LABEL_TO_ID.get(expected_v14_label)
        if expected_v15_id is None:
            pytest.skip(f"No V15 mapping for V14 label '{expected_v14_label}'")

        genre_ids = case["genre_ids"] if case["genre_ids"] else None
        origin_country_list = [case["origin_country"]] if case.get("origin_country") else None
        source = case.get("source", "tmdb")
        media_type_v15 = "movie" if case["media_type"] == "movie" else "tv"

        # Select the correct genre ID parameters based on source
        tmdb_genre_ids = genre_ids if source == "tmdb" else None
        tvdb_genre_ids = genre_ids if source == "tvdb" else None

        result_id, reason = classify(
            test_config,  # type: ignore[arg-type]
            media_type=media_type_v15,
            tmdb_genre_ids=tmdb_genre_ids,
            tvdb_genre_ids=tvdb_genre_ids,
            origin_country=origin_country_list,
        )

        assert result_id == expected_v15_id, (
            f"V15 equivalence failure in scenario '{case['scenario']}': "
            f"expected '{expected_v15_id}' (from V14 '{expected_v14_label}'), "
            f"got '{result_id}' (reason: {reason})"
        )
