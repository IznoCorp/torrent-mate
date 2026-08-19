"""The card and the completeness panel must never disagree.

Written failing-first in sub-phase 5.1: they pinned the divergence that
sub-phase 5.2 then removed — the ``poll_aired`` fallback and the local
``_episode_state`` re-derivation in ``completeness.py``, which made the card
read the five-state truth (phase 4) while the panel ran a live provider poll
through the old three-value vocabulary.

Two mechanisms keep the removal from creeping back, one per re-introduction
shape:

* ``poll_aired`` is patched at its DEFINITION site
  (``personalscraper.acquire.airing``) rather than on the completeness module,
  which no longer holds that name. A lazy re-import inside the function would
  therefore still be recorded by the mock.
* :func:`test_completeness_never_calls_a_provider` additionally asserts the
  completeness module exposes no ``poll_aired`` attribute, which catches a
  module-level re-import (a name bound before the patch applies).

Design: ``docs/features/acq-states/plan/phase-05-single-source.md`` §5.1–5.2.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, Mock, patch

import pytest

from personalscraper.acquire.domain import AiredEpisode, FollowedSeries
from personalscraper.core.identity import MediaRef
from personalscraper.web.acquisition import completeness as completeness_module
from personalscraper.web.acquisition.completeness import compute_completeness
from personalscraper.web.acquisition.states import (
    derive_episode_state,
    derive_follow_status,
)

#: Patch target: the airing poller's DEFINITION site. The web read path no
#: longer imports it, so patching the completeness module would raise.
_POLL_AIRED = "personalscraper.acquire.airing.poll_aired"

_REF = MediaRef(tvdb_id=81189)


def _follow(*, kind: str = "show") -> FollowedSeries:
    """Build an active show follow with id set."""
    return FollowedSeries(
        id=5,
        media_ref=_REF,
        title="Breaking Bad",
        added_at=1,
        kind=kind,  # type: ignore[arg-type]
    )


def _ep(season: int, episode: int, title: str = "Ep") -> AiredEpisode:
    """Build an aired episode for the follow's ref (used only by poll_aired mocks)."""
    return AiredEpisode(
        media_ref=_REF,
        season=season,
        episode=episode,
        air_date=date(2024, 1, episode),
        title=title,
    )


# ── Cached-path helpers ────────────────────────────────────────────────────


def _cached_row(season: int, episode: int) -> Mock:
    """Return a mock ``AiredEpisodeRow`` the cached path reads."""
    row = Mock()
    row.season = season
    row.episode = episode
    row.title = None
    row.air_date = "2024-01-01"
    row.updated_at = 1_750_000_000
    return row


def _wanted_row(
    season: int,
    episode: int,
    status: str,
    *,
    row_id: int,
    last_search_outcome: str | None = None,
    last_search_found: int | None = None,
) -> Mock:
    """Return a mock ``wanted`` row as the bulk read yields it."""
    row = Mock()
    row.id = row_id
    row.season = season
    row.episode = episode
    row.status = status
    row.last_search_outcome = last_search_outcome
    row.last_search_found = last_search_found
    return row


def _store_with_cache(rows: list[Mock], wanted: list[Mock] | None = None) -> MagicMock:
    """Build a store serving *rows* as the cached catalog and *wanted* as the queue."""
    store = MagicMock()
    store.aired.list_for_followed.return_value = list(rows)
    store.wanted.list_for_followed.return_value = list(wanted or [])
    return store


# ═══════════════════════════════════════════════════════════════════════════
# Test 1 — uncached follow: card vs panel agreement
# ═══════════════════════════════════════════════════════════════════════════


def test_card_and_completeness_agree_on_an_uncached_follow() -> None:
    """The card and the detail panel must never contradict each other.

    On 2026-07-27 they did: with an empty aired cache the card fell back to raw
    wanted counters and said « À jour », while compute_completeness fell back to
    a LIVE poll_aired and would have listed three episodes as missing. Same
    database, same instant, opposite answers. This test pins the agreement.
    """
    followed = _follow()

    # The card's truth (post phase-4): no catalog → all-None → unverified.
    card_status = derive_follow_status(
        active=True,
        aired_count=None,
        to_grab_count=None,
        acquiring_count=None,
        pending_count=None,
        unverified_count=None,
        announced_count=None,
        series_status=None,
    )
    assert card_status == "unverified", (
        "The card MUST read unverified when the catalog is absent — the founding incident's direct fix."
    )

    # A poller that would return 3 aired episodes — the patch records every
    # call so we can assert ZERO.
    three_episodes = [_ep(1, 1), _ep(1, 2), _ep(1, 3)]

    # Store with EMPTY cache: no detect pass has run yet.
    store = MagicMock()
    store.aired.list_for_followed.return_value = []
    store.wanted.list_for_followed.return_value = []

    ownership = MagicMock()
    ownership.owns.return_value = False

    with patch(_POLL_AIRED, return_value=three_episodes) as poll_mock:
        result = compute_completeness(followed, ownership=ownership, store=store)

    # ── Post-5.2 invariant: NO provider call from a web-read path ──────────
    # Before 5.2 this failed — the uncached path polled live.
    poll_mock.assert_not_called()

    # ── Post-5.2 invariant: no fabricated all-missing matrix ───────────────
    # Before 5.2 this failed — the live poll produced 3 "manquant" episodes.
    assert result.seasons == [], (
        "An uncached follow MUST NOT fabricate an all-missing matrix from a "
        "live poll. The honest reading is empty seasons, matching the card's "
        "unverified — both say 'we don't know yet'."
    )

    # ── Agreement: the panel must not lie about provider_catalog_empty ─────
    # provider_catalog_empty=True means « the provider KNOWS the series but
    # lists no episodes » (Top Chef case). An uncached follow at read time
    # does NOT know this — it simply has no data.
    assert result.provider_catalog_empty is False, (
        "provider_catalog_empty must be False for an uncached follow — "
        "that flag is for DETECT-confirmed empty catalogs, not for "
        "web-read-time ignorance."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Test 2 — cached facts: panel state MUST equal derive_episode_state
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "season,episode,owned,wanted_status,last_search_outcome,last_search_found,expected_5state",
    [
        # owned beats everything — the one case that agrees today.
        pytest.param(1, 1, True, None, None, None, "in_library", id="owned"),
        # grabbed → 5-state: acquiring, old: en_cours
        pytest.param(1, 2, False, "grabbed", "available", 1, "acquiring", id="grabbed"),
        # available → 5-state: to_grab, old: manquant (available is not a recognised
        # status in the old _episode_state → falls through to the default "manquant")
        pytest.param(1, 3, False, "available", "available", 3, "to_grab", id="available"),
        # pending, never searched → 5-state: unverified, old: en_file
        pytest.param(1, 4, False, "pending", None, None, "unverified", id="pending_never_searched"),
        # pending, searched, nothing takeable → 5-state: pending, old: en_file
        # (old code does not read the verdict → same en_file for both pending cases)
        pytest.param(
            1,
            5,
            False,
            "pending",
            "no_candidates",
            0,
            "pending",
            id="pending_searched_nothing",
        ),
        # no wanted row, never searched → 5-state: unverified, old: manquant
        pytest.param(1, 6, False, None, None, None, "unverified", id="no_row"),
    ],
)
def test_card_and_completeness_agree_on_cached_facts(
    season: int,
    episode: int,
    owned: bool,
    wanted_status: str | None,
    last_search_outcome: str | None,
    last_search_found: int | None,
    expected_5state: str,
) -> None:
    """Per (season, episode) the completeness state MUST equal derive_episode_state.

    The panel's ``EpisodeCompleteness.state`` must be the five-state value
    that ``states.derive_episode_state`` returns for the same ownership,
    wanted status and search verdict. Before 5.2 the panel used a local
    ``_episode_state`` with the old three-value vocabulary (``en_file`` /
    ``en_cours`` / ``manquant``), so this failed for every case but "owned".
    """
    followed = _follow()

    # One cached row for the parametrised episode, plus the queue row carrying
    # the parametrised facts (no row at all when the case has no status).
    queue = (
        []
        if wanted_status is None
        else [
            _wanted_row(
                season,
                episode,
                wanted_status,
                row_id=1,
                last_search_outcome=last_search_outcome,
                last_search_found=last_search_found,
            )
        ]
    )
    store = _store_with_cache([_cached_row(season, episode)], queue)

    ownership = MagicMock()
    ownership.owns.return_value = owned

    with patch(_POLL_AIRED) as poll_mock:
        result = compute_completeness(followed, ownership=ownership, store=store)

    # Cached path must NOT poll a provider.
    poll_mock.assert_not_called()

    assert len(result.seasons) == 1
    eps = result.seasons[0].episodes
    assert len(eps) == 1
    ep = eps[0]

    # Sanity: the expected state must match derive_episode_state.
    actual_5state = derive_episode_state(
        owned=owned,
        wanted_status=wanted_status,
        last_search_outcome=last_search_outcome,
        last_search_found=last_search_found,
    )
    assert actual_5state == expected_5state, (
        f"Sanity check: derive_episode_state({owned=}, {wanted_status=}, "
        f"{last_search_outcome=}, {last_search_found=}) = {actual_5state!r}, "
        f"expected {expected_5state!r}"
    )

    # The invariant: panel state == card's derivation for the same facts.
    assert ep.state == expected_5state, (
        f"Episode S{season:02d}E{episode:02d}: panel said {ep.state!r}, "
        f"card derivation says {expected_5state!r}. The panel MUST use "
        f"derive_episode_state as its single source."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Test 2b — WHICH row governs: the two surfaces must select the same one
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("closed_status", ["done", "abandoned"])
def test_a_closed_row_alone_reads_unverified_on_both_surfaces(closed_status: str) -> None:
    """A ``done`` / ``abandoned`` row is history — it must not answer for its episode.

    Agreeing on the derivation is not enough: the two surfaces must also read
    the SAME row. The card's ``compute_follow_truth`` only ever considered OPEN
    rows, so an episode whose sole row is closed derives from « no row » facts
    and reads ``unverified``. The panel used ``store.wanted.find``, which
    returns the first row of ANY status — so it read the closed row's concluded
    verdict and could answer ``pending`` (or ``to_grab``) where the card
    said ``unverified``. Both now go through ``select_wanted_facts``.
    """
    ownership = MagicMock()
    ownership.owns.return_value = False
    # The closed row carries a concluded verdict — precisely what must NOT leak.
    store = _store_with_cache(
        [_cached_row(1, 1)],
        [_wanted_row(1, 1, closed_status, row_id=10, last_search_outcome="no_candidates", last_search_found=0)],
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    card_state = derive_episode_state(owned=False, wanted_status=None, last_search_outcome=None, last_search_found=None)
    assert card_state == "unverified"
    assert result.seasons[0].episodes[0].state == card_state, (
        f"A lone {closed_status} row must not speak for its episode: the card reads "
        f"{card_state!r} from « no open row », so the panel must too."
    )


def test_duplicate_rows_resolve_to_the_latest_open_one_on_both_surfaces() -> None:
    """One abandoned leftover + one available row → ``to_grab`` on both surfaces.

    A re-follow leaves the closed row behind with a LOWER id. ``find`` returned
    that one (first by id, any status); the card took the latest OPEN one. Same
    episode, same instant, opposite answers — the exact divergence shape this
    phase exists to remove.
    """
    ownership = MagicMock()
    ownership.owns.return_value = False
    store = _store_with_cache(
        [_cached_row(1, 1)],
        [
            _wanted_row(1, 1, "abandoned", row_id=10, last_search_outcome="no_candidates", last_search_found=0),
            _wanted_row(1, 1, "available", row_id=11, last_search_outcome="available", last_search_found=2),
        ],
    )

    result = compute_completeness(_follow(), ownership=ownership, store=store)

    card_state = derive_episode_state(
        owned=False, wanted_status="available", last_search_outcome="available", last_search_found=2
    )
    assert card_state == "to_grab"
    assert result.seasons[0].episodes[0].state == card_state
    # And it counts as « en mouvement » in the season aggregate.
    assert result.seasons[0].queued == 1


# ═══════════════════════════════════════════════════════════════════════════
# Test 3 — no provider call from any web-read path
# ═══════════════════════════════════════════════════════════════════════════


def test_completeness_never_calls_a_provider() -> None:
    """Any input (cached, uncached, movie): the airing poller records zero calls.

    Before 5.2 the uncached path polled live. Now ALL paths are read-only from
    the cached catalog (or honest ignorance when no catalog exists); no
    web-read path ever calls a provider.
    """
    ownership = MagicMock()
    ownership.owns.return_value = False

    with patch(_POLL_AIRED) as poll_mock:
        # ── Cached show ──
        store_cached = _store_with_cache([_cached_row(1, 1)])
        store_cached.wanted.list_for_followed.return_value = []
        compute_completeness(_follow(), ownership=ownership, store=store_cached)

        # ── Movie ──
        store_movie = MagicMock()
        store_movie.wanted.list_for_followed.return_value = []
        compute_completeness(_follow(kind="movie"), ownership=ownership, store=store_movie)

        # ── Uncached show: the case that polled live before 5.2 ──
        store_uncached = MagicMock()
        store_uncached.aired.list_for_followed.return_value = []
        store_uncached.wanted.list_for_followed.return_value = []
        compute_completeness(_follow(), ownership=ownership, store=store_uncached)

    # Catches a LAZY re-import (a call resolved through the patched module).
    poll_mock.assert_not_called()

    # Catches a MODULE-LEVEL re-import: a name bound at import time would be
    # unaffected by the patch above, so the absence of the attribute is what
    # keeps the fallback from creeping back in that shape.
    assert not hasattr(completeness_module, "poll_aired"), (
        "The completeness read-model must not import the airing poller at all: "
        "a module-level binding escapes the patch above, which is exactly how "
        "the divergent live fallback could return unnoticed."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Test 4 — provider_catalog_empty is a DETECT-only signal, not web-read-time
# ═══════════════════════════════════════════════════════════════════════════


def test_provider_catalog_empty_stays_distinct() -> None:
    """A follow whose cache is empty keeps its ignorance honest.

    ``provider_catalog_empty=True`` means « the provider KNOWS the series but
    lists no episodes » (the Top Chef case — TVDB 475278). It is only
    assertable from a DETECT-written empty-after-poll state, not from
    web-read-time ignorance.

    An uncached follow at read time must NOT claim ``provider_catalog_empty=True``
    — it must surface an honest "unknown catalog" without fabricating an
    all-missing matrix. The card reads ``unverified``; the panel must agree.

    Before 5.2 the empty cache triggered a live poll: a poll returning nothing
    set ``provider_catalog_empty=True`` (wrong — a web-read-time guess, not a
    DETECT confirmation), and a poll returning episodes rendered a fabricated
    all-missing matrix (wrong — the panel claimed what was missing without
    having verified ownership).
    """
    followed = _follow()
    store = MagicMock()
    store.aired.list_for_followed.return_value = []
    store.wanted.list_for_followed.return_value = []
    ownership = MagicMock()
    ownership.owns.return_value = False

    with patch(_POLL_AIRED, return_value=[]) as poll_mock:
        result = compute_completeness(followed, ownership=ownership, store=store)

    # ── Post-5.2 invariant 1: NO live poll from a web-read path ────────────
    poll_mock.assert_not_called()

    # ── Post-5.2 invariant 2: not a fabricated claim ──────────────────────
    assert result.provider_catalog_empty is False, (
        "An uncached follow MUST NOT claim provider_catalog_empty=True — "
        "that flag is for DETECT-confirmed empty catalogs (Top Chef case), "
        "not for web-read-time ignorance."
    )

    # ── Post-5.2 invariant 3: no fabricated all-missing matrix ────────────
    assert result.seasons == [], (
        "An uncached follow MUST NOT fabricate an all-missing matrix — "
        "the honest reading is empty seasons (we don't know the catalog)."
    )

    # ── Post-5.2 invariant 4: card and panel agree ────────────────────────
    card_status = derive_follow_status(
        active=True,
        aired_count=None,
        to_grab_count=None,
        acquiring_count=None,
        pending_count=None,
        unverified_count=None,
        announced_count=None,
        series_status=None,
    )
    assert card_status == "unverified", (
        "The card reads unverified when the catalog is absent. The panel's "
        "empty seasons match this — both say 'we don't know yet'."
    )
