"""Generate classifier equivalence golden table from V14 GenreMapper.

Exercises GenreMapper.categorize_movie() and categorize_tvshow() across all 11
V14 category labels and multiple scenarios per category. The resulting JSON is
used by tests/equivalence/test_classifier_v14_vs_v15.py to assert behavioral
equivalence between V14 genre_mapper and V15 classifier.

Usage:
    python scripts/generate_classifier_golden.py

Output:
    tests/equivalence/golden/classifier_cases.json
"""

import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path so imports work from repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from personalscraper.genre_mapper import GenreMapper  # noqa: E402

_OUTPUT_PATH = _REPO_ROOT / "tests" / "equivalence" / "golden" / "classifier_cases.json"


def _case(
    media_type: str,
    genres: list[str],
    genre_ids: list[int] | None,
    expected_v14_label: str,
    origin_country: str | None = None,
    source: str = "tmdb",
    scenario: str = "",
) -> dict:
    """Build a single test-case dict.

    Args:
        media_type: "movie" or "tvshow".
        genres: Genre name strings.
        genre_ids: Provider genre IDs, or None for string-fallback cases.
        expected_v14_label: Expected V14 category label (verified by invoking GenreMapper).
        origin_country: Origin country code for anime detection (TV only).
        source: Provider name ("tmdb" or "tvdb") — only relevant for TV.
        scenario: Human-readable description of the scenario.

    Returns:
        Dict representing a single golden test case.
    """
    return {
        "media_type": media_type,
        "genres": genres,
        "genre_ids": genre_ids,
        "origin_country": origin_country,
        "source": source,
        "expected_v14_label": expected_v14_label,
        "scenario": scenario,
    }


def _build_cases() -> list[dict]:
    """Build the full matrix of test cases covering all 11 V14 categories.

    Returns:
        List of test case dicts, each with verified expected_v14_label.
    """
    cases: list[dict] = []

    # --- MOVIES: "films" (default fallback) ---
    cases.append(_case("movie", ["Action"], [28], "films", scenario="movies_id_action_fallback_to_films"))
    cases.append(_case("movie", ["Comedy"], [35], "films", scenario="movies_id_comedy_fallback_to_films"))
    cases.append(_case("movie", ["Drama"], [18], "films", scenario="movies_id_drama_fallback_to_films"))
    cases.append(_case("movie", ["Thriller"], [53], "films", scenario="movies_id_thriller_fallback_to_films"))
    cases.append(_case("movie", ["Action", "Thriller"], [28, 53], "films", scenario="movies_id_multi_genre_no_special"))
    # String-based fallback (no IDs)
    cases.append(_case("movie", ["Action"], None, "films", scenario="movies_string_action_fallback"))
    cases.append(_case("movie", ["Drama", "Romance"], None, "films", scenario="movies_string_multi_no_special"))
    cases.append(_case("movie", [], [], "films", scenario="movies_empty_ids_fallback"))

    # --- MOVIES_ANIMATION: "films animations" ---
    cases.append(_case("movie", ["Animation"], [16], "films animations", scenario="movies_anim_id"))
    cases.append(
        _case("movie", ["Animation", "Action"], [16, 28], "films animations", scenario="movies_anim_id_with_action")
    )
    cases.append(
        _case(
            "movie",
            ["Animation", "Documentary"],
            [16, 99],
            "films animations",
            scenario="movies_anim_id_beats_documentary",
        )
    )
    cases.append(_case("movie", ["animation"], None, "films animations", scenario="movies_anim_string_lowercase"))
    cases.append(_case("movie", ["Animation"], None, "films animations", scenario="movies_anim_string_title_case"))

    # --- MOVIES_DOCUMENTARY: "films documentaires" ---
    cases.append(_case("movie", ["Documentary"], [99], "films documentaires", scenario="movies_doc_id"))
    cases.append(
        _case("movie", ["Documentary", "Drama"], [99, 18], "films documentaires", scenario="movies_doc_id_with_drama")
    )
    cases.append(_case("movie", ["documentary"], None, "films documentaires", scenario="movies_doc_string_lowercase"))
    cases.append(_case("movie", ["Documentaire"], None, "films documentaires", scenario="movies_doc_string_french"))
    cases.append(
        _case("movie", ["Documentary", "Action"], None, "films documentaires", scenario="movies_doc_string_with_action")
    )

    # --- TV_SHOWS: "series" (default fallback) ---
    cases.append(_case("tvshow", ["Drama"], [18], "series", scenario="tv_id_drama_fallback"))
    cases.append(_case("tvshow", ["Comedy"], [35], "series", scenario="tv_id_comedy_fallback"))
    cases.append(_case("tvshow", ["Action & Adventure"], [10759], "series", scenario="tv_id_action_adventure_fallback"))
    cases.append(_case("tvshow", ["Crime"], [80], "series", scenario="tv_id_crime_fallback"))
    cases.append(_case("tvshow", ["Drama"], None, "series", scenario="tv_string_drama_fallback"))
    cases.append(_case("tvshow", ["Fantasy"], None, "series", scenario="tv_string_fantasy_fallback"))
    cases.append(_case("tvshow", [], [], "series", scenario="tv_empty_ids_fallback"))
    cases.append(_case("tvshow", ["Comedy", "Drama"], [35, 18], "series", scenario="tv_id_multi_no_special"))

    # --- TV_SHOWS_ANIMATION: "series animations" (non-JP) ---
    cases.append(_case("tvshow", ["Animation"], [16], "series animations", scenario="tv_anim_tmdb_no_jp"))
    cases.append(
        _case("tvshow", ["Animation", "Comedy"], [16, 35], "series animations", scenario="tv_anim_tmdb_multi_no_jp")
    )
    cases.append(_case("tvshow", ["Animation"], None, "series animations", scenario="tv_anim_string_no_jp"))
    cases.append(_case("tvshow", ["animation"], None, "series animations", scenario="tv_anim_string_lowercase_no_jp"))
    # TVDB Animation (17) = series animations
    cases.append(_case("tvshow", ["Animation"], [17], "series animations", source="tvdb", scenario="tv_anim_tvdb_id"))
    cases.append(
        _case(
            "tvshow",
            ["Animation", "Comedy"],
            [17, 35],
            "series animations",
            source="tvdb",
            scenario="tv_anim_tvdb_multi",
        )
    )

    # --- TV_SHOWS_DOCUMENTARY: "series documentaires" ---
    cases.append(_case("tvshow", ["Documentary"], [99], "series documentaires", scenario="tv_doc_tmdb_id"))
    cases.append(
        _case("tvshow", ["Documentary", "Drama"], [99, 18], "series documentaires", scenario="tv_doc_tmdb_with_drama")
    )
    cases.append(_case("tvshow", ["documentary"], None, "series documentaires", scenario="tv_doc_string_lowercase"))
    cases.append(_case("tvshow", ["Documentaire"], None, "series documentaires", scenario="tv_doc_string_french"))
    # TVDB Documentary (3)
    cases.append(
        _case("tvshow", ["Documentary"], [3], "series documentaires", source="tvdb", scenario="tv_doc_tvdb_id")
    )

    # --- ANIME: "series animes" ---
    # TMDB: Animation + JP origin
    cases.append(_case("tvshow", ["Animation"], [16], "series animes", origin_country="JP", scenario="anime_tmdb_jp"))
    cases.append(
        _case(
            "tvshow",
            ["Animation", "Action"],
            [16, 28],
            "series animes",
            origin_country="JP",
            scenario="anime_tmdb_jp_multi",
        )
    )
    cases.append(
        _case("tvshow", ["Animation"], None, "series animes", origin_country="JP", scenario="anime_string_anim_jp")
    )
    cases.append(
        _case(
            "tvshow",
            ["animation"],
            None,
            "series animes",
            origin_country="JP",
            scenario="anime_string_anim_lowercase_jp",
        )
    )
    cases.append(_case("tvshow", ["anime"], None, "series animes", scenario="anime_string_name_no_jp"))
    cases.append(_case("tvshow", ["Anime"], None, "series animes", scenario="anime_string_name_title_no_jp"))
    # TVDB Anime (27)
    cases.append(_case("tvshow", ["Anime"], [27], "series animes", source="tvdb", scenario="anime_tvdb_id"))
    cases.append(
        _case("tvshow", ["Anime", "Action"], [27, 28], "series animes", source="tvdb", scenario="anime_tvdb_multi")
    )

    # --- TV_PROGRAMS: "emissions" ---
    # TMDB Reality (10764)
    cases.append(_case("tvshow", ["Reality"], [10764], "emissions", scenario="tv_prog_tmdb_reality_id"))
    # TMDB Talk (10767)
    cases.append(_case("tvshow", ["Talk"], [10767], "emissions", scenario="tv_prog_tmdb_talk_id"))
    # TMDB News (10763)
    cases.append(_case("tvshow", ["News"], [10763], "emissions", scenario="tv_prog_tmdb_news_id"))
    # Multiple emission-type IDs
    cases.append(
        _case("tvshow", ["Reality", "Talk"], [10764, 10767], "emissions", scenario="tv_prog_tmdb_reality_talk")
    )
    # String-based fallback
    cases.append(_case("tvshow", ["reality"], None, "emissions", scenario="tv_prog_string_reality"))
    cases.append(_case("tvshow", ["talk show"], None, "emissions", scenario="tv_prog_string_talk_show"))
    cases.append(_case("tvshow", ["news"], None, "emissions", scenario="tv_prog_string_news"))
    cases.append(_case("tvshow", ["Émission"], None, "emissions", scenario="tv_prog_string_french_emission"))
    cases.append(
        _case("tvshow", ["Divertissement"], None, "emissions", scenario="tv_prog_string_french_divertissement")
    )
    # TVDB Reality (8), Talk (10), News (11)
    cases.append(_case("tvshow", ["Reality"], [8], "emissions", source="tvdb", scenario="tv_prog_tvdb_reality"))
    cases.append(_case("tvshow", ["Talk"], [10], "emissions", source="tvdb", scenario="tv_prog_tvdb_talk"))
    cases.append(_case("tvshow", ["News"], [11], "emissions", source="tvdb", scenario="tv_prog_tvdb_news"))

    return cases


def _verify_and_enrich(cases: list[dict]) -> list[dict]:
    """Run each case through GenreMapper and assert the expected label matches.

    Args:
        cases: List of test case dicts with expected_v14_label.

    Returns:
        Verified cases (unchanged if all match).

    Raises:
        AssertionError: If any case produces a label different from expected.
    """
    gm = GenreMapper()
    verified: list[dict] = []
    mismatches: list[str] = []

    for i, case in enumerate(cases):
        media_type = case["media_type"]
        genres = case["genres"]
        genre_ids = case["genre_ids"] if case["genre_ids"] else None
        origin_country = case["origin_country"]
        source = case["source"]
        expected = case["expected_v14_label"]

        if media_type == "movie":
            actual = gm.categorize_movie(genres, genre_ids)
        else:
            actual = gm.categorize_tvshow(
                genres,
                genre_ids,
                origin_country=origin_country,
                source=source,
            )

        if actual != expected:
            mismatches.append(f"  Case {i} ({case['scenario']}): expected '{expected}', got '{actual}'")
        else:
            verified.append(case)

    if mismatches:
        print("MISMATCHES found — fix cases before using as golden table:", file=sys.stderr)
        for m in mismatches:
            print(m, file=sys.stderr)
        sys.exit(1)

    return verified


def main() -> None:
    """Generate and write the golden table to the output path."""
    print("Building golden table cases...")
    cases = _build_cases()

    print(f"Verifying {len(cases)} cases against V14 GenreMapper...")
    verified = _verify_and_enrich(cases)

    # Count categories covered
    categories_covered = {c["expected_v14_label"] for c in verified}
    print(f"Categories covered: {len(categories_covered)} / 11")
    for cat in sorted(categories_covered):
        count = sum(1 for c in verified if c["expected_v14_label"] == cat)
        print(f"  {cat}: {count} cases")

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(verified, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(verified)} cases to {_OUTPUT_PATH}")
    assert len(verified) >= 50, f"Expected ≥50 cases, got {len(verified)}"
    print("OK: ≥50 cases generated.")


if __name__ == "__main__":
    main()
