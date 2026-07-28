"""episode-states D2 — the ``annonce`` state and its exclusion from the card.

Core invariant of the feature: a FUTURE episode (air_date > today) is known to
the cache but is not searchable on trackers, so:

- it derives to ``annonce`` FIRST, whatever its ownership / verdict / row facts
  (a future can't be owned, searched, or waiting);
- it must NEVER degrade a series' card: a show whose AIRED episodes are all in
  the library stays « À jour » even with announced episodes ahead.
"""

from __future__ import annotations

from datetime import date

import pytest

from personalscraper.web.acquisition.states import derive_episode_state, derive_follow_status

TODAY = date(2024, 6, 15)
FUTURE = date(2025, 1, 1)
PAST = date(2023, 1, 1)


class TestAnnonceDerivation:
    """``derive_episode_state`` returns ``annonce`` first for a future air_date."""

    def test_future_air_date_is_annonce(self) -> None:
        """A future episode reads ``annonce`` — the plain case."""
        state = derive_episode_state(
            owned=False,
            wanted_status=None,
            last_search_outcome=None,
            last_search_found=None,
            air_date=FUTURE,
            today=TODAY,
        )
        assert state == "annonce"

    @pytest.mark.parametrize(
        ("owned", "wanted_status", "outcome", "found"),
        [
            (True, None, None, None),  # somehow "owned" — impossible for a future, but annonce still wins
            (False, "grabbed", None, None),  # a stray grabbed row
            (False, "available", "available", 3),  # a stray takeable verdict
            (False, None, "no_candidates", 0),  # searched, nothing
        ],
        ids=["owned", "grabbed", "available", "searched"],
    )
    def test_annonce_wins_over_every_other_fact(
        self, owned: bool, wanted_status: str | None, outcome: str | None, found: int | None
    ) -> None:
        """``annonce`` is decided FIRST — no combination of facts overrides a future date."""
        state = derive_episode_state(
            owned=owned,
            wanted_status=wanted_status,
            last_search_outcome=outcome,
            last_search_found=found,
            air_date=FUTURE,
            today=TODAY,
        )
        assert state == "annonce", "a future episode is annonce regardless of its facts"

    def test_annonce_precedes_the_no_row_non_verifie_path(self) -> None:
        """A future has no wanted row → no-row facts; annonce must win BEFORE non_verifie.

        This is the trap the coordinator called out: a future episode's facts
        are the same all-None « never searched » facts a genuinely unknown aired
        episode has. Only the date tells them apart, and the date is checked
        first.
        """
        no_row = derive_episode_state(
            owned=False,
            wanted_status=None,
            last_search_outcome=None,
            last_search_found=None,
            air_date=FUTURE,
            today=TODAY,
        )
        assert no_row == "annonce"

    def test_today_is_not_annonce(self) -> None:
        """Air-date == today is aired (inclusive), not announced."""
        state = derive_episode_state(
            owned=False,
            wanted_status=None,
            last_search_outcome=None,
            last_search_found=None,
            air_date=TODAY,
            today=TODAY,
        )
        assert state != "annonce"
        assert state == "non_verifie"  # aired, no row, unowned

    def test_past_episode_keeps_its_five_state_derivation(self) -> None:
        """An aired episode is unchanged by the new parameters."""
        owned = derive_episode_state(
            owned=True,
            wanted_status=None,
            last_search_outcome=None,
            last_search_found=None,
            air_date=PAST,
            today=TODAY,
        )
        assert owned == "en_mediatheque"

    def test_missing_air_date_falls_through_to_the_five_states(self) -> None:
        """Additive: callers passing no air_date/today get the historical behaviour."""
        assert (
            derive_episode_state(owned=True, wanted_status=None, last_search_outcome=None, last_search_found=None)
            == "en_mediatheque"
        )
        assert (
            derive_episode_state(owned=False, wanted_status="grabbed", last_search_outcome=None, last_search_found=None)
            == "en_acquisition"
        )


class TestAnnonceExcludedFromCard:
    """ACC-03 — an announced future never degrades the aggregated card status."""

    def test_all_aired_owned_stays_a_jour_with_announced_ahead(self) -> None:
        """The card counts AIRED episodes only; announced ones are simply not fed in.

        ``derive_follow_status`` aggregates the five per-state counts. A future
        episode is ``annonce`` — which has no counter — so a series whose aired
        episodes are all owned stays « À jour ». The announced count is display
        only; if it ever leaked into the aggregation, this series would read
        ``non_verifie``.
        """
        status = derive_follow_status(
            active=True,
            aired_count=8,  # 8 aired episodes...
            a_recuperer_count=0,
            en_acquisition_count=0,
            en_attente_count=0,
            non_verifie_count=0,  # ...all owned (aired_count == owned, nothing pending)
        )
        assert status == "a_jour", "announced futures must not degrade an up-to-date series"

    def test_follow_status_has_no_annonce_input(self) -> None:
        """``derive_follow_status`` takes no announced parameter — annonce is structurally out."""
        import inspect

        params = inspect.signature(derive_follow_status).parameters
        assert not any("annonc" in p or "announced" in p for p in params), (
            "the card aggregation must not accept an announced count"
        )
