"""Unit tests for the §5 completeness read-model (compute_completeness).

Pure-computation tests over mocked sources: the detect-written aired-catalog
cache, library ownership, and the wanted queue. Guards the §5 contract in the
five-state vocabulary of ``web/acquisition/states.py`` — ``in_library`` /
``acquiring`` / ``to_grab`` / ``pending`` / ``unverified`` — and
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
    row_id: int | None = None,
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
        id=row_id if row_id is not None else 100 + episode,
        last_search_outcome=last_search_outcome,
        last_search_found=last_search_found,
    )


def _store(rows: list[AiredEpisodeRow], wanted: list[WantedItem] | None = None) -> MagicMock:
    """Build a store serving *rows* as the cached catalog and *wanted* as the queue."""
    store = MagicMock()
    store.aired.list_for_followed.return_value = list(rows)
    store.wanted.list_for_followed.return_value = list(wanted or [])
    return store


def test_states_matrix_over_the_five_states() -> None:
    """§5 guard: each aired episode reads its true five-state value, grouped by season."""
    ownership = MagicMock()
    # E1 owned; E2/E3/E4/E5 not owned.
    ownership.owns.side_effect = lambda ref, *, kind, season, episode: episode == 1
    store = _store(
        [_cached(1, 1), _cached(1, 2), _cached(1, 3), _cached(1, 4), _cached(1, 5)],
        [
            # Taken by the pipeline.
            _wanted(1, 2, "grabbed", last_search_outcome="available", last_search_found=1),
            # A takeable candidate is known but not claimed yet.
            _wanted(1, 3, "available", last_search_outcome="available", last_search_found=2),
            # Searched, concluded, nothing takeable.
            _wanted(1, 4, "pending", last_search_outcome="no_candidates", last_search_found=0),
            # Enqueued but never searched — we know nothing.
            _wanted(1, 5, "pending"),
        ],
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert result.provider_catalog_empty is False
    assert result.source == "cache"
    assert len(result.seasons) == 1
    season = result.seasons[0]
    # ``queued`` counts the two « in motion » states: to_grab + acquiring.
    assert (season.season, season.total, season.owned, season.queued) == (1, 5, 1, 2)
    states = {e.episode: e.state for e in season.episodes}
    assert states == {
        1: "in_library",
        2: "acquiring",
        3: "to_grab",
        4: "pending",
        5: "unverified",
    }


def test_absorbed_episode_reads_absorbed_and_counts_in_motion() -> None:
    """Review F7: an absorbed episode chips « Absorbé », never « Non vérifié ».

    Season-grab R5 absorbs the live episode rows into a season wanted. The
    open-statuses-only selection silenced them → NO_WANTED_FACTS →
    ``unverified`` (« never checked ») for every episode of a season being
    grabbed. The absorbed row must speak, and the season header must count the
    episode as in motion (``queued``).
    """
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store(
        [_cached(2, 1), _cached(2, 2)],
        [
            _wanted(2, 1, "absorbed"),
            _wanted(2, 2, "absorbed", last_search_outcome="no_candidates", last_search_found=0),
        ],
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    season = result.seasons[0]
    assert {e.episode: e.state for e in season.episodes} == {1: "absorbed", 2: "absorbed"}
    assert season.queued == 2  # absorbed = in motion, the header stays honest


def test_newer_live_row_outranks_the_old_absorbed_one_in_the_matrix() -> None:
    """Review F7 (R6 ordering): after a fallback, the fresh live row governs."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store(
        [_cached(3, 1)],
        [
            _wanted(3, 1, "absorbed", row_id=10),
            _wanted(3, 1, "pending", row_id=11, last_search_outcome="available", last_search_found=2),
        ],
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert result.seasons[0].episodes[0].state == "to_grab"


def test_ownership_beats_a_stale_grabbed_row() -> None:
    """A grabbed row on an owned episode is a phantom (the Silo bug), not an acquisition."""
    ownership = MagicMock()
    ownership.owns.return_value = True
    store = _store([_cached(1, 1)], [_wanted(1, 1, "grabbed", last_search_outcome="available", last_search_found=1)])

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert [e.state for e in result.seasons[0].episodes] == ["in_library"]
    assert (result.seasons[0].owned, result.seasons[0].queued) == (1, 0)


def test_an_inconclusive_search_reads_unverified() -> None:
    """Panne ≠ absence: a tracker outage must never read « rien à prendre »."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store([_cached(1, 1)], [_wanted(1, 1, "pending", last_search_outcome="trackers_unavailable")])

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert [e.state for e in result.seasons[0].episodes] == ["unverified"]
    # « Non vérifié » is not « en mouvement » — it must not inflate the queued count.
    assert result.seasons[0].queued == 0


def test_a_closed_row_never_speaks_for_its_episode() -> None:
    """A ``done`` row's concluded verdict is history — the episode reads « never searched »."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store(
        [_cached(1, 1)],
        [_wanted(1, 1, "done", last_search_outcome="no_candidates", last_search_found=0)],
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert [e.state for e in result.seasons[0].episodes] == ["unverified"]


def test_the_latest_open_row_governs_over_an_older_leftover() -> None:
    """Two open rows for one episode: the highest id is the current intent."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store(
        [_cached(1, 1)],
        [
            _wanted(1, 1, "pending", row_id=10, last_search_outcome="no_candidates", last_search_found=0),
            _wanted(1, 1, "grabbed", row_id=11),
        ],
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert [e.state for e in result.seasons[0].episodes] == ["acquiring"]


def test_rows_of_another_episode_never_leak() -> None:
    """The bulk read is indexed per (season, episode) — no cross-episode contamination."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store([_cached(1, 1), _cached(1, 2)], [_wanted(1, 2, "grabbed")])

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    states = {e.episode: e.state for e in result.seasons[0].episodes}
    assert states == {1: "unverified", 2: "acquiring"}


def test_an_uncached_follow_is_honest_ignorance() -> None:
    """No cached catalog → empty seasons + source="unknown", never a fabricated matrix.

    Replaces the pre-phase-5 ``provider_catalog_empty`` reading of this case: it
    used to run a live poll and, when the poll came back empty, claim the
    provider listed no episode (the Top Chef case). A web read cannot establish
    that — it can only say « we have no catalog yet ». The card reads
    ``unverified`` from the same absence, so the two surfaces agree.
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
    store.wanted.list_for_followed.side_effect = RuntimeError("database is locked")

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    assert [e.state for e in result.seasons[0].episodes] == ["unverified"]


def test_waiting_episode_exposes_the_verdict_it_was_derived_from() -> None:
    """An ``pending`` episode carries its outcome so the UI can say WHY (phase 8)."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store(
        [_cached(1, 1), _cached(1, 2)],
        [
            _wanted(1, 1, "pending", last_search_outcome="all_filtered", last_search_found=0),
            _wanted(1, 2, "pending", last_search_outcome="no_matching_episode", last_search_found=0),
        ],
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    episodes = {e.episode: e for e in result.seasons[0].episodes}
    assert episodes[1].state == "pending"
    assert episodes[1].last_search_outcome == "all_filtered"
    assert episodes[2].last_search_outcome == "no_matching_episode"


def test_exposed_outcome_comes_from_the_governing_row() -> None:
    """The exposed verdict is the governing row's — never a closed row's stale one."""
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store(
        [_cached(1, 1)],
        [
            # Closed row: history, and its verdict must not answer for the episode.
            _wanted(1, 1, "done", row_id=10, last_search_outcome="all_filtered", last_search_found=0),
            # Open row, higher id: the current intent, never searched.
            _wanted(1, 1, "pending", row_id=11),
        ],
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    episode = result.seasons[0].episodes[0]
    assert episode.state == "unverified"
    assert episode.last_search_outcome is None


# ---------------------------------------------------------------------------
# episode-states D2 — the matrix shows futures as ``annonce`` + counts them apart
# ---------------------------------------------------------------------------


def _cached_dated(season: int, episode: int, air_date: str) -> AiredEpisodeRow:
    """Build a cached row with an explicit ``air_date``."""
    return AiredEpisodeRow(followed_id=5, season=season, episode=episode, title="Ep", air_date=air_date, updated_at=1)


def test_matrix_shows_future_as_announced_kept_out_of_aired_tallies() -> None:
    """A future cached episode reads ``annonce`` and is counted in ``announced`` only.

    Owned/queued/total stay AIRED-only; ``annonce`` is a display state and its
    count lives in the separate ``announced`` field — never inflating the
    season's completeness denominator.
    """
    from datetime import date

    ownership = MagicMock()
    ownership.owns.side_effect = lambda ref, *, kind, season, episode: (season, episode) == (1, 1)
    store = _store([_cached_dated(1, 1, "2024-06-01"), _cached_dated(1, 2, "2025-01-01")])

    result = compute_completeness(_follow(), ownership=ownership, store=store, today=date(2024, 6, 15))

    season = result.seasons[0]
    states = {e.episode: e.state for e in season.episodes}
    assert states == {1: "in_library", 2: "announced"}, "the future episode reads announced"
    assert season.total == 1, "total counts AIRED only"
    assert season.owned == 1
    assert season.announced == 1, "the future is counted apart, in announced"
    # The announced episode still exposes its air_date for the click-to-see-date UI.
    assert next(e.air_date for e in season.episodes if e.episode == 2) == "2025-01-01"
