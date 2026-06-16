"""Regression tests for the directional length-ratio guard in confidence._score_result.

AC-1: query "S03" does NOT accept "Glina. Nowy rozdział" (ratio 0.150 < 0.40 guard threshold).
AC-3: query "Among" does NOT accept "Love Amongst War" (ratio 0.312 < 0.40 guard threshold).
AC-4: "The Hack sur ecoute" still matches "The Hack" (local-longer direction — guard must NOT fire).
      "Top Chef France" still matches "Top Chef" (local-longer direction — guard must NOT fire).
AC-5: "FROM" → "FROM" at 1.0 is unaffected.
"""

from pathlib import Path

from personalscraper.api.metadata._base import SearchResult
from personalscraper.scraper.confidence import HIGH_CONFIDENCE, LOW_CONFIDENCE, _score_result


def _sr(title: str, year: int | None = None, aliases: list[str] | None = None) -> SearchResult:
    """Build a minimal SearchResult for scoring tests."""
    return SearchResult(
        provider="tvdb",
        provider_id="999",
        title=title,
        original_title=title,
        year=year,
        media_type="tvshow",
        aliases=aliases or [],
    )


# ---------------------------------------------------------------------------
# AC-1 — Orville / S03 suppression
# ---------------------------------------------------------------------------


class TestAC1OrvelleSuppression:
    """AC-1: query 'S03' must NOT match 'Glina. Nowy rozdział' despite alias amplification."""

    def test_season_token_rejects_glina_title(self) -> None:
        """_score_result(' S03', None, Glina result) < LOW_CONFIDENCE."""
        result = _sr("Glina. Nowy rozdział", 2025, aliases=["Glina S03"])
        score = _score_result(" S03", None, result)
        assert score < LOW_CONFIDENCE, (
            f"Guard failed: score={score:.3f} — 'S03' matched 'Glina. Nowy rozdział'; "
            "removing the directional guard must be the only way to fix this"
        )

    def test_season_token_normalized_rejects_glina(self) -> None:
        """_score_result('S03', None, Glina result) < LOW_CONFIDENCE (no leading space)."""
        result = _sr("Glina. Nowy rozdział", 2025)
        score = _score_result("S03", None, result)
        assert score < LOW_CONFIDENCE, f"Guard failed: score={score:.3f} for 'S03' vs 'Glina. Nowy rozdział'"


# ---------------------------------------------------------------------------
# AC-3 — Among Us / "Among" suppression
# ---------------------------------------------------------------------------


class TestAC3AmongUsSuppression:
    """AC-3: query 'Among' must NOT match 'Love Amongst War' (ratio 0.312 < 0.40 guard threshold)."""

    def test_among_rejects_love_amongst_war(self) -> None:
        """_score_result('Among', None, 'Love Amongst War') < LOW_CONFIDENCE."""
        result = _sr("Love Amongst War", 2012)
        score = _score_result("Among", None, result)
        assert score < LOW_CONFIDENCE, (
            f"Guard failed: score={score:.3f} — 'Among' matched 'Love Amongst War'; "
            "length ratio is 0.312, well below 0.40 guard threshold"
        )


# ---------------------------------------------------------------------------
# AC-4 — Directional: local-longer must NOT be rejected
# ---------------------------------------------------------------------------


class TestAC4DirectionalPreservation:
    """AC-4: guard must NOT fire when local title is longer than API title."""

    def test_the_hack_sur_ecoute_matches_the_hack(self) -> None:
        """'The Hack sur ecoute' (local-longer) must still match 'The Hack'."""
        result = _sr("The Hack", None)
        score = _score_result("The Hack sur ecoute", None, result)
        # Score may be lower than HIGH_CONFIDENCE (subtitle adds distance),
        # but guard must not reject it entirely — score must be > LOW_CONFIDENCE
        # to prove the guard did not fire on the local-longer direction.
        assert score > LOW_CONFIDENCE, (
            f"Guard incorrectly fired on local-longer match: score={score:.3f} for 'The Hack sur ecoute' → 'The Hack'"
        )

    def test_top_chef_france_matches_top_chef(self) -> None:
        """'Top Chef France' (local-longer) must still score against 'Top Chef'."""
        result = _sr("Top Chef", None)
        score = _score_result("Top Chef France", None, result)
        assert score > LOW_CONFIDENCE, (
            f"Guard incorrectly fired on local-longer match: score={score:.3f} for 'Top Chef France' → 'Top Chef'"
        )


# ---------------------------------------------------------------------------
# AC-5 — Exact / short legit titles unaffected
# ---------------------------------------------------------------------------


class TestAC5ExactShortTitlesUnaffected:
    """AC-5: 'FROM' → 'FROM' at 1.0 must be unaffected by any guard."""

    def test_from_matches_from_at_full_score(self) -> None:
        """_score_result('FROM', None, 'FROM') must be >= HIGH_CONFIDENCE."""
        result = _sr("FROM", None)
        score = _score_result("FROM", None, result)
        assert score >= HIGH_CONFIDENCE, f"Legit short exact match broken: score={score:.3f} for 'FROM' → 'FROM'"


# ---------------------------------------------------------------------------
# AC-2 — Orville recovery: degenerate folder → episode-filename fallback
# ---------------------------------------------------------------------------


class TestAC2OrvilleRecovery:
    """AC-2: a season-token folder with Orville episode files recovers 'The Orville'."""

    def test_recover_title_from_episode_files(self, tmp_path: Path) -> None:
        """_recover_title_from_episodes returns 'The Orville' from episode filenames."""
        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / " S03"
        show_dir.mkdir()
        # Create representative episode files matching the real torrent layout
        (show_dir / "The Orville - S3E01 - Some Episode.mkv").touch()
        (show_dir / "The Orville - S3E02 - Another Episode.mkv").touch()

        recovered = _recover_title_from_episodes(show_dir)
        assert recovered == "The Orville", (
            f"Expected 'The Orville', got {recovered!r}. "
            "NameCleaner.clean() on the first episode file should extract 'The Orville'."
        )

    def test_recover_title_strips_season_token(self, tmp_path: Path) -> None:
        """Recovered title must not contain 'S3'/'S03' residue."""
        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / "S03"
        show_dir.mkdir()
        (show_dir / "The Orville - S3E01.mkv").touch()

        recovered = _recover_title_from_episodes(show_dir)
        assert recovered is not None
        import re  # noqa: PLC0415

        assert not re.search(r"\bS\d+\b", recovered, re.IGNORECASE), (
            f"Recovered title still contains season token: {recovered!r}"
        )

    def test_no_episode_files_returns_none(self, tmp_path: Path) -> None:
        """Empty show dir with no video files returns None (no recovery possible)."""
        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / "S03"
        show_dir.mkdir()
        (show_dir / "subtitles.srt").touch()  # not a video file

        recovered = _recover_title_from_episodes(show_dir)
        assert recovered is None, f"Expected None when no video files present, got {recovered!r}"


# ---------------------------------------------------------------------------
# AC-2 (real layout) — recursive episode scan in Saison NN/ subdirs
# ---------------------------------------------------------------------------


class TestAC2RealLayoutRecovery:
    """AC-2 (real layout): _recover_title_from_episodes must work with Saison-subdir layout.

    The REAL Orville staging folder is ' S03/Saison 3/The Orville - S3E01.mkv'.
    The flat-layout test above passed but the real layout failed because
    show_dir.iterdir() is non-recursive and misses the nested 'Saison 3/' subdir.
    After the fix (rglob), this test must pass.
    """

    def test_recover_title_from_nested_saison_subdir(self, tmp_path: Path) -> None:
        """_recover_title_from_episodes returns 'The Orville' from Saison-subdir layout.

        Build: tmp/' S03'/'Saison 3'/'The Orville - S3E01.mkv' (+ E02).
        Current iterdir() scan FAILS (returns None).
        After rglob fix it must return 'The Orville'.
        """
        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / " S03"
        show_dir.mkdir()
        season_subdir = show_dir / "Saison 3"
        season_subdir.mkdir()
        (season_subdir / "The Orville - S3E01 - Premiere.mkv").touch()
        (season_subdir / "The Orville - S3E02 - Episode Two.mkv").touch()

        recovered = _recover_title_from_episodes(show_dir)
        assert recovered == "The Orville", (
            f"Expected 'The Orville', got {recovered!r}. "
            "iterdir() is non-recursive and misses Saison 3/; rglob() fix is required."
        )

    def test_recover_title_from_nested_subdir_s4c_no_overstrip(self, tmp_path: Path) -> None:
        r"""Recovery keeps 'S4C Documentary' (NOT '') when cleaned title embeds an S-number.

        Filename 'S4C Documentary - S01E01.mkv' -> NameCleaner.clean() = 'S4C Documentary S01E01'.
        The old _SEASON_TOKEN_RE (r'\\s*-?\\s*S\\d+(?:E\\d+)*.*$') strips from the FIRST
        S-digit ('S4C') -> result ''. New regex anchors on S\\d+E\\d+ so the title-internal
        'S4' is safe.
        """
        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / "S01"
        show_dir.mkdir()
        season_subdir = show_dir / "Saison 1"
        season_subdir.mkdir()
        (season_subdir / "S4C Documentary - S01E01.mkv").touch()

        recovered = _recover_title_from_episodes(show_dir)
        assert recovered == "S4C Documentary", (
            f"Over-strip regression: expected 'S4C Documentary', got {recovered!r}. "
            "The regex must anchor on S\\d+E\\d+, not bare S\\d+."
        )


# ---------------------------------------------------------------------------
# AC-6 — empty/whitespace title is degenerate
# ---------------------------------------------------------------------------


class TestAC6EmptyTitleDegenerate:
    """AC-6: is_degenerate_title must return True for empty/whitespace-only input."""

    def test_empty_string_is_degenerate(self) -> None:
        """is_degenerate_title('') must return True (DESIGN: 'empty OR season token')."""
        from personalscraper.scraper.classifier import is_degenerate_title

        assert is_degenerate_title("") is True, "Empty string must be degenerate"

    def test_whitespace_only_is_degenerate(self) -> None:
        """is_degenerate_title('   ') must return True."""
        from personalscraper.scraper.classifier import is_degenerate_title

        assert is_degenerate_title("   ") is True, "Whitespace-only title must be degenerate"

    def test_legit_title_is_not_degenerate(self) -> None:
        """Legit show titles must remain non-degenerate (guard: no regression)."""
        from personalscraper.scraper.classifier import is_degenerate_title

        for title in ("The Orville", "S.W.A.T.", "Sense8", "S4C Documentary", "S Club 7"):
            assert is_degenerate_title(title) is False, f"Legit title incorrectly flagged degenerate: {title!r}"


# ---------------------------------------------------------------------------
# AC-1 (alias amplification — de-vacuum)
# ---------------------------------------------------------------------------


class TestAC1AliasAmplification:
    """AC-1 mutation-proof: guard must fire even when the alias matches well.

    The vacuous test (test_season_token_normalized_rejects_glina, no alias) passes
    even with the guard REMOVED because WRatio('S03', 'Glina. Nowy rozdzial')=0.15.
    This class exercises the ALIAS path: with alias 'Glina S03', WRatio(' S03',
    'Glina S03')≈0.90 — the alias would win if the guard were absent.  With the
    guard in place the query ' S03' is still too short relative to 'Glina. Nowy
    rozdzial' (ratio≈0.12) so the guard rejects ALL api_title candidates including
    the alias, keeping the score < LOW_CONFIDENCE.
    """

    def test_alias_amplification_rejected(self) -> None:
        r"""_score_result(' S03', None, Glina+alias) < LOW_CONFIDENCE despite alias hit.

        Mutation-proof: removing _length_ratio_guard in _score_result would cause
        the alias 'Glina S03' to score ~0.90 and the result would be ACCEPTED.
        """
        from personalscraper.scraper.confidence import LOW_CONFIDENCE, _score_result

        result = _sr("Glina. Nowy rozdział", 2025, aliases=["Glina S03"])
        score = _score_result(" S03", None, result)
        assert score < LOW_CONFIDENCE, (
            f"Alias amplification not blocked: score={score:.3f} — "
            "removing the directional guard is the only way to accept this"
        )


# ---------------------------------------------------------------------------
# Length-ratio guard boundary — pins the 0.40 threshold
# ---------------------------------------------------------------------------


class TestLengthRatioGuardBoundary:
    r"""Pin the 0.40 guard threshold with just-below-rejected and just-above-accepted cases.

    The guard default threshold (_DEFAULT_MIN_LENGTH_RATIO) is 0.40.
    Actual threshold: ratio = len(normed_query) / len(normed_api).
    - ratio < 0.40 → guard fires → candidate title skipped → score = 0.0
    - ratio >= 0.40 → guard does NOT fire → normal WRatio scoring

    Calibrated pairs:
    - 'GO' (normed len 2) vs 'GO AWAY' (normed len 7) → ratio 0.286 → guard fires
    - 'GO' (normed len 2) vs 'GO ON' (normed len 5) → ratio 0.400 → guard does NOT fire
    """

    def test_just_below_threshold_rejected(self) -> None:
        r"""query/api ratio 0.286 < 0.40 → guard fires → score = 0.0.

        'GO' (len 2) vs 'GO AWAY' (normed 'go away', len 7): ratio=0.286 → rejected.
        """
        from personalscraper.scraper.confidence import _score_result

        result = _sr("GO AWAY")
        score = _score_result("GO", None, result)
        assert score == 0.0, f"Expected score=0.0 (guard fires at ratio 0.286), got {score:.3f}"

    def test_just_at_threshold_accepted(self) -> None:
        r"""query/api ratio 0.400 >= 0.40 → guard does NOT fire → WRatio-based score.

        'GO' (len 2) vs 'GO ON' (normed 'go on', len 5): ratio=0.400 → accepted.
        Score is WRatio-based (~0.82) and must be > LOW_CONFIDENCE.
        """
        from personalscraper.scraper.confidence import LOW_CONFIDENCE, _score_result

        result = _sr("GO ON")
        score = _score_result("GO", None, result)
        assert score > LOW_CONFIDENCE, (
            f"Expected score > {LOW_CONFIDENCE} (guard does NOT fire at ratio 0.400), got {score:.3f}"
        )


# ---------------------------------------------------------------------------
# Prince Andrew floor — the case that set the 0.40 threshold
# ---------------------------------------------------------------------------


class TestPrinceAndrewFloor:
    r"""Prince Andrew vs 'Andrew: The Problem Prince' must score >= LOW_CONFIDENCE.

    ratio = len('prince andrew') / len('andrew the problem prince') ≈ 0.52 > 0.40.
    WRatio score ≈ 0.775. This is the real-world case that drove the threshold
    down from 0.67 (bidirectional FuzzyMatchConfig) to 0.40 (directional guard).
    """

    def test_prince_andrew_scores_above_low_confidence(self) -> None:
        r"""'Prince Andrew' → 'Andrew: The Problem Prince' must be accepted (ratio 0.52 > 0.40)."""
        from personalscraper.scraper.confidence import LOW_CONFIDENCE, _score_result

        result = _sr("Andrew: The Problem Prince")
        score = _score_result("Prince Andrew", None, result)
        assert score >= LOW_CONFIDENCE, (
            f"Prince Andrew floor broken: score={score:.3f} < LOW_CONFIDENCE={LOW_CONFIDENCE}. "
            "This is the case that set the 0.40 threshold (not 0.67)."
        )


# ---------------------------------------------------------------------------
# Recovery branch completeness
# ---------------------------------------------------------------------------


class TestRecoveryBranches:
    """Cover the remaining _recover_title_from_episodes branches.

    Non-degenerate gate lives in scrape_tvshow (is_degenerate_title check before
    calling _recover_title_from_episodes), so we test the function itself:
    - empty folder → None
    - multi-file: sorted pick is deterministic (E01 before E02, E03)
    """

    def test_empty_folder_returns_none(self, tmp_path: Path) -> None:
        """_recover_title_from_episodes returns None when no video files exist."""
        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / " S03"
        show_dir.mkdir()
        # Only non-video files
        (show_dir / "info.txt").touch()
        (show_dir / "subtitles.srt").touch()

        assert _recover_title_from_episodes(show_dir) is None

    def test_multi_file_sorted_pick(self, tmp_path: Path) -> None:
        """Multiple episode files: sorted() ensures the first (alphabetically) is picked."""
        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / " S03"
        show_dir.mkdir()
        saison = show_dir / "Saison 3"
        saison.mkdir()
        # Files added in reverse episode order; sorted() must pick E01 first
        (saison / "The Orville - S3E03.mkv").touch()
        (saison / "The Orville - S3E01.mkv").touch()
        (saison / "The Orville - S3E02.mkv").touch()

        recovered = _recover_title_from_episodes(show_dir)
        assert recovered == "The Orville", f"Sorted pick returned wrong title: {recovered!r}"
