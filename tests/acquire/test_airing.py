"""Tests for acquire/airing.py — aired predicate helpers (Phase 1)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


def test_parse_date_valid_past() -> None:
    """_parse_date returns a date for a valid ISO-8601 string."""
    from personalscraper.acquire.airing import _parse_date

    result = _parse_date("2023-01-15")
    assert result == date(2023, 1, 15)


def test_parse_date_empty_string_returns_none() -> None:
    """_parse_date returns None for an empty string (TBA / unknown)."""
    from personalscraper.acquire.airing import _parse_date

    assert _parse_date("") is None


def test_parse_date_malformed_returns_none() -> None:
    """_parse_date returns None for a non-ISO string — never raises."""
    from personalscraper.acquire.airing import _parse_date

    assert _parse_date("January 15, 2023") is None
    assert _parse_date("2023/01/15") is None
    assert _parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# _is_aired
# ---------------------------------------------------------------------------


def test_is_aired_past_date_true() -> None:
    """LOAD-BEARING: an episode with a past air-date is aired."""
    from personalscraper.acquire.airing import _is_aired

    today = date(2024, 6, 1)
    assert _is_aired("2023-01-15", today) is True


def test_is_aired_future_date_false() -> None:
    """LOAD-BEARING: an episode with a future air-date is NOT aired."""
    from personalscraper.acquire.airing import _is_aired

    today = date(2024, 6, 1)
    assert _is_aired("2025-12-31", today) is False


def test_is_aired_today_boundary_true() -> None:
    """LOAD-BEARING: air_date == today counts as aired (<= today inclusive)."""
    from personalscraper.acquire.airing import _is_aired

    today = date(2024, 6, 15)
    assert _is_aired("2024-06-15", today) is True


def test_is_aired_empty_string_false() -> None:
    """LOAD-BEARING: empty air_date (TBA) is never aired, never raises."""
    from personalscraper.acquire.airing import _is_aired

    assert _is_aired("", date(2024, 6, 1)) is False


def test_is_aired_malformed_false() -> None:
    """LOAD-BEARING: malformed air_date is never aired, never raises."""
    from personalscraper.acquire.airing import _is_aired

    assert _is_aired("not-a-date", date(2024, 6, 1)) is False


# ---------------------------------------------------------------------------
# Helpers shared by service tests
# ---------------------------------------------------------------------------


def _make_episode(ep_num: int, season_num: int, air_date: str, title: str = "") -> MagicMock:
    """Build a mock EpisodeInfo with known air_date."""
    ep = MagicMock()
    ep.episode_number = ep_num
    ep.season_number = season_num
    ep.air_date = air_date
    ep.title = title
    return ep


def _make_season(season_number: int) -> MagicMock:
    """Build a mock SeasonInfo."""
    s = MagicMock()
    s.season_number = season_number
    return s


def _make_registry(tv_provider: MagicMock, ep_fetcher: MagicMock) -> MagicMock:
    """Build a mock ProviderRegistry returning [tv_provider] and [ep_fetcher]."""
    from personalscraper.api.metadata._contracts import EpisodeFetcher, TvDetailsProvider

    def _chain(cap):
        if cap is TvDetailsProvider:
            return [tv_provider]
        if cap is EpisodeFetcher:
            return [ep_fetcher]
        return []

    registry = MagicMock()
    registry.chain.side_effect = _chain
    return registry


def _make_series(tvdb_id: int, title: str = "Test Show") -> MagicMock:
    """Build a mock FollowedSeries with a MediaRef."""
    from personalscraper.core.identity import MediaRef

    fs = MagicMock()
    fs.title = title
    fs.media_ref = MediaRef(tvdb_id=tvdb_id)
    return fs


# ---------------------------------------------------------------------------
# Golden test — assert WHICH episodes (not len > 0)
# ---------------------------------------------------------------------------


def test_poll_aired_golden() -> None:
    """LOAD-BEARING golden: past → surfaced, future → absent, today → surfaced, empty/malformed → absent."""
    from datetime import date

    from personalscraper.acquire.airing import poll_aired
    from personalscraper.core.identity import MediaRef

    TODAY = date(2024, 6, 15)
    TVDB_ID = 81189

    ep_past = _make_episode(1, 1, "2023-01-10", "Past Episode")
    ep_future = _make_episode(2, 1, "2025-12-31", "Future Episode")
    ep_today = _make_episode(3, 1, "2024-06-15", "Today Episode")
    ep_empty = _make_episode(4, 1, "", "TBA Episode")
    ep_malformed = _make_episode(5, 1, "not-a-date", "Malformed Episode")

    ep_fetcher = MagicMock()
    ep_fetcher.get_episodes.return_value = [ep_past, ep_future, ep_today, ep_empty, ep_malformed]

    tv_provider = MagicMock()
    details = MagicMock()
    details.seasons = [_make_season(1)]
    tv_provider.get_tv.return_value = details

    registry = _make_registry(tv_provider, ep_fetcher)
    series = [_make_series(TVDB_ID, "Breaking Bad")]

    aired = poll_aired(series, registry, today=TODAY)

    expected_ref = MediaRef(tvdb_id=TVDB_ID)
    aired_episodes = [(e.season, e.episode, e.air_date) for e in aired]

    assert (1, 1, date(2023, 1, 10)) in aired_episodes, "Past episode must be surfaced"
    assert (1, 3, date(2024, 6, 15)) in aired_episodes, "Today episode must be surfaced (inclusive)"
    assert not any(e.episode == 2 for e in aired), "Future episode must be absent"
    assert not any(e.episode == 4 for e in aired), "Empty air_date must be absent"
    assert not any(e.episode == 5 for e in aired), "Malformed air_date must be absent"
    assert all(e.media_ref == expected_ref for e in aired), "media_ref must match the series ref"


# ---------------------------------------------------------------------------
# Set-poll aggregate — 2 series, each AiredEpisode carries its series' media_ref
# ---------------------------------------------------------------------------


def test_poll_aired_set_poll_aggregate() -> None:
    """LOAD-BEARING: 2-series poll aggregates all aired episodes, each with correct media_ref."""
    from datetime import date

    from personalscraper.acquire.airing import poll_aired
    from personalscraper.core.identity import MediaRef

    TODAY = date(2024, 6, 15)
    TVDB_A, TVDB_B = 81189, 153021

    ep_a = _make_episode(1, 1, "2023-05-01", "Show A Ep1")
    ep_b = _make_episode(1, 2, "2024-03-10", "Show B Ep1")

    def ep_fetcher_side_effect(series_id, season):
        if str(series_id) == str(TVDB_A):
            return [ep_a]
        return [ep_b]

    ep_fetcher = MagicMock()
    ep_fetcher.get_episodes.side_effect = ep_fetcher_side_effect

    tv_provider = MagicMock()

    def get_tv_side_effect(tvdb_id):
        details = MagicMock()
        details.seasons = [_make_season(1)] if tvdb_id == TVDB_A else [_make_season(2)]
        return details

    tv_provider.get_tv.side_effect = get_tv_side_effect

    registry = _make_registry(tv_provider, ep_fetcher)
    series = [_make_series(TVDB_A, "Show A"), _make_series(TVDB_B, "Show B")]

    aired = poll_aired(series, registry, today=TODAY)

    refs = {e.media_ref for e in aired}
    assert MediaRef(tvdb_id=TVDB_A) in refs, "Show A episodes must carry TVDB_A ref"
    assert MediaRef(tvdb_id=TVDB_B) in refs, "Show B episodes must carry TVDB_B ref"
    assert len(aired) == 2, f"Expected exactly 2 aired episodes, got {len(aired)}"


# ---------------------------------------------------------------------------
# Fail-soft — one series raises, others still polled
# ---------------------------------------------------------------------------


def test_poll_aired_fail_soft_one_series_raises() -> None:
    """LOAD-BEARING: ApiError on one series must NOT propagate — others still polled."""
    from datetime import date

    from personalscraper.acquire.airing import poll_aired
    from personalscraper.api._contracts import ApiError
    from personalscraper.core.identity import MediaRef

    TODAY = date(2024, 6, 15)
    TVDB_GOOD = 153021

    tv_provider = MagicMock()

    def get_tv_side_effect(tvdb_id):
        if tvdb_id == 99999:
            raise ApiError(provider="tvdb", http_status=500, message="server error")
        details = MagicMock()
        details.seasons = [_make_season(1)]
        return details

    tv_provider.get_tv.side_effect = get_tv_side_effect

    ep_fetcher = MagicMock()
    ep_fetcher.get_episodes.return_value = [_make_episode(1, 1, "2023-01-01", "Good Ep")]

    registry = _make_registry(tv_provider, ep_fetcher)
    series = [_make_series(99999, "Bad Show"), _make_series(TVDB_GOOD, "Good Show")]

    aired = poll_aired(series, registry, today=TODAY)

    assert len(aired) == 1, f"Good show must still be polled, got {len(aired)} episodes"
    assert aired[0].media_ref == MediaRef(tvdb_id=TVDB_GOOD)


# ---------------------------------------------------------------------------
# Empty chain — chain() returns [] → empty result, no crash
# ---------------------------------------------------------------------------


def test_poll_aired_empty_chain_no_crash() -> None:
    """Empty provider chain returns empty list without raising."""
    from datetime import date

    from personalscraper.acquire.airing import poll_aired

    registry = MagicMock()
    registry.chain.return_value = []

    series = [_make_series(81189, "Test Show")]
    aired = poll_aired(series, registry, today=date(2024, 6, 15))

    assert aired == []


# ---------------------------------------------------------------------------
# Season selection — excludes season 0, covers non-special seasons
# ---------------------------------------------------------------------------


def test_poll_aired_season_selection_excludes_season_zero() -> None:
    """LOAD-BEARING: get_episodes must be called for seasons 1+ and NEVER for season 0."""
    from datetime import date

    from personalscraper.acquire.airing import poll_aired

    TODAY = date(2024, 6, 15)
    TVDB_ID = 81189

    tv_provider = MagicMock()
    details = MagicMock()
    # Catalog includes season 0 (specials) and seasons 1, 2
    details.seasons = [_make_season(0), _make_season(1), _make_season(2)]
    tv_provider.get_tv.return_value = details

    ep_fetcher = MagicMock()
    ep_fetcher.get_episodes.return_value = []

    registry = _make_registry(tv_provider, ep_fetcher)
    series = [_make_series(TVDB_ID)]

    poll_aired(series, registry, today=TODAY)

    called_seasons = [c.args[1] for c in ep_fetcher.get_episodes.call_args_list]
    assert 0 not in called_seasons, f"Season 0 must be excluded but was called: {called_seasons}"
    assert 1 in called_seasons, "Season 1 must be polled"
    assert 2 in called_seasons, "Season 2 must be polled"
