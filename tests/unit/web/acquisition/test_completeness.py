"""Unit tests for the §5 completeness read-model (compute_completeness).

Pure-computation tests over mocked sources: provider catalog (poll_aired),
library ownership, and the wanted queue. Guards the §5 contract: aired vs
en_mediatheque vs en_file / en_cours vs manquant — and the honest
``provider_catalog_empty`` state (the Top Chef case) instead of a misleading
all-missing matrix.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from personalscraper.acquire.domain import AiredEpisode, FollowedSeries, WantedItem
from personalscraper.core.identity import MediaRef
from personalscraper.web.acquisition.completeness import compute_completeness

_REF = MediaRef(tvdb_id=81189)


def _follow(kind: str = "show") -> FollowedSeries:
    """Build an active follow with id set."""
    return FollowedSeries(id=5, media_ref=_REF, title="Breaking Bad", added_at=1, kind=kind)  # type: ignore[arg-type]


def _ep(season: int, episode: int, title: str = "Ep") -> AiredEpisode:
    """Build an aired episode for the follow's ref."""
    return AiredEpisode(media_ref=_REF, season=season, episode=episode, air_date=date(2024, 1, episode), title=title)


def _wanted(season: int, episode: int, status: str) -> WantedItem:
    """Build a wanted row for (season, episode) with the given status."""
    return WantedItem(
        media_ref=_REF,
        kind="episode",
        status=status,  # type: ignore[arg-type]
        enqueued_at=1,
        followed_id=5,
        season=season,
        episode=episode,
        id=100 + episode,
    )


def test_states_matrix_owned_queued_in_progress_missing() -> None:
    """§5 guard: each aired episode reads its true state, grouped by season."""
    ownership = MagicMock()
    # E1 owned; E2/E3/E4 not owned.
    ownership.owns.side_effect = lambda ref, *, kind, season, episode: episode == 1
    store = MagicMock()
    wanted_by_ep = {2: _wanted(1, 2, "pending"), 3: _wanted(1, 3, "grabbed")}
    store.wanted.find.side_effect = lambda *, followed_id, kind, season, episode: wanted_by_ep.get(episode)

    with patch(
        "personalscraper.web.acquisition.completeness.poll_aired",
        return_value=[_ep(1, 1), _ep(1, 2), _ep(1, 3), _ep(1, 4)],
    ):
        result = compute_completeness(_follow(), registry=MagicMock(), ownership=ownership, store=store)

    assert result.provider_catalog_empty is False
    assert len(result.seasons) == 1
    season = result.seasons[0]
    assert (season.season, season.total, season.owned, season.queued) == (1, 4, 1, 2)
    states = {e.episode: e.state for e in season.episodes}
    assert states == {1: "en_mediatheque", 2: "en_file", 3: "en_cours", 4: "manquant"}


def test_empty_provider_catalog_is_an_explicit_state() -> None:
    """The Top Chef case: zero aired episodes → provider_catalog_empty, no fake matrix."""
    with patch("personalscraper.web.acquisition.completeness.poll_aired", return_value=[]):
        result = compute_completeness(_follow(), registry=MagicMock(), ownership=MagicMock(), store=MagicMock())

    assert result.provider_catalog_empty is True
    assert result.seasons == []


def test_movie_follow_has_no_seasons() -> None:
    """A movie follow returns an empty matrix — its lifecycle lives on the card."""
    with patch("personalscraper.web.acquisition.completeness.poll_aired") as poll:
        result = compute_completeness(
            _follow(kind="movie"), registry=MagicMock(), ownership=MagicMock(), store=MagicMock()
        )

    poll.assert_not_called()
    assert result.kind == "movie"
    assert result.seasons == []


def test_seasons_are_newest_first() -> None:
    """Season ordering: the operator's eye goes to the current season."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = MagicMock()
    store.wanted.find.return_value = None
    with patch(
        "personalscraper.web.acquisition.completeness.poll_aired",
        return_value=[_ep(1, 1), _ep(2, 1)],
    ):
        result = compute_completeness(_follow(), registry=MagicMock(), ownership=ownership, store=store)

    assert [s.season for s in result.seasons] == [2, 1]
