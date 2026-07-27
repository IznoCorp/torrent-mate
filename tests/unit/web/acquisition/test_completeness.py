"""Unit tests for the §5 completeness read-model (compute_completeness).

Pure-computation tests over mocked sources: the detect-written aired-catalog
cache, library ownership, and the wanted queue. Guards the §5 contract in the
five-state vocabulary of ``web/acquisition/states.py`` — ``en_mediatheque`` /
``en_acquisition`` / ``a_recuperer`` / ``en_attente`` / ``non_verifie`` — and
the honest "unknown catalog" reading (empty seasons, ``source="unknown"``)
instead of a misleading all-missing matrix.

Since acq-states phase 5 the cache is the ONLY catalog source: no provider is
ever polled from this read path, so there is nothing to patch here — a live
poll would be a missing method on the mocked store, not a silent network call.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.acquire.domain import AiredEpisodeRow, FollowedSeries, WantedItem
from personalscraper.core.identity import MediaRef
from personalscraper.web.acquisition.completeness import compute_completeness

_REF = MediaRef(tvdb_id=81189)


def _follow(kind: str = "show") -> FollowedSeries:
    """Build an active follow with id set."""
    return FollowedSeries(id=5, media_ref=_REF, title="Breaking Bad", added_at=1, kind=kind)  # type: ignore[arg-type]


def _cached(season: int, episode: int, *, title: str | None = "Ep", updated_at: int = 1_750_000_000) -> AiredEpisodeRow:
    """Build one cached aired-catalog row for the follow."""
    return AiredEpisodeRow(
        followed_id=5,
        season=season,
        episode=episode,
        title=title,
        air_date=f"2024-01-{episode:02d}",
        updated_at=updated_at,
    )


def _wanted(
    season: int,
    episode: int,
    status: str,
    *,
    last_search_outcome: str | None = None,
    last_search_found: int | None = None,
) -> WantedItem:
    """Build a wanted row for (season, episode) with the given status + verdict."""
    return WantedItem(
        media_ref=_REF,
        kind="episode",
        status=status,  # type: ignore[arg-type]
        enqueued_at=1,
        followed_id=5,
        season=season,
        episode=episode,
        id=100 + episode,
        last_search_outcome=last_search_outcome,
        last_search_found=last_search_found,
    )


def _store(rows: list[AiredEpisodeRow], wanted_by_ep: dict[int, WantedItem] | None = None) -> MagicMock:
    """Build a store serving *rows* as the cached catalog and *wanted_by_ep* as the queue."""
    store = MagicMock()
    store.aired.list_for_followed.return_value = list(rows)
    by_ep = wanted_by_ep or {}
    store.wanted.find.side_effect = lambda *, followed_id, kind, season, episode: by_ep.get(episode)
    return store


def test_states_matrix_over_the_five_states() -> None:
    """§5 guard: each aired episode reads its true five-state value, grouped by season."""
    ownership = MagicMock()
    # E1 owned; E2/E3/E4/E5 not owned.
    ownership.owns.side_effect = lambda ref, *, kind, season, episode: episode == 1
    store = _store(
        [_cached(1, 1), _cached(1, 2), _cached(1, 3), _cached(1, 4), _cached(1, 5)],
        {
            # Taken by the pipeline.
            2: _wanted(1, 2, "grabbed", last_search_outcome="available", last_search_found=1),
            # A takeable candidate is known but not claimed yet.
            3: _wanted(1, 3, "available", last_search_outcome="available", last_search_found=2),
            # Searched, concluded, nothing takeable.
            4: _wanted(1, 4, "pending", last_search_outcome="no_candidates", last_search_found=0),
            # Enqueued but never searched — we know nothing.
            5: _wanted(1, 5, "pending"),
        },
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert result.provider_catalog_empty is False
    assert result.source == "cache"
    assert len(result.seasons) == 1
    season = result.seasons[0]
    # ``queued`` counts the two « in motion » states: a_recuperer + en_acquisition.
    assert (season.season, season.total, season.owned, season.queued) == (1, 5, 1, 2)
    states = {e.episode: e.state for e in season.episodes}
    assert states == {
        1: "en_mediatheque",
        2: "en_acquisition",
        3: "a_recuperer",
        4: "en_attente",
        5: "non_verifie",
    }


def test_ownership_beats_a_stale_grabbed_row() -> None:
    """A grabbed row on an owned episode is a phantom (the Silo bug), not an acquisition."""
    ownership = MagicMock()
    ownership.owns.return_value = True
    store = _store([_cached(1, 1)], {1: _wanted(1, 1, "grabbed", last_search_outcome="available", last_search_found=1)})

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert [e.state for e in result.seasons[0].episodes] == ["en_mediatheque"]
    assert (result.seasons[0].owned, result.seasons[0].queued) == (1, 0)


def test_an_inconclusive_search_reads_non_verifie() -> None:
    """Panne ≠ absence: a tracker outage must never read « rien à prendre »."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store([_cached(1, 1)], {1: _wanted(1, 1, "pending", last_search_outcome="trackers_unavailable")})

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert [e.state for e in result.seasons[0].episodes] == ["non_verifie"]
    # « Non vérifié » is not « en mouvement » — it must not inflate the queued count.
    assert result.seasons[0].queued == 0


def test_an_uncached_follow_is_honest_ignorance() -> None:
    """No cached catalog → empty seasons + source="unknown", never a fabricated matrix.

    Replaces the pre-phase-5 ``provider_catalog_empty`` reading of this case: it
    used to run a live poll and, when the poll came back empty, claim the
    provider listed no episode (the Top Chef case). A web read cannot establish
    that — it can only say « we have no catalog yet ». The card reads
    ``non_verifie`` from the same absence, so the two surfaces agree.
    """
    ownership = MagicMock()
    ownership.owns.return_value = False

    result = compute_completeness(_follow(), ownership=ownership, store=_store([]))

    assert result.seasons == []
    assert result.source == "unknown"
    assert result.provider_catalog_empty is False
    assert result.catalog_refreshed_at is None


def test_a_broken_cache_read_degrades_to_unknown() -> None:
    """A cache read error is ignorance, not a 500 and not an all-missing matrix."""
    store = MagicMock()
    store.aired.list_for_followed.side_effect = RuntimeError("database is locked")

    result = compute_completeness(_follow(), ownership=MagicMock(), store=store)

    assert result.seasons == []
    assert result.source == "unknown"
    assert result.provider_catalog_empty is False


def test_movie_follow_has_no_seasons() -> None:
    """A movie follow returns an empty matrix — its lifecycle lives on the card."""
    store = MagicMock()

    result = compute_completeness(_follow(kind="movie"), ownership=MagicMock(), store=store)

    store.aired.list_for_followed.assert_not_called()
    assert result.kind == "movie"
    assert result.seasons == []
    assert result.source == "unknown"


def test_seasons_are_newest_first() -> None:
    """Season ordering: the operator's eye goes to the current season."""
    ownership = MagicMock()
    ownership.owns.return_value = False

    result = compute_completeness(_follow(), ownership=ownership, store=_store([_cached(1, 1), _cached(2, 1)]))

    assert [s.season for s in result.seasons] == [2, 1]


def test_duplicate_cached_rows_never_double_an_episode() -> None:
    """A duplicated cache row must not appear twice in the matrix (B.1)."""
    ownership = MagicMock()
    ownership.owns.return_value = False

    result = compute_completeness(_follow(), ownership=ownership, store=_store([_cached(1, 1), _cached(1, 1)]))

    assert result.seasons[0].total == 1
    assert len(result.seasons[0].episodes) == 1


def test_catalog_refreshed_at_is_the_latest_cached_write() -> None:
    """The caption « catalogue du JJ/MM » reads the most recent detect pass."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store([_cached(1, 1, updated_at=1_700_000_000), _cached(1, 2, updated_at=1_750_000_000)])

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert result.catalog_refreshed_at == 1_750_000_000.0
    assert result.source == "cache"


def test_an_unreadable_wanted_row_degrades_to_never_searched() -> None:
    """A queue read error must read « non vérifié », never « rien à prendre »."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = MagicMock()
    store.aired.list_for_followed.return_value = [_cached(1, 1)]
    store.wanted.find.side_effect = RuntimeError("database is locked")

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert [e.state for e in result.seasons[0].episodes] == ["non_verifie"]
