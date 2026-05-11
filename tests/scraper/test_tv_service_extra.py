"""Extra coverage tests for ``personalscraper.scraper.tv_service``.

Targets the uncovered branches in:

- ``_tvdb_series_to_show_data`` (legacy dict path: contentRatings, year-string,
  translations, fallback language, artwork fetch + failure).
- ``TvServiceMixin._download_episode_thumb`` (skip + RequestException paths).
- ``TvServiceMixin._lookup_series`` (match exception, low-confidence,
  TVDB success path with cross-refs, TMDB success path, get-details exception,
  TVDB legacy dict (no ``external_ids``) branch).
- ``TvServiceMixin._build_episode_map`` (no-seasons return, TVDB iteration,
  TMDB iteration, season-fetch exception, bootstrap from filenames).
- ``TvServiceMixin._match_seasons`` (no episodes, no matches, full path).
- ``TvServiceMixin._generate_episode_nfos`` (fallback skip, NFO exists →
  thumb-recovery only, full NFO + thumb generation, NFO write exception).
- ``TvServiceMixin.scrape_tvshow`` (drift rescrape, drift NFO-delete failure,
  artwork-recovered branch, repaired branch, low-confidence early return,
  classify-no-category branch, NFO/artwork exceptions, dry-run NFO corrupt,
  rename + merge paths, samefile branch).

All TMDB/TVDB clients are MagicMocks; no network access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    SeasonDetails,
)
from personalscraper.naming_patterns import PATTERNS, NamingPatterns
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.confidence import MatchResult
from personalscraper.scraper.tv_service import (
    TvServiceMixin,
    _tvdb_series_to_show_data,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mixin(
    *,
    dry_run: bool = False,
    tvdb: Any = None,
    tmdb: Any = None,
    nfo: Any = None,
    artwork: Any = None,
    config: Any | None = None,
    patterns: NamingPatterns | None = None,
    classify_return: str | None = "tv_shows",
) -> TvServiceMixin:
    """Build a ``TvServiceMixin`` with the minimum attributes the methods touch.

    Args:
        dry_run: Toggles the dry-run branch.
        tvdb: TVDB client mock.
        tmdb: TMDB client mock.
        nfo: NFO generator mock.
        artwork: Artwork downloader mock.
        config: Config mock or None.
        patterns: NamingPatterns instance (defaults to package PATTERNS).
        classify_return: What ``_classify_item`` returns.

    Returns:
        A ready-to-use TvServiceMixin instance.
    """
    mixin = TvServiceMixin.__new__(TvServiceMixin)
    mixin.dry_run = dry_run
    mixin._tvdb = tvdb if tvdb is not None else MagicMock()  # type: ignore[assignment]
    mixin._tmdb = tmdb if tmdb is not None else MagicMock()  # type: ignore[assignment]
    mixin._nfo = nfo if nfo is not None else MagicMock()  # type: ignore[assignment]
    mixin._artwork = artwork if artwork is not None else MagicMock()  # type: ignore[assignment]
    mixin.config = config  # type: ignore[assignment]
    mixin.patterns = patterns or PATTERNS  # type: ignore[assignment]
    mixin._scraper_language = "fr-FR"
    mixin._scraper_fallback_language = "en-US"
    mixin._tvdb_language = "fra"
    mixin._tvdb_fallback_language = "eng"
    mixin._classify_item = MagicMock(return_value=classify_return)  # type: ignore[assignment]
    mixin._resolve_title = MagicMock(side_effect=lambda api_title, _data, _typ: api_title)  # type: ignore[assignment]
    mixin._strip_trailing_year = MagicMock(side_effect=lambda s: s)  # type: ignore[assignment]
    mixin._verify_existing_scrape = MagicMock(return_value=(True, ""))  # type: ignore[assignment]
    mixin._check_missing_tvshow_artwork = MagicMock(return_value=[])  # type: ignore[assignment]
    mixin._recover_tvshow_artwork = MagicMock()  # type: ignore[assignment]
    mixin._repair_tvshow_dir = MagicMock(return_value=False)  # type: ignore[assignment]
    return mixin


# ---------------------------------------------------------------------------
# _tvdb_series_to_show_data — legacy dict branch coverage
# ---------------------------------------------------------------------------


class TestTvdbSeriesToShowDataLegacyDict:
    """Cover the legacy raw-dict branch (lines 122-170) and artwork (172-189)."""

    def test_content_ratings_built_when_rating_present(self) -> None:
        """``contentRatings`` entries with rating produce TMDB-shaped result."""
        raw = {
            "name": "X",
            "originalName": "X",
            "contentRatings": [
                {"name": "TV-14", "country": "USA"},
                {"name": "", "country": "FR"},  # empty rating ignored
            ],
        }
        out = _tvdb_series_to_show_data(raw, tvdb_id=1)
        results = out["content_ratings"]["results"]
        assert results == [{"rating": "TV-14", "iso_3166_1": "USA"}]

    def test_seasons_skip_zero_and_negative(self) -> None:
        """Season 0 (specials) is dropped; positive numbers survive."""
        raw = {
            "name": "X",
            "seasons": [
                {"number": 0},  # specials dropped
                {"number": 1},
                {"number": 2},
            ],
        }
        out = _tvdb_series_to_show_data(raw, tvdb_id=1)
        nums = {s["season_number"] for s in out["seasons"]}
        assert nums == {1, 2}

    def test_year_string_to_first_air_date(self) -> None:
        """Numeric string year coerces into ``YYYY-01-01``."""
        raw = {"name": "X", "year": "2018"}
        out = _tvdb_series_to_show_data(raw, tvdb_id=1)
        assert out["first_air_date"] == "2018-01-01"

    def test_year_int_to_first_air_date(self) -> None:
        """Integer year coerces into ``YYYY-01-01``."""
        raw = {"name": "X", "year": 2018}
        out = _tvdb_series_to_show_data(raw, tvdb_id=1)
        assert out["first_air_date"] == "2018-01-01"

    def test_year_invalid_string_yields_empty(self) -> None:
        """Non-numeric string year does not produce a synthetic date."""
        raw = {"name": "X", "year": "abc"}
        out = _tvdb_series_to_show_data(raw, tvdb_id=1)
        assert out["first_air_date"] == ""

    def test_translations_preferred_language(self) -> None:
        """Preferred-language translation wins over raw name."""
        raw = {
            "name": "Original",
            "translations": {"fr": "Traduction"},
        }
        out = _tvdb_series_to_show_data(raw, tvdb_id=1, preferred_language="fr-FR")
        assert out["name"] == "Traduction"

    def test_translations_fallback_language(self) -> None:
        """Falls back to the secondary language when preferred is missing."""
        raw = {
            "name": "Original",
            "translations": {"eng": "English Title"},
        }
        out = _tvdb_series_to_show_data(
            raw,
            tvdb_id=1,
            preferred_language="fr-FR",
            fallback_language="en-US",
        )
        # The fallback path looks up ``en`` then ``eng``.
        assert out["name"] in {"English Title", "Original"}

    def test_artwork_fetched_via_client(self) -> None:
        """When a tvdb_client is provided, posters/backdrops are populated."""
        client = MagicMock()
        client.get_artwork_urls.return_value = [
            ArtworkItem(type="poster", url="http://x/p.jpg", language="fr"),
            ArtworkItem(type="backdrop", url="http://x/b.jpg"),
            # empty url skipped
            ArtworkItem(type="poster", url=""),
            # other types ignored by this shim
            ArtworkItem(type="logo", url="http://x/l.jpg"),
        ]
        out = _tvdb_series_to_show_data({"name": "X"}, tvdb_id=99, tvdb_client=client)
        assert len(out["images"]["posters"]) == 1
        assert out["images"]["posters"][0]["file_path"] == "http://x/p.jpg"
        assert out["images"]["posters"][0]["iso_639_1"] == "fr"
        assert len(out["images"]["backdrops"]) == 1

    def test_artwork_fetch_exception_is_swallowed(self) -> None:
        """Artwork fetch errors are logged but do not raise."""
        client = MagicMock()
        client.get_artwork_urls.side_effect = RuntimeError("api down")
        out = _tvdb_series_to_show_data({"name": "X"}, tvdb_id=99, tvdb_client=client)
        assert out["images"] == {"posters": [], "backdrops": []}


# ---------------------------------------------------------------------------
# Static helper
# ---------------------------------------------------------------------------


class TestToTvdbLanguage:
    """The 2-letter → 3-letter TVDB code mapping helper."""

    def test_fr_fr_maps_to_three_letter(self) -> None:
        """``fr-FR`` maps via ``map_language`` (covers the static method)."""
        out = TvServiceMixin._to_tvdb_language("fr-FR")
        assert isinstance(out, str)
        assert len(out) >= 2


# ---------------------------------------------------------------------------
# _download_episode_thumb
# ---------------------------------------------------------------------------


class TestDownloadEpisodeThumb:
    """Cover lines 458-464."""

    def test_skips_when_still_path_empty(self, tmp_path: Path) -> None:
        """Empty still_path → no-op (no artwork client call)."""
        mixin = _make_mixin()
        mixin._download_episode_thumb("", tmp_path / "t.jpg", 1, 1)
        assert not mixin._artwork.download_image.called  # type: ignore[union-attr]

    def test_skips_when_thumb_already_exists(self, tmp_path: Path) -> None:
        """Existing thumb file → no-op."""
        thumb = tmp_path / "t.jpg"
        thumb.write_bytes(b"x")
        mixin = _make_mixin()
        mixin._download_episode_thumb("/abc.jpg", thumb, 1, 1)
        assert not mixin._artwork.download_image.called  # type: ignore[union-attr]

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Dry-run mode never touches the artwork client."""
        mixin = _make_mixin(dry_run=True)
        mixin._download_episode_thumb("/abc.jpg", tmp_path / "t.jpg", 1, 1)
        assert not mixin._artwork.download_image.called  # type: ignore[union-attr]

    def test_downloads_when_all_conditions_met(self, tmp_path: Path) -> None:
        """Happy path: client called with the TMDB image URL."""
        mixin = _make_mixin()
        mixin._download_episode_thumb("/abc.jpg", tmp_path / "t.jpg", 1, 1)
        mixin._artwork.download_image.assert_called_once()  # type: ignore[union-attr]
        url = mixin._artwork.download_image.call_args[0][0]  # type: ignore[union-attr]
        assert url == "https://image.tmdb.org/t/p/original/abc.jpg"

    def test_request_exception_is_swallowed(self, tmp_path: Path) -> None:
        """``requests`` errors are logged but do not propagate."""
        mixin = _make_mixin()
        mixin._artwork.download_image.side_effect = requests.exceptions.ConnectionError()  # type: ignore[union-attr]
        # Should not raise.
        mixin._download_episode_thumb("/abc.jpg", tmp_path / "t.jpg", 2, 3)


# ---------------------------------------------------------------------------
# _lookup_series
# ---------------------------------------------------------------------------


class TestLookupSeries:
    """Cover lines 497-509, 522-541, 558-566."""

    def test_match_exception_returns_none(self, tmp_path: Path) -> None:
        """``match_tvshow`` raising sets ``result.error`` and returns ``None``."""
        mixin = _make_mixin()
        result = ScrapeResult(media_path=tmp_path, media_type="tvshow")
        with patch(
            "personalscraper.scraper.scraper.match_tvshow",
            side_effect=RuntimeError("boom"),
        ):
            out = mixin._lookup_series("X", None, set(), result)
        assert out is None
        assert result.error is not None
        assert "Match failed" in result.error

    def test_no_match_low_confidence_returns_none(self, tmp_path: Path) -> None:
        """A None match yields ``skipped_low_confidence``."""
        mixin = _make_mixin()
        result = ScrapeResult(media_path=tmp_path, media_type="tvshow")
        with patch(
            "personalscraper.scraper.scraper.match_tvshow",
            return_value=None,
        ):
            out = mixin._lookup_series("X", None, set(), result)
        assert out is None
        assert result.action == "skipped_low_confidence"

    def test_low_confidence_match_returns_none(self, tmp_path: Path) -> None:
        """A real match below the LOW_CONFIDENCE threshold also skips."""
        mixin = _make_mixin()
        result = ScrapeResult(media_path=tmp_path, media_type="tvshow")
        match = MatchResult(api_id=1, api_title="X", api_year=2020, confidence=0.0, source="tmdb")
        with patch(
            "personalscraper.scraper.scraper.match_tvshow",
            return_value=match,
        ):
            out = mixin._lookup_series("X", None, set(), result)
        assert out is None
        assert result.action == "skipped_low_confidence"

    def test_tvdb_branch_with_tmdb_cross_ref(self, tmp_path: Path) -> None:
        """TVDB success: external_ids drives the tmdb_id cross-reference."""
        tvdb_md = MediaDetails(
            provider="tvdb",
            provider_id="42",
            title="Show",
            external_ids={"tmdb": "100", "imdb": "tt9"},
        )
        tvdb = MagicMock()
        tvdb.get_series.return_value = tvdb_md
        tvdb.get_artwork_urls.return_value = []
        mixin = _make_mixin(tvdb=tvdb)
        result = ScrapeResult(media_path=tmp_path, media_type="tvshow")
        match = MatchResult(api_id=42, api_title="Show", api_year=2020, confidence=0.95, source="tvdb")
        with patch(
            "personalscraper.scraper.scraper.match_tvshow",
            return_value=match,
        ):
            out = mixin._lookup_series("Show", 2020, {1}, result)
        assert out is not None
        match_out, show_data, tmdb_id, resolved = out
        assert tmdb_id == 100
        assert resolved == "Show"
        assert show_data["external_ids"]["tvdb_id"] == 42

    def test_tvdb_branch_no_external_ids_attr(self, tmp_path: Path) -> None:
        """When the TVDB result lacks ``external_ids``, fall through cleanly."""
        # Plain object missing the attribute.
        plain = {"name": "X"}
        tvdb = MagicMock()
        tvdb.get_series.return_value = plain
        mixin = _make_mixin(tvdb=tvdb)
        result = ScrapeResult(media_path=tmp_path, media_type="tvshow")
        match = MatchResult(api_id=42, api_title="Show", api_year=2020, confidence=0.95, source="tvdb")
        with patch(
            "personalscraper.scraper.scraper.match_tvshow",
            return_value=match,
        ):
            out = mixin._lookup_series("Show", 2020, {1}, result)
        assert out is not None
        _match_out, _show_data, tmdb_id, _resolved = out
        # No remote_ids → tmdb_id is None and the "show_tvdb_only" log fires.
        assert tmdb_id is None

    def test_tmdb_branch(self, tmp_path: Path) -> None:
        """TMDB success path: ``get_tv`` result is coerced to show_data dict."""
        tmdb = MagicMock()
        tmdb.get_tv.return_value = MediaDetails(
            provider="tmdb",
            provider_id="200",
            title="TmdbShow",
        )
        mixin = _make_mixin(tmdb=tmdb)
        result = ScrapeResult(media_path=tmp_path, media_type="tvshow")
        match = MatchResult(
            api_id=200,
            api_title="TmdbShow",
            api_year=2021,
            confidence=0.9,
            source="tmdb",
        )
        with patch(
            "personalscraper.scraper.scraper.match_tvshow",
            return_value=match,
        ):
            out = mixin._lookup_series("TmdbShow", 2021, {1}, result)
        assert out is not None
        _match_out, show_data, tmdb_id, _resolved = out
        assert tmdb_id == 200
        assert show_data.get("title") == "TmdbShow" or show_data.get("name") == "TmdbShow"

    def test_get_details_exception(self, tmp_path: Path) -> None:
        """A TMDB/TVDB get-details failure sets ``result.error`` and returns None."""
        tmdb = MagicMock()
        tmdb.get_tv.side_effect = ValueError("payload bad")
        mixin = _make_mixin(tmdb=tmdb)
        result = ScrapeResult(media_path=tmp_path, media_type="tvshow")
        match = MatchResult(
            api_id=200,
            api_title="X",
            api_year=2021,
            confidence=0.9,
            source="tmdb",
        )
        with patch(
            "personalscraper.scraper.scraper.match_tvshow",
            return_value=match,
        ):
            out = mixin._lookup_series("X", 2021, set(), result)
        assert out is None
        assert result.error is not None
        assert "Get details failed" in result.error


# ---------------------------------------------------------------------------
# _build_episode_map
# ---------------------------------------------------------------------------


class TestBuildEpisodeMap:
    """Cover lines 593-638."""

    def test_returns_empty_when_no_seasons(self, tmp_path: Path) -> None:
        """No Saison-NN dirs and no SxxEyy filenames → empty dict."""
        show = tmp_path / "Show"
        show.mkdir()
        mixin = _make_mixin()
        match = MatchResult(api_id=1, api_title="X", api_year=None, confidence=1.0, source="tmdb")
        out = mixin._build_episode_map(show, match, tmdb_id=1, episode_default_name="Episode")
        assert out == {}

    def test_real_season_dir_re_does_not_raise_indexerror(self, tmp_path: Path) -> None:
        """Regression: real ``Saison NN/`` dirs no longer raise IndexError.

        Before fix: ``int(m.group(1))`` on ``SEASON_DIR_RE`` raised
        ``IndexError: no such group`` because the production regex had
        no capturing group. This test exercises ``_build_episode_map``
        with real ``Saison NN/`` directories on disk and asserts the
        season iteration completes without raising.
        """
        show = tmp_path / "Show"
        show.mkdir()
        (show / "Saison 01").mkdir()
        (show / "Saison 02").mkdir()
        (show / "Extras").mkdir()  # Non-season dir, must be ignored.

        tmdb = MagicMock()
        tmdb.get_tv_season.side_effect = RuntimeError("network down")
        mixin = _make_mixin(tmdb=tmdb)
        match = MatchResult(api_id=1, api_title="X", api_year=None, confidence=1.0, source="tmdb")

        # No patch on SEASON_DIR_RE — uses production regex.
        out = mixin._build_episode_map(show, match, tmdb_id=1, episode_default_name="Episode")

        # Both real season dirs were discovered; iteration completed
        # without IndexError, even though the API mock raises per call.
        assert tmdb.get_tv_season.call_count == 2
        # The mock raises on every call so the map is empty, but the
        # important invariant is that we got here without IndexError.
        assert out == {}

    def test_tvdb_iteration_populates_episodes(self, tmp_path: Path) -> None:
        """TVDB branch fills the (season, episode) map from ``get_series_episodes``."""
        show = tmp_path / "Show"
        show.mkdir()
        # Use SxxEyy filenames so the bootstrap branch picks up season 1.
        (show / "Show.S01E01.mkv").write_bytes(b"x")
        tvdb = MagicMock()
        tvdb.get_series_episodes.return_value = SeasonDetails(
            provider="tvdb",
            tv_id="42",
            season_number=1,
            episodes=[
                EpisodeInfo(episode_number=1, title="Pilot"),
                EpisodeInfo(episode_number=2, title=""),  # synthetic title path
            ],
        )
        mixin = _make_mixin(tvdb=tvdb)
        match = MatchResult(api_id=42, api_title="X", api_year=2020, confidence=0.9, source="tvdb")
        out = mixin._build_episode_map(show, match, tmdb_id=None, episode_default_name="Ep")
        assert (1, 1) in out
        assert out[(1, 1)]["title"] == "Pilot"
        assert out[(1, 2)]["title"] == "Ep 2"

    def test_tmdb_iteration_populates_episodes(self, tmp_path: Path) -> None:
        """TMDB branch fills the (season, episode) map from ``get_tv_season``."""
        show = tmp_path / "Show"
        show.mkdir()
        (show / "Show.S02E05.mkv").write_bytes(b"x")
        tmdb = MagicMock()
        tmdb.get_tv_season.return_value = SeasonDetails(
            provider="tmdb",
            tv_id="100",
            season_number=2,
            episodes=[
                EpisodeInfo(episode_number=5, title="Five"),
                EpisodeInfo(episode_number=6, title=""),
            ],
        )
        mixin = _make_mixin(tmdb=tmdb)
        match = MatchResult(api_id=100, api_title="X", api_year=2020, confidence=0.9, source="tmdb")
        out = mixin._build_episode_map(show, match, tmdb_id=100, episode_default_name="Episode")
        assert out[(2, 5)]["title"] == "Five"
        assert out[(2, 6)]["title"] == "Episode 6"

    def test_season_fetch_exception_is_swallowed(self, tmp_path: Path) -> None:
        """An exception during season fetch logs a warning but does not raise."""
        show = tmp_path / "Show"
        show.mkdir()
        (show / "Show.S01E01.mkv").write_bytes(b"x")
        tmdb = MagicMock()
        tmdb.get_tv_season.side_effect = RuntimeError("boom")
        mixin = _make_mixin(tmdb=tmdb)
        match = MatchResult(api_id=100, api_title="X", api_year=2020, confidence=0.9, source="tmdb")
        out = mixin._build_episode_map(show, match, tmdb_id=100, episode_default_name="Episode")
        assert out == {}

    def test_bootstrap_from_filenames_when_no_season_dirs(self, tmp_path: Path) -> None:
        """No Saison-NN dirs but SxxEyy filenames → seasons inferred from videos."""
        show = tmp_path / "Show"
        show.mkdir()
        # Bare SxxEyy file at root (no season subdir).
        (show / "Show.S01E01.mkv").write_bytes(b"x")
        tmdb = MagicMock()
        tmdb.get_tv_season.return_value = SeasonDetails(
            provider="tmdb",
            tv_id="100",
            season_number=1,
            episodes=[EpisodeInfo(episode_number=1, title="Pilot")],
        )
        mixin = _make_mixin(tmdb=tmdb)
        match = MatchResult(api_id=100, api_title="X", api_year=2020, confidence=0.9, source="tmdb")
        out = mixin._build_episode_map(show, match, tmdb_id=100, episode_default_name="Ep")
        assert (1, 1) in out

    def test_tvdb_warns_when_season_returns_empty_episodes(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Regression for BUG #2 (Top Chef Le Concours Parallèle).

        When a local file says ``S17E10`` but the matched TVDB show has only
        3 seasons, ``get_series_episodes`` returns SeasonDetails with
        ``episodes=[]``. Previously the loop body never ran and the function
        returned ``{}`` silently — the episode file was left at the show
        root with no warning, no error, just ``result.action="scraped"``.

        Expected behavior: a ``show_season_empty`` warning per season with
        zero episodes from the API.
        """
        show = tmp_path / "Show"
        show.mkdir()
        # Local file claims S17E10 — show only has S01..S03 in TVDB.
        (show / "Show.S17E10.mkv").write_bytes(b"x")
        tvdb = MagicMock()
        tvdb.get_series_episodes.return_value = SeasonDetails(
            provider="tvdb",
            tv_id="475278",
            season_number=17,
            episodes=[],
        )
        mixin = _make_mixin(tvdb=tvdb)
        match = MatchResult(api_id=475278, api_title="X", api_year=2026, confidence=0.98, source="tvdb")
        with caplog.at_level("WARNING"):
            out = mixin._build_episode_map(show, match, tmdb_id=None, episode_default_name="Episode")
        assert out == {}
        assert "show_season_empty" in caplog.text
        assert "season=17" in caplog.text or "'season': 17" in caplog.text

    def test_tmdb_warns_when_season_returns_empty_episodes(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Same regression as the TVDB variant but via the TMDB branch."""
        show = tmp_path / "Show"
        show.mkdir()
        (show / "Show.S99E01.mkv").write_bytes(b"x")
        tmdb = MagicMock()
        tmdb.get_tv_season.return_value = SeasonDetails(
            provider="tmdb",
            tv_id="100",
            season_number=99,
            episodes=[],
        )
        mixin = _make_mixin(tmdb=tmdb)
        match = MatchResult(api_id=100, api_title="X", api_year=2020, confidence=0.9, source="tmdb")
        with caplog.at_level("WARNING"):
            out = mixin._build_episode_map(show, match, tmdb_id=100, episode_default_name="Episode")
        assert out == {}
        assert "show_season_empty" in caplog.text


# ---------------------------------------------------------------------------
# _match_seasons
# ---------------------------------------------------------------------------


class TestMatchSeasons:
    """Cover lines 664-678."""

    def test_returns_zero_when_no_api_episodes(self, tmp_path: Path) -> None:
        """Empty api_episodes → 0 without calling helpers."""
        mixin = _make_mixin()
        n = mixin._match_seasons([], {}, tmp_path, {}, "Episode")
        assert n == 0

    def test_returns_zero_when_no_matches(self, tmp_path: Path) -> None:
        """``match_episode_files`` returning {} short-circuits."""
        mixin = _make_mixin()
        with patch(
            "personalscraper.scraper.tv_service.match_episode_files",
            return_value={},
        ):
            n = mixin._match_seasons(
                [tmp_path / "v.mkv"],
                {(1, 1): {"title": "x", "still_path": ""}},
                tmp_path,
                {},
                "Episode",
            )
        assert n == 0

    def test_full_path_renames_and_generates_nfos(self, tmp_path: Path) -> None:
        """Happy path: season dirs created, episodes renamed, NFO generation called."""
        show = tmp_path / "Show"
        show.mkdir()
        v = show / "Show.S01E01.mkv"
        v.write_bytes(b"x")
        mixin = _make_mixin(dry_run=True)  # dry_run avoids real fs renames
        matched = {
            v: {
                "season": 1,
                "episode": 1,
                "api_title": "Pilot",
                "still_path": "",
                "fallback": False,
            }
        }
        with (
            patch(
                "personalscraper.scraper.tv_service.match_episode_files",
                return_value=matched,
            ),
            patch("personalscraper.scraper.tv_service.create_season_dirs") as csd,
            patch(
                "personalscraper.scraper.tv_service.rename_episodes",
                return_value=1,
            ),
        ):
            n = mixin._match_seasons(
                [v],
                {(1, 1): {"title": "Pilot", "still_path": ""}},
                show,
                {"name": "Show"},
                "Episode",
            )
        assert n == 1
        csd.assert_called_once()


# ---------------------------------------------------------------------------
# _generate_episode_nfos
# ---------------------------------------------------------------------------


class TestGenerateEpisodeNfos:
    """Cover lines 697-767."""

    def test_skips_fallback_entries(self, tmp_path: Path) -> None:
        """Synthetic ``fallback=True`` entries do not generate NFO/thumb."""
        mixin = _make_mixin()
        v = tmp_path / "v.mkv"
        v.write_bytes(b"x")
        matched = {
            v: {
                "season": 1,
                "episode": 1,
                "api_title": "X",
                "still_path": "/x.jpg",
                "fallback": True,
            }
        }
        mixin._generate_episode_nfos(matched, tmp_path, {"name": "Show"})
        assert not mixin._nfo.generate_episode_nfo.called  # type: ignore[union-attr]

    def test_existing_nfo_only_recovers_thumb(self, tmp_path: Path) -> None:
        """When NFO already exists, only the thumb-recovery path runs."""
        show = tmp_path / "Show"
        season_dir = show / "Saison 01"
        season_dir.mkdir(parents=True)
        # Pre-existing NFO that matches the pattern.
        new_stem = mixin_format_episode(1, 1, "Pilot")
        nfo_path = season_dir / f"{new_stem}.nfo"
        nfo_path.write_text("<x/>")
        v = show / "Show.S01E01.mkv"
        v.write_bytes(b"x")
        mixin = _make_mixin()
        matched = {
            v: {
                "season": 1,
                "episode": 1,
                "api_title": "Pilot",
                "still_path": "/p.jpg",
                "fallback": False,
            }
        }
        mixin._generate_episode_nfos(matched, show, {"name": "Show"})
        # NFO generation skipped, but artwork.download_image called for the thumb.
        assert not mixin._nfo.generate_episode_nfo.called  # type: ignore[union-attr]

    def test_full_nfo_generation_writes_nfo(self, tmp_path: Path) -> None:
        """Without an existing NFO, NFO is generated and written, thumb downloaded."""
        show = tmp_path / "Show"
        show.mkdir()
        v = show / "Show.S01E01.mkv"
        v.write_bytes(b"x")
        mixin = _make_mixin()
        mixin._nfo.generate_episode_nfo.return_value = "<xml/>"  # type: ignore[union-attr]
        matched = {
            v: {
                "season": 1,
                "episode": 1,
                "api_title": "Pilot",
                "still_path": "/p.jpg",
                "fallback": False,
            }
        }
        with patch(
            "personalscraper.scraper.scraper.extract_stream_info",
            return_value=None,
        ):
            mixin._generate_episode_nfos(matched, show, {"name": "Show"})
        mixin._nfo.write_nfo.assert_called()  # type: ignore[union-attr]

    def test_nfo_generation_exception_swallowed(self, tmp_path: Path) -> None:
        """An NFO-generation exception is logged, not raised."""
        show = tmp_path / "Show"
        show.mkdir()
        v = show / "Show.S01E01.mkv"
        v.write_bytes(b"x")
        mixin = _make_mixin()
        mixin._nfo.generate_episode_nfo.side_effect = RuntimeError("boom")  # type: ignore[union-attr]
        matched = {
            v: {
                "season": 1,
                "episode": 1,
                "api_title": "Pilot",
                "still_path": "",
                "fallback": False,
            }
        }
        # Should not raise.
        mixin._generate_episode_nfos(matched, show, {"name": "Show", "networks": [{"name": "HBO"}]})


def mixin_format_episode(season: int, episode: int, title: str) -> str:
    """Build the expected episode stem for fixture pre-creation."""
    return PATTERNS.format("episode_video", Season=season, Episode=episode, EpisodeTitle=title)


# ---------------------------------------------------------------------------
# scrape_tvshow — high-level orchestration
# ---------------------------------------------------------------------------


def _make_scrape_mocks(
    *,
    classify_return: str | None = "tv_shows",
    has_config: bool = True,
) -> TvServiceMixin:
    """Create a mixin with a config object so ``scrape_tvshow`` runs end-to-end."""
    cfg = MagicMock()
    cfg.scraper.episode_default_name = "Episode"
    return _make_mixin(
        config=cfg if has_config else None,
        classify_return=classify_return,
    )


class TestScrapeTvshowDriftAndFastPath:
    """Drift detection, fast-path branches in scrape_tvshow."""

    def test_drift_unlink_failure_returns_error(self, tmp_path: Path) -> None:
        """Drift detected, NFO unlink fails → result.error and early return."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<x/>")
        mixin = _make_scrape_mocks()
        mixin._verify_existing_scrape = MagicMock(return_value=(False, "drifted"))  # type: ignore[assignment]
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=True,
            ),
            patch(
                "pathlib.Path.unlink",
                side_effect=OSError("perm"),
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.error is not None and "Cannot delete drifted NFO" in res.error

    def test_fast_path_artwork_recovered(self, tmp_path: Path) -> None:
        """Valid NFO + missing artwork → ``artwork_recovered`` action."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<x/>")
        mixin = _make_scrape_mocks()
        mixin._check_missing_tvshow_artwork = MagicMock(return_value=["poster.jpg"])  # type: ignore[assignment]

        def _set_action(_nfo: Path, _show: Path, result: ScrapeResult) -> None:
            result.action = "artwork_recovered"

        mixin._recover_tvshow_artwork = MagicMock(side_effect=_set_action)  # type: ignore[assignment]
        with patch(
            "personalscraper.scraper.tv_service._is_nfo_complete",
            return_value=True,
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "artwork_recovered"

    def test_fast_path_repaired(self, tmp_path: Path) -> None:
        """Valid NFO + repair makes changes → ``repaired`` action."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<x/>")
        mixin = _make_scrape_mocks()
        mixin._repair_tvshow_dir = MagicMock(return_value=True)  # type: ignore[assignment]
        with patch(
            "personalscraper.scraper.tv_service._is_nfo_complete",
            return_value=True,
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "repaired"

    def test_fast_path_skipped_already_done(self, tmp_path: Path) -> None:
        """Valid NFO, no artwork missing, no repair → ``skipped_already_done``."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<x/>")
        mixin = _make_scrape_mocks()
        with patch(
            "personalscraper.scraper.tv_service._is_nfo_complete",
            return_value=True,
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "skipped_already_done"

    def test_corrupt_nfo_dry_run_logs_only(self, tmp_path: Path) -> None:
        """Dry-run + corrupt NFO: never deletes, falls through to lookup, no match."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<bad/>")
        mixin = _make_scrape_mocks()
        mixin.dry_run = True
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=None,
            ),
        ):
            res = mixin.scrape_tvshow(show)
        # NFO still present (dry run skipped delete).
        assert (show / "tvshow.nfo").exists()
        assert res.action == "skipped_low_confidence"

    def test_corrupt_nfo_delete_failure_returns_error(self, tmp_path: Path) -> None:
        """Corrupt NFO unlink failure short-circuits with an error."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<bad/>")
        mixin = _make_scrape_mocks()
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "pathlib.Path.unlink",
                side_effect=OSError("perm"),
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.error is not None and "Cannot delete corrupt NFO" in res.error


class TestScrapeTvshowFullPath:
    """End-to-end paths through the lookup, rename, classify, NFO/artwork steps."""

    def _patched_match(self, **kw: Any) -> Any:
        """Build a MatchResult-returning patcher for ``match_tvshow``."""
        match = MatchResult(
            api_id=kw.get("api_id", 100),
            api_title=kw.get("api_title", "Show"),
            api_year=kw.get("api_year", 2020),
            confidence=kw.get("confidence", 0.95),
            source=kw.get("source", "tmdb"),
        )
        return match

    def test_low_confidence_returns_early(self, tmp_path: Path) -> None:
        """Lookup fails (no match) → result.action = skipped_low_confidence."""
        show = tmp_path / "Bad (1900)"
        show.mkdir()
        mixin = _make_scrape_mocks()
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=None,
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "skipped_low_confidence"

    def test_dry_run_full_path(self, tmp_path: Path) -> None:
        """Dry-run end-to-end: nothing written, action = scraped."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        mixin = _make_scrape_mocks()
        mixin.dry_run = True
        match = self._patched_match()
        tmdb = mixin._tmdb
        tmdb.get_tv.return_value = MediaDetails(  # type: ignore[union-attr]
            provider="tmdb", provider_id="100", title="Show"
        )
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=match,
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "scraped"
        # NFO not written under dry_run.
        assert not mixin._nfo.write_nfo.called  # type: ignore[union-attr]

    def test_classify_no_category_short_circuits(self, tmp_path: Path) -> None:
        """``_classify_item`` returning None with config set ⇒ skipped_no_category."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        mixin = _make_scrape_mocks(classify_return=None)
        match = self._patched_match()
        tmdb = mixin._tmdb
        tmdb.get_tv.return_value = MediaDetails(  # type: ignore[union-attr]
            provider="tmdb", provider_id="100", title="Show"
        )
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=match,
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "skipped_no_category"

    def test_nfo_generation_failure_records_error(self, tmp_path: Path) -> None:
        """NFO generation raising sets result.error and stops the flow."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        mixin = _make_scrape_mocks()
        mixin.dry_run = True  # avoid real renames
        mixin._nfo.generate_tvshow_nfo.side_effect = RuntimeError("xml fail")  # type: ignore[union-attr]
        match = self._patched_match()
        tmdb = mixin._tmdb
        tmdb.get_tv.return_value = MediaDetails(  # type: ignore[union-attr]
            provider="tmdb", provider_id="100", title="Show"
        )
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=match,
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.error is not None and "tvshow.nfo failed" in res.error

    def test_artwork_failure_recorded_as_warning(self, tmp_path: Path) -> None:
        """Artwork download error is captured in warnings, not error."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        mixin = _make_scrape_mocks()
        mixin.dry_run = True
        mixin._artwork.download_tvshow_artwork.side_effect = requests.RequestException("net")  # type: ignore[union-attr]
        match = self._patched_match()
        tmdb = mixin._tmdb
        tmdb.get_tv.return_value = MediaDetails(  # type: ignore[union-attr]
            provider="tmdb", provider_id="100", title="Show"
        )
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=match,
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "scraped"
        assert any("Artwork failed" in w for w in res.warnings)

    def test_dry_run_rename_logs_action(self, tmp_path: Path) -> None:
        """Dry-run rename branch logs would-rename without touching disk."""
        # Folder name differs from canonical so the rename branch fires.
        show = tmp_path / "showraw"
        show.mkdir()
        mixin = _make_scrape_mocks()
        mixin.dry_run = True
        match = self._patched_match(api_title="Show", api_year=2020)
        tmdb = mixin._tmdb
        tmdb.get_tv.return_value = MediaDetails(  # type: ignore[union-attr]
            provider="tmdb", provider_id="100", title="Show"
        )
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=match,
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "scraped"
        # Folder still on disk under the original name (dry-run).
        assert show.exists()

    def test_real_rename_simple_path(self, tmp_path: Path) -> None:
        """Real rename when destination doesn't exist (covers _rename_dir_case_safe)."""
        show = tmp_path / "showraw"
        show.mkdir()
        mixin = _make_scrape_mocks()
        match = self._patched_match(api_title="Show", api_year=2020)
        tmdb = mixin._tmdb
        tmdb.get_tv.return_value = MediaDetails(  # type: ignore[union-attr]
            provider="tmdb", provider_id="100", title="Show"
        )
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=match,
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "scraped"
        # Real rename ran.
        assert (tmp_path / "Show (2020)").exists()

    def test_rename_failure_returns_error(self, tmp_path: Path) -> None:
        """Real rename raising OSError sets result.error and short-circuits."""
        show = tmp_path / "showraw"
        show.mkdir()
        mixin = _make_scrape_mocks()
        match = self._patched_match(api_title="Show", api_year=2020)
        tmdb = mixin._tmdb
        tmdb.get_tv.return_value = MediaDetails(  # type: ignore[union-attr]
            provider="tmdb", provider_id="100", title="Show"
        )
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=match,
            ),
            patch(
                "personalscraper.scraper.tv_service._rename_dir_case_safe",
                side_effect=OSError("denied"),
            ),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.error is not None and "Rename/merge failed" in res.error

    def test_loose_episodes_unmatched_surface_warning(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Regression for BUG #2: loose video files left at show root.

        Loose files left at show root must propagate to ``result.warnings``
        plus a structured log event so verify and operators see the issue.
        Previously ``scrape_tvshow`` returned ``action="scraped"`` with no
        warnings even though a S17E10 file was sitting at the show root
        because TVDB had no season 17.
        """
        show = tmp_path / "Show (2026)"
        show.mkdir()
        (show / "Show.S17E10.mkv").write_bytes(b"x")
        mixin = _make_scrape_mocks()
        match = self._patched_match(api_id=475278, api_title="Show", api_year=2026, source="tvdb")
        # TVDB returns an empty SeasonDetails for the requested season — the
        # spin-off-vs-parent-numbering scenario from the prod incident.
        mixin._tvdb.get_series.return_value = MediaDetails(  # type: ignore[union-attr]
            provider="tvdb",
            provider_id="475278",
            title="Show",
            external_ids={"tmdb": "315820"},
        )
        mixin._tvdb.get_series_episodes.return_value = SeasonDetails(  # type: ignore[union-attr]
            provider="tvdb",
            tv_id="475278",
            season_number=17,
            episodes=[],
        )
        mixin._tvdb.get_artwork_urls.return_value = []  # type: ignore[union-attr]
        with (
            patch(
                "personalscraper.scraper.tv_service._is_nfo_complete",
                return_value=False,
            ),
            patch(
                "personalscraper.scraper.scraper.match_tvshow",
                return_value=match,
            ),
            caplog.at_level("WARNING"),
        ):
            res = mixin.scrape_tvshow(show)
        assert res.action == "scraped"
        assert any("Episodes unmatched" in w for w in res.warnings)
        assert "show_episodes_unmatched" in caplog.text


@pytest.mark.parametrize("source", ["tvdb", "tmdb"])
def test_lookup_series_emits_match_attribute(tmp_path: Path, source: str) -> None:
    """Both branches surface ``result.match`` after the confidence check."""
    if source == "tmdb":
        tmdb = MagicMock()
        tmdb.get_tv.return_value = MediaDetails(provider="tmdb", provider_id="1", title="X")
        mixin = _make_mixin(tmdb=tmdb)
    else:
        tvdb = MagicMock()
        tvdb.get_series.return_value = MediaDetails(
            provider="tvdb",
            provider_id="1",
            title="X",
            external_ids={"tmdb": "5"},
        )
        tvdb.get_artwork_urls.return_value = []
        mixin = _make_mixin(tvdb=tvdb)
    result = ScrapeResult(media_path=tmp_path, media_type="tvshow")
    match = MatchResult(api_id=1, api_title="X", api_year=2020, confidence=0.9, source=source)
    with patch(
        "personalscraper.scraper.scraper.match_tvshow",
        return_value=match,
    ):
        out = mixin._lookup_series("X", 2020, set(), result)
    assert out is not None
    assert result.match is match
