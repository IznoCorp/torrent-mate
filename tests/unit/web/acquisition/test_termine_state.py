"""« À jour » vs « Terminé » — the operator's 2026-08-09 split.

One status was covering two situations the operator needs to tell apart:

- **À jour** — every aired episode is in the library, but the series continues;
- **Terminé** — every aired episode is in the library AND nothing more will come.

The operator stated the second as « il n'y a plus d'épisodes annoncés avec une
diffusion à venir ». Taken alone that rule is not true: an empty announcement
list is not the end of a series, it is usually a provider that has not published
the next dates yet. The measurement that settles it is in
:class:`TestAbsenceOfAnnouncementIsNotAnEnding` — real production data, the day
the operator asked.

So « Terminé » requires a POSITIVE end-of-series fact from the provider, which
detect already fetches and used to discard.
"""

from __future__ import annotations

import pytest

from personalscraper.web.acquisition.states import (
    SERIES_ENDED_STATUSES,
    derive_follow_status,
    series_has_ended,
)


def caught_up(**overrides: object) -> str:
    """Derive the status of a series whose aired episodes are ALL owned.

    Args:
        **overrides: Fields to override on the caught-up baseline.

    Returns:
        The derived :data:`~personalscraper.web.acquisition.states.FollowStatus`.
    """
    facts: dict[str, object] = {
        "active": True,
        "aired_count": 12,
        "a_recuperer_count": 0,
        "en_acquisition_count": 0,
        "en_attente_count": 0,
        "non_verifie_count": 0,
        "announced_count": 0,
        "series_status": None,
    }
    facts.update(overrides)
    return derive_follow_status(**facts)  # type: ignore[arg-type]


class TestSeriesHasEnded:
    """What counts as a provider saying « this series is over »."""

    @pytest.mark.parametrize("raw", ["Ended", "ended", " ENDED ", "Canceled", "Cancelled"])
    def test_terminal_provider_statuses(self, raw: str) -> None:
        """TVDB and TMDB spell the end differently; both are read, case-folded."""
        assert series_has_ended(raw) is True

    @pytest.mark.parametrize("raw", ["Continuing", "Returning Series", "In Production", "Upcoming", ""])
    def test_running_provider_statuses(self, raw: str) -> None:
        """Anything that is not terminal leaves the series running."""
        assert series_has_ended(raw) is False

    def test_no_status_is_ignorance_not_an_ending(self) -> None:
        """``None`` means « never polled » — never « finished ».

        A follow written before migration 023, or one whose provider names no
        status, must not be declared over. Silence is not a verdict (§14).
        """
        assert series_has_ended(None) is False

    def test_terminal_set_is_case_folded_already(self) -> None:
        """The constant holds folded values, so the comparison cannot drift."""
        assert all(v == v.casefold() for v in SERIES_ENDED_STATUSES)


class TestCaughtUpSplitsInTwo:
    """A caught-up series reads « Terminé » only when BOTH facts agree."""

    def test_ended_and_nothing_announced_is_termine(self) -> None:
        """The series is over and the library holds all of it."""
        assert caught_up(series_status="Ended", announced_count=0) == "termine"

    def test_still_running_stays_a_jour(self) -> None:
        """Caught up on a running series is « À jour », not « Terminé »."""
        assert caught_up(series_status="Continuing", announced_count=0) == "a_jour"

    def test_ended_but_a_final_episode_still_ahead_stays_a_jour(self) -> None:
        """« Ended » with an unaired finale is not yet finished FOR US.

        A series can be cancelled while its last episodes are still scheduled.
        Until they air and land, the honest card is « À jour ».
        """
        assert caught_up(series_status="Ended", announced_count=1) == "a_jour"

    def test_unknown_status_stays_a_jour(self) -> None:
        """No provider verdict → no « Terminé ». The founding-incident rule."""
        assert caught_up(series_status=None, announced_count=0) == "a_jour"

    def test_a_paused_follow_is_still_disabled(self) -> None:
        """« disabled » outranks everything, ended series included."""
        assert caught_up(active=False, series_status="Ended") == "disabled"

    def test_no_catalog_is_never_termine(self) -> None:
        """No catalog is no knowledge — the strongest rule in the module.

        An ended series we have never catalogued must read ``non_verifie``, not
        ``termine``: we do not know what it contains, so we cannot claim to hold
        all of it.
        """
        assert caught_up(aired_count=None, series_status="Ended") == "non_verifie"


class TestAbsenceOfAnnouncementIsNotAnEnding:
    """Why « Terminé » needs the provider status, measured on real data."""

    def test_house_of_the_dragon_2026_08_09(self) -> None:
        """The case that rules out the announcement-only rule.

        Measured on the production acquire database on 2026-08-09, the day the
        operator asked for this split: « House of the Dragon » had **zero**
        future episodes cached and its most recent aired episode dated **that
        very day** — the series was airing. An « plus rien d'annoncé ⇒ terminé »
        rule would have declared a running series finished.

        The provider knows better, and says so: TVDB carries « Continuing ».
        """
        announcement_only_rule_would_say = "termine"
        assert caught_up(series_status="Continuing", announced_count=0) != announcement_only_rule_would_say
        assert caught_up(series_status="Continuing", announced_count=0) == "a_jour"
