"""Failing-first tests: the card and the completeness panel must never disagree.

These tests intentionally FAIL until sub-phase 5.2 removes the divergent
``poll_aired`` fallback and the local ``_episode_state`` re-derivation from
``completeness.py``. The failures prove the divergence exists today: the card
reads the five-state truth (phase 4) while the completeness panel still uses
a live provider poll and the old three-value vocabulary.

Design: ``docs/features/acq-states/plan/phase-05-single-source.md`` §5.1.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, Mock, patch

import pytest

from personalscraper.acquire.domain import AiredEpisode, FollowedSeries
from personalscraper.core.identity import MediaRef
from personalscraper.web.acquisition.completeness import compute_completeness
from personalscraper.web.acquisition.states import (
    derive_episode_state,
    derive_follow_status,
)

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


def _store_with_cache(rows: list[Mock]) -> MagicMock:
    """Build a store whose ``aired.list_for_followed`` returns *rows* (the cached path)."""
    store = MagicMock()
    store.aired.list_for_followed.return_value = list(rows)
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

    # The card's truth (post phase-4): no catalog → all-None → non_verifie.
    card_status = derive_follow_status(
        active=True,
        aired_count=None,
        a_recuperer_count=None,
        en_acquisition_count=None,
        en_attente_count=None,
        non_verifie_count=None,
    )
    assert card_status == "non_verifie", (
        "The card MUST read non_verifie when the catalog is absent — the founding incident's direct fix."
    )

    # A registry whose poll_aired would return 3 aired episodes — the
    # patch records every call so we can assert ZERO after 5.2.
    registry = MagicMock()
    three_episodes = [_ep(1, 1), _ep(1, 2), _ep(1, 3)]

    # Store with EMPTY cache: no detect pass has run yet.
    store = MagicMock()
    store.aired.list_for_followed.return_value = []
    store.wanted.find.return_value = None

    ownership = MagicMock()
    ownership.owns.return_value = False

    with patch(
        "personalscraper.web.acquisition.completeness.poll_aired",
        return_value=three_episodes,
    ) as poll_mock:
        result = compute_completeness(
            followed,
            registry=registry,
            ownership=ownership,
            store=store,
        )

    # ── Post-5.2 invariant: NO provider call from a web-read path ──────────
    # TODAY this FAILS — the uncached path calls poll_aired live.
    poll_mock.assert_not_called()

    # ── Post-5.2 invariant: no fabricated all-missing matrix ───────────────
    # TODAY this FAILS — the live poll produces 3 episodes all "manquant".
    assert result.seasons == [], (
        "An uncached follow MUST NOT fabricate an all-missing matrix from a "
        "live poll. The honest reading is empty seasons, matching the card's "
        "non_verifie — both say 'we don't know yet'."
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
        pytest.param(1, 1, True, None, None, None, "en_mediatheque", id="owned"),
        # grabbed → 5-state: en_acquisition, old: en_cours
        pytest.param(1, 2, False, "grabbed", "available", 1, "en_acquisition", id="grabbed"),
        # available → 5-state: a_recuperer, old: manquant (available is not a recognised
        # status in the old _episode_state → falls through to the default "manquant")
        pytest.param(1, 3, False, "available", "available", 3, "a_recuperer", id="available"),
        # pending, never searched → 5-state: non_verifie, old: en_file
        pytest.param(1, 4, False, "pending", None, None, "non_verifie", id="pending_never_searched"),
        # pending, searched, nothing takeable → 5-state: en_attente, old: en_file
        # (old code does not read the verdict → same en_file for both pending cases)
        pytest.param(
            1,
            5,
            False,
            "pending",
            "no_candidates",
            0,
            "en_attente",
            id="pending_searched_nothing",
        ),
        # no wanted row, never searched → 5-state: non_verifie, old: manquant
        pytest.param(1, 6, False, None, None, None, "non_verifie", id="no_row"),
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
    wanted status and search verdict. Today the panel uses a local
    ``_episode_state`` with the old three-value vocabulary (``en_file`` /
    ``en_cours`` / ``manquant``) — this test FAILS until 5.2 replaces it
    with the single derivation.
    """
    followed = _follow()

    # One cached row for the parametrised episode.
    store = _store_with_cache([_cached_row(season, episode)])

    # Wanted lookup: the store returns a row carrying the parametrised facts.
    if wanted_status is not None:
        wanted_row = Mock()
        wanted_row.status = wanted_status
        wanted_row.last_search_outcome = last_search_outcome
        wanted_row.last_search_found = last_search_found
        store.wanted.find.return_value = wanted_row
    else:
        store.wanted.find.return_value = None

    ownership = MagicMock()
    ownership.owns.return_value = owned

    with patch("personalscraper.web.acquisition.completeness.poll_aired") as poll_mock:
        result = compute_completeness(
            followed,
            registry=MagicMock(),
            ownership=ownership,
            store=store,
        )

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
    # TODAY this FAILS for every case except "owned" — the panel still uses
    # the old 3-value _episode_state (en_file / en_cours / manquant).
    assert ep.state == expected_5state, (
        f"Episode S{season:02d}E{episode:02d}: panel said {ep.state!r}, "
        f"card derivation says {expected_5state!r}. The panel MUST use "
        f"derive_episode_state as its single source."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Test 3 — no provider call from any web-read path
# ═══════════════════════════════════════════════════════════════════════════


def test_completeness_never_calls_a_provider() -> None:
    """Any input (cached, uncached, movie): the registry records zero calls.

    TODAY the uncached path calls ``poll_aired`` live — this test FAILS.
    After 5.2 ALL paths are read-only from the cached catalog (or honest
    ``non_verifie`` when no catalog exists); no web-read path ever calls
    a provider.
    """
    ownership = MagicMock()
    ownership.owns.return_value = False

    with patch("personalscraper.web.acquisition.completeness.poll_aired") as poll_mock:
        # ── Cached show: already does not poll today ──
        store_cached = _store_with_cache([_cached_row(1, 1)])
        store_cached.wanted.find.return_value = None
        compute_completeness(
            _follow(),
            registry=MagicMock(),
            ownership=ownership,
            store=store_cached,
        )

        # ── Movie: already does not poll today ──
        store_movie = MagicMock()
        store_movie.wanted.find.return_value = None
        compute_completeness(
            _follow(kind="movie"),
            registry=MagicMock(),
            ownership=ownership,
            store=store_movie,
        )

        # ── Uncached show: TODAY calls poll_aired live ──
        store_uncached = MagicMock()
        store_uncached.aired.list_for_followed.return_value = []
        store_uncached.wanted.find.return_value = None
        compute_completeness(
            _follow(),
            registry=MagicMock(),
            ownership=ownership,
            store=store_uncached,
        )

    # TODAY this FAILS — the third case above called poll_aired.
    poll_mock.assert_not_called()


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
    all-missing matrix. The card reads ``non_verifie``; the panel must agree.

    TODAY the empty cache triggers a live poll: if the poll returns nothing,
    ``provider_catalog_empty=True`` is set (wrong — that's a web-read-time
    guess, not a DETECT confirmation). If the poll returns episodes, a
    fabricated all-missing matrix is rendered (wrong — the panel lies about
    what is missing when it has not verified ownership).
    """
    followed = _follow()
    store = MagicMock()
    store.aired.list_for_followed.return_value = []
    store.wanted.find.return_value = None
    ownership = MagicMock()
    ownership.owns.return_value = False

    with patch(
        "personalscraper.web.acquisition.completeness.poll_aired",
        return_value=[],  # poll returns nothing → provider_catalog_empty=True TODAY
    ) as poll_mock:
        result = compute_completeness(
            followed,
            registry=MagicMock(),
            ownership=ownership,
            store=store,
        )

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
        a_recuperer_count=None,
        en_acquisition_count=None,
        en_attente_count=None,
        non_verifie_count=None,
    )
    assert card_status == "non_verifie", (
        "The card reads non_verifie when the catalog is absent. The panel's "
        "empty seasons match this — both say 'we don't know yet'."
    )
