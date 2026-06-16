"""Regression tests for the directional length-ratio guard in confidence._score_result.

AC-1: query "S03" does NOT accept "Glina. Nowy rozdział" (ratio 0.150 < 0.67).
AC-3: query "Among" does NOT accept "Love Amongst War" (ratio 0.312 < 0.67).
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
    """AC-3: query 'Among' must NOT match 'Love Amongst War' (ratio 0.312 < 0.67)."""

    def test_among_rejects_love_amongst_war(self) -> None:
        """_score_result('Among', None, 'Love Amongst War') < LOW_CONFIDENCE."""
        result = _sr("Love Amongst War", 2012)
        score = _score_result("Among", None, result)
        assert score < LOW_CONFIDENCE, (
            f"Guard failed: score={score:.3f} — 'Among' matched 'Love Amongst War'; "
            "length ratio is 0.312, well below 0.67"
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
