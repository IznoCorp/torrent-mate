"""An absorbed episode must report what its SEASON row is actually doing (§2).

Live incident 2026-08-04: the reswitch declared both American Dad season packs dead,
deleted them from the client and requeued rows #88/#89 to ``pending`` — correctly. But
the four absorbed episodes kept reading « En cours d'acquisition », because
``derive_episode_state`` returns ``absorbed`` unconditionally and neither read path
(card ``truth.py``, matrix ``completeness.py``) ever loads the season row. The operator
saw « source bloquée, bascule vers une autre release » and then… no change at all.

``absorbed`` is not a state of the episode — it is a POINTER to the row that carries its
acquisition. Reading the pointer instead of following it is what produced the lie.
"""

from __future__ import annotations

import pytest

from personalscraper.web.acquisition.states import (
    derive_episode_state,
    select_wanted_facts,
    substitute_absorbed_facts,
)


class TestSubstituteAbsorbedFacts:
    """The absorbed row's facts become the absorbing season row's facts."""

    def test_absorbed_row_takes_the_season_facts(self) -> None:
        """A season still grabbing ⇒ the episode really is being acquired."""
        rows = [(10, "absorbed", "no_candidates", 0, 88)]
        season = {88: ("grabbed", "grabbed", 4)}

        out = substitute_absorbed_facts(rows, season)

        assert out == [(10, "grabbed", "grabbed", 4)]

    def test_requeued_season_stops_claiming_acquisition(self) -> None:
        """THE incident: the season was requeued by the reswitch — nothing is in flight."""
        rows = [(10, "absorbed", "no_candidates", 0, 88)]
        season = {88: ("pending", None, None)}

        out = substitute_absorbed_facts(rows, season)
        status, outcome, found = select_wanted_facts(out)

        assert (
            derive_episode_state(
                owned=False,
                wanted_status=status,
                last_search_outcome=outcome,
                last_search_found=found,
            )
            == "unverified"
        ), "a requeued season is « non vérifié », never « en cours »"

    def test_non_absorbed_rows_pass_through_untouched(self) -> None:
        """Only absorbed rows are redirected — everything else is left alone."""
        rows = [(10, "grabbed", "grabbed", 1, None), (11, "pending", "no_candidates", 0, None)]

        assert substitute_absorbed_facts(rows, {}) == [
            (10, "grabbed", "grabbed", 1),
            (11, "pending", "no_candidates", 0),
        ]

    def test_unknown_season_link_keeps_the_absorbed_reading(self) -> None:
        """A dangling link is ignorance, not a licence to invent a state.

        ``absorbed_by`` has no FK (advisory), so the row may point nowhere. Falling back
        to ``absorbed`` keeps the historical reading rather than silently downgrading a
        season that IS being grabbed.
        """
        rows = [(10, "absorbed", None, None, 999)]

        assert substitute_absorbed_facts(rows, {}) == [(10, "absorbed", None, None)]

    def test_null_link_keeps_the_absorbed_reading(self) -> None:
        """Same for a row absorbed before the link column existed."""
        rows = [(10, "absorbed", None, None, None)]

        assert substitute_absorbed_facts(rows, {}) == [(10, "absorbed", None, None)]


class TestEndToEndStateOfAnAbsorbedEpisode:
    """What the operator finally reads, per season-row status."""

    @pytest.mark.parametrize(
        "season_facts,expected",
        [
            (("grabbed", "grabbed", 4), "acquiring"),
            (("available", "available", 2), "to_grab"),
            (("pending", "no_candidates", 0), "pending"),
            (("pending", None, None), "unverified"),
            (("searching", "no_candidates", 0), "pending"),
        ],
    )
    def test_episode_mirrors_its_season(self, season_facts: tuple[str, str | None, int | None], expected: str) -> None:
        """The episode says exactly what the row carrying its acquisition says."""
        rows = [(10, "absorbed", "no_candidates", 0, 88)]
        out = substitute_absorbed_facts(rows, {88: season_facts})
        status, outcome, found = select_wanted_facts(out)

        assert (
            derive_episode_state(
                owned=False,
                wanted_status=status,
                last_search_outcome=outcome,
                last_search_found=found,
            )
            == expected
        )


class TestGoverningFactsByEpisodeIsTheSingleSeam:
    """ONE function answers « which row speaks for this episode », for every surface.

    Both read paths (the card in ``truth.py``, the matrix in ``completeness.py``) used
    to group rows, resolve absorption and select the governing row **each on their
    own**. Two implementations of one rule is how the card and the matrix drift into
    disagreeing about the same episode — the defect this seam exists to prevent.
    """

    def test_groups_selects_and_resolves_in_one_call(self) -> None:
        """Episode rows + season rows in, authoritative facts per episode out."""
        from personalscraper.web.acquisition.states import governing_facts_by_episode

        episode_rows = [
            # (id, season, episode, status, outcome, found, absorbed_by)
            (1, 15, 21, "absorbed", "no_candidates", 0, 88),
            (2, 15, 22, "absorbed", "no_candidates", 0, 88),
            (3, 16, 1, "pending", "no_candidates", 0, None),
        ]
        season_rows = [(88, "pending", None, None)]

        facts = governing_facts_by_episode(episode_rows, season_rows)

        assert facts[(15, 21)] == ("pending", None, None)
        assert facts[(15, 22)] == ("pending", None, None)
        assert facts[(16, 1)] == ("pending", "no_candidates", 0)

    def test_latest_open_row_still_wins_per_episode(self) -> None:
        """The « highest id among admitted rows » rule survives the refactor."""
        from personalscraper.web.acquisition.states import governing_facts_by_episode

        episode_rows = [
            (1, 15, 21, "absorbed", None, None, 88),
            (7, 15, 21, "pending", "no_candidates", 0, None),  # re-enqueued after R6
        ]
        season_rows = [(88, "grabbed", "grabbed", 4)]

        facts = governing_facts_by_episode(episode_rows, season_rows)

        assert facts[(15, 21)] == ("pending", "no_candidates", 0)

    def test_episode_with_no_row_is_absent(self) -> None:
        """No row ⇒ no entry; the caller degrades to « jamais cherché » itself."""
        from personalscraper.web.acquisition.states import governing_facts_by_episode

        assert governing_facts_by_episode([], []) == {}
