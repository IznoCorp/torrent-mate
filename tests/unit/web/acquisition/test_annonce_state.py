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
        assert state == "announced"

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
        assert state == "announced", "a future episode is announced regardless of its facts"

    def test_annonce_precedes_the_no_row_unverified_path(self) -> None:
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
        assert no_row == "announced"

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
        assert state != "announced"
        assert state == "unverified"  # aired, no row, unowned

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
        assert owned == "in_library"

    def test_missing_air_date_falls_through_to_the_five_states(self) -> None:
        """Additive: callers passing no air_date/today get the historical behaviour."""
        assert (
            derive_episode_state(owned=True, wanted_status=None, last_search_outcome=None, last_search_found=None)
            == "in_library"
        )
        assert (
            derive_episode_state(owned=False, wanted_status="grabbed", last_search_outcome=None, last_search_found=None)
            == "acquiring"
        )


class TestAnnonceExcludedFromCard:
    """ACC-03 — an announced future never degrades the aggregated card status."""

    def test_all_aired_owned_stays_up_to_date_with_announced_ahead(self) -> None:
        """The card counts AIRED episodes only; announced ones enter no bucket.

        ``derive_follow_status`` aggregates the five per-state counts. A future
        episode is ``annonce`` — which has no counter — so a series whose aired
        episodes are all owned stays « À jour ». The announced count reaches the
        aggregation (it is what tells « À jour » from « Terminé ») but never as a
        bucket: were it counted as one, this series would read ``non_verifie``.
        """
        status = derive_follow_status(
            active=True,
            aired_count=8,  # 8 aired episodes...
            to_grab_count=0,
            acquiring_count=0,
            pending_count=0,
            unverified_count=0,  # ...all owned (aired_count == owned, nothing pending)
            announced_count=3,  # ...and three announced ahead
            series_status="Continuing",
        )
        assert status == "up_to_date", "announced futures must not degrade an up-to-date series"

    @pytest.mark.parametrize(
        ("counts", "expected"),
        [
            ({"to_grab_count": 1}, "to_grab"),
            ({"acquiring_count": 1}, "acquiring"),
            ({"pending_count": 1}, "pending"),
            ({"unverified_count": 1}, "unverified"),
        ],
    )
    def test_announced_count_never_changes_an_actionable_status(self, counts: dict[str, int], expected: str) -> None:
        """The announced count may only ever pick between ``a_jour`` and ``termine``.

        ``derive_follow_status`` now RECEIVES an announced count (operator,
        2026-08-09: « À jour » had to split in two). The reason it was kept out
        before still stands and is what this pins: an announced future must
        never DEGRADE a series. Whatever the futures say, a series with
        something takeable still reads « à récupérer », one being acquired still
        reads « en acquisition », and so on — the announced count is only
        consulted once every other bucket is empty.
        """
        base = {
            "to_grab_count": 0,
            "acquiring_count": 0,
            "pending_count": 0,
            "unverified_count": 0,
        }
        for announced in (0, 7):
            for series_status in (None, "Ended", "Continuing"):
                status = derive_follow_status(
                    active=True,
                    aired_count=8,
                    **{**base, **counts},
                    announced_count=announced,
                    series_status=series_status,
                )
                assert status == expected, (
                    f"announced={announced} series_status={series_status!r} changed an "
                    f"actionable status into {status!r}"
                )
