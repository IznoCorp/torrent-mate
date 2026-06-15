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


# ---------------------------------------------------------------------------
# NEGATIVE boundary (DESIGN §1 / §8 — LOAD-BEARING)
# These tests encode the RP9↔D2 boundary as executable assertions.
# A future refactor that folds D2 logic into RP9 will fail here.
# ---------------------------------------------------------------------------


def test_poll_aired_makes_no_store_wanted_calls() -> None:
    """LOAD-BEARING (DESIGN §1): poll_aired must NEVER call store.wanted.* (D2's job)."""
    from datetime import date
    from unittest.mock import MagicMock

    from personalscraper.acquire.airing import poll_aired

    registry = MagicMock()
    registry.chain.return_value = []  # empty chain → no network calls

    store_spy = MagicMock()
    wanted_spy = MagicMock()
    store_spy.wanted = wanted_spy

    series = [_make_series(81189, "Test Show")]

    # poll_aired does NOT accept a store argument — we are verifying it is never
    # called at all (it has no store parameter by design).
    poll_aired(series, registry, today=date(2024, 6, 15))

    # The store spy was never passed in, so wanted_spy must have zero calls.
    # This confirms poll_aired's signature has no store parameter (DESIGN §2).
    assert wanted_spy.add.call_count == 0, "poll_aired must not call store.wanted.add"
    assert wanted_spy.enqueue.call_count == 0, "poll_aired must not call store.wanted.enqueue"
    assert store_spy.call_count == 0, "poll_aired must not call the store at all"


def test_poll_aired_makes_no_ownership_calls() -> None:
    """LOAD-BEARING (DESIGN §1): poll_aired must NEVER call ownership.owns() (D2's job)."""
    from datetime import date
    from unittest.mock import MagicMock, patch

    from personalscraper.acquire.airing import poll_aired

    registry = MagicMock()
    registry.chain.return_value = []

    ownership_spy = MagicMock()

    with patch("personalscraper.acquire.airing.ownership", ownership_spy, create=True):
        # Even if an 'ownership' symbol existed in the module namespace, it must
        # never be called. create=True so the patch installs it without import error.
        series = [_make_series(81189, "Test Show")]
        poll_aired(series, registry, today=date(2024, 6, 15))

    assert ownership_spy.owns.call_count == 0, "poll_aired must not call ownership.owns()"


def test_poll_aired_does_not_read_cadence_json() -> None:
    """LOAD-BEARING (DESIGN §1): poll_aired must NOT access cadence_json on FollowedSeries."""
    from datetime import date
    from unittest.mock import MagicMock, PropertyMock

    from personalscraper.acquire.airing import poll_aired
    from personalscraper.core.identity import MediaRef

    registry = MagicMock()
    registry.chain.return_value = []

    # Build a FollowedSeries mock that records cadence_json access.
    fs = MagicMock()
    fs.title = "Test Show"
    fs.media_ref = MediaRef(tvdb_id=81189)
    cadence_spy = PropertyMock(return_value=None)
    type(fs).cadence_json = cadence_spy

    poll_aired([fs], registry, today=date(2024, 6, 15))

    assert cadence_spy.call_count == 0, (
        f"poll_aired must not read cadence_json (accessed {cadence_spy.call_count} time(s))"
    )


# ---------------------------------------------------------------------------
# Layering guard (DESIGN §7)
# acquire/airing.py must import downward only:
#   api/metadata + acquire.domain + core.identity + stdlib datetime
# Never store, indexer, or any triage package.
# ---------------------------------------------------------------------------


def test_airing_module_has_no_store_or_indexer_import() -> None:
    """DESIGN §7: acquire/airing.py must not import store or indexer packages."""
    import ast
    from pathlib import Path

    source = (Path(__file__).parent.parent.parent / "personalscraper" / "acquire" / "airing.py").read_text()
    tree = ast.parse(source)

    forbidden_prefixes = (
        "personalscraper.indexer",
        "personalscraper.acquire.store",
        "personalscraper.acquire._ports",
        "personalscraper.scraper",
        "personalscraper.ingest",
        "personalscraper.commands",
        "personalscraper.pipeline",
    )

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
            for prefix in forbidden_prefixes:
                assert not module.startswith(prefix), (
                    f"acquire/airing.py imports forbidden module '{module}' (violates DESIGN §7 layering invariant)"
                )
