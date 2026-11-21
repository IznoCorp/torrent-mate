"""K3 P10 — ``tracker_ratio_state`` in the ranking, and the preview that shows it.

``rank()`` is UNCHANGED (DESIGN § 2.10): a criterion ``{field: "tracker_ratio_state", values: {...}}``
scores the field the way ``provider`` is scored, and a ranking that names no such criterion scores
byte-identically to before, whatever state the results carry. No default criterion ships: the
tracked template is pinned below. ``RankingPreview`` serves the preview's fixed samples with their
tracker's standing; every state reads ``None`` until K5 writes ``ratio_state`` (O-8 A).
"""

from __future__ import annotations

from pathlib import Path

import json5
import pytest

from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, rank
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.ids import AccountId, RoleId
from personalscraper.app.accounts.rights import Right
from personalscraper.app.acquisition.ranking import RankingPreview
from personalscraper.app.errors import AppForbidden
from personalscraper.core.units import ByteSize

_NO_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)

_STATE_SCORES = {"under_floor": -50, "under_target": 0, "comfortable": 10}


def _result(provider: str, seeders: int = 10, state: str | None = None, tid: str = "t") -> TrackerResult:
    """Build a result differing only on the axes under test."""
    return TrackerResult(
        provider=provider,
        tracker_id=f"{provider}-{tid}",
        title=f"Movie 2024 {provider}",
        size=ByteSize(4_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution="1080p",
        tracker_ratio_state=state,
    )


def _admin() -> Actor:
    """An Admin actor, who holds every right the ceiling leaves."""
    return Actor.system(_NO_CEILING, account_id=AccountId("admin"), name="admin")


def _ordinary(rights: frozenset[Right]) -> Actor:
    """An ordinary-role actor carrying only *rights*."""
    return Actor(
        account_id=AccountId("a"),
        name="a",
        role_id=RoleId("role-a"),
        role_kind=RoleKind.ORDINARY,
        role_rights=rights,
        ceiling=_NO_CEILING,
    )


class TestTrackerResultField:
    """``TrackerResult.tracker_ratio_state`` is additive."""

    def test_defaults_to_none(self) -> None:
        """A result built as before P10 carries no state."""
        assert _result("c411").tracker_ratio_state is None


class TestRankScoresTheState:
    """A criterion on ``tracker_ratio_state`` scores like ``provider``."""

    _CRITERION = RankingCriterion(field="tracker_ratio_state", weight=1.0, values=_STATE_SCORES)

    def test_each_state_scores_its_value(self) -> None:
        """The three members score ``-50`` / ``0`` / ``10``."""
        results = [
            _result("a", state="under_floor", tid="1"),
            _result("a", state="under_target", tid="2"),
            _result("a", state="comfortable", tid="3"),
        ]

        scored = rank(results, RankingConfig(criteria=[self._CRITERION], min_seeders=0))

        assert [(r.tracker_ratio_state, s) for r, s in scored] == [
            ("comfortable", 10),
            ("under_target", 0),
            ("under_floor", -50),
        ]

    def test_the_weight_multiplies(self) -> None:
        """The criterion's weight applies as to any other categorical criterion."""
        criterion = RankingCriterion(field="tracker_ratio_state", weight=2.0, values=_STATE_SCORES)

        scored = rank([_result("a", state="comfortable")], RankingConfig(criteria=[criterion], min_seeders=0))

        assert scored[0][1] == 20

    def test_a_none_state_scores_nothing(self) -> None:
        """A result with no state (no economy, no observed ratio) is skipped by the criterion."""
        scored = rank([_result("a", state=None)], RankingConfig(criteria=[self._CRITERION], min_seeders=0))

        assert scored[0][1] == 0

    def test_a_starved_tracker_sinks_below_a_comfortable_one(self) -> None:
        """The point of the axis: more seeders do not rescue a release from an under-floor tracker."""
        results = [_result("starved", seeders=99, state="under_floor"), _result("fed", seeders=1, state="comfortable")]

        scored = rank(results, RankingConfig(criteria=[self._CRITERION], min_seeders=0))

        assert [r.provider for r, _ in scored] == ["fed", "starved"]


class TestNoCriterionIsByteIdentical:
    """Without a criterion naming the field, the state moves no score."""

    _SEEDERS = RankingCriterion(field="provider", values={"fed": 5, "starved": 3})

    def test_states_do_not_change_scores_or_order(self) -> None:
        """The same results with and without states rank identically."""
        bare = [_result("fed", 7, None, "1"), _result("starved", 90, None, "2"), _result("other", 4, None, "3")]
        stated = [
            _result("fed", 7, "comfortable", "1"),
            _result("starved", 90, "under_floor", "2"),
            _result("other", 4, "under_target", "3"),
        ]
        ranking = RankingConfig(criteria=[self._SEEDERS], min_seeders=0)

        assert [(r.tracker_id, s) for r, s in rank(bare, ranking)] == [
            (r.tracker_id, s) for r, s in rank(stated, ranking)
        ]

    def test_the_tracked_template_names_no_such_criterion(self) -> None:
        """No default criterion: the operator writes it in the ranking settings (DESIGN § 2.10)."""
        raw = json5.loads(Path("config.example/ranking.json5").read_text())

        fields = {c["field"] for c in raw["ranking"]["criteria"]}

        assert "tracker_ratio_state" not in fields


class TestRankingPreview:
    """``RankingPreview.preview(actor, ranking)``: the samples with their tracker's standing."""

    _STATES = {"tr4ker": "comfortable", "c411": "under_floor"}

    def test_every_sample_carries_its_trackers_standing(self) -> None:
        """Each sample's state is the standing of its tracker; none is dropped."""
        preview = RankingPreview(standing_of=self._STATES.get)

        rows = preview.preview(_admin(), RankingConfig(min_seeders=0))

        assert len(rows) == 12
        assert {r.provider for r in rows} == {"tr4ker", "c411"}
        assert all(r.tracker_ratio_state == self._STATES[r.provider] for r in rows)

    def test_every_state_reads_none_until_a_ratio_is_written(self) -> None:
        """K5 writes ``ratio_state``: until then the resolver answers ``None`` for every tracker."""
        preview = RankingPreview(standing_of=lambda _tracker: None)

        rows = preview.preview(_admin(), RankingConfig(min_seeders=0))

        assert {r.tracker_ratio_state for r in rows} == {None}

    def test_a_criterion_on_the_state_reorders_the_samples(self) -> None:
        """Naming the field in the candidate ranking moves the samples the way ``provider`` would."""
        criterion = RankingCriterion(field="tracker_ratio_state", values=_STATE_SCORES)
        preview = RankingPreview(standing_of=self._STATES.get)

        # Freeleech bonuses off: the samples differ by their tracker's standing alone.
        ranking = RankingConfig(criteria=[criterion], bonuses=RankingBonuses(freeleech=0, silverleech=0), min_seeders=0)

        rows = preview.preview(_admin(), ranking)

        assert {r.score for r in rows if r.provider == "tr4ker"} == {10}
        assert {r.score for r in rows if r.provider == "c411"} == {-50}
        assert [r.provider for r in rows[:6]] == ["tr4ker"] * 6

    def test_no_criterion_leaves_scores_unmoved_by_the_standing(self) -> None:
        """With no criterion on the field, the scores and the order equal those of an unknown standing."""
        criterion = RankingCriterion(field="provider", values={"tr4ker": 5, "c411": 3})
        ranking = RankingConfig(criteria=[criterion], min_seeders=0)

        stated = RankingPreview(standing_of=self._STATES.get).preview(_admin(), ranking)
        unknown = RankingPreview(standing_of=lambda _tracker: None).preview(_admin(), ranking)

        assert [(r.title, r.score) for r in stated] == [(r.title, r.score) for r in unknown]

    def test_a_sample_under_min_seeders_is_flagged_and_sunk_never_dropped(self) -> None:
        """The preview's own contract, kept: ``excluded`` rows are shown, last."""
        preview = RankingPreview(standing_of=lambda _tracker: None)

        rows = preview.preview(_admin(), RankingConfig(min_seeders=30))

        assert len(rows) == 12
        flags = [r.excluded for r in rows]
        assert flags == sorted(flags)
        assert all(r.excluded == (r.seeders < 30) for r in rows)
        assert any(flags) and not all(flags)

    def test_the_actor_needs_configuration_write(self) -> None:
        """``previewRanking`` is ``configuration.write``: refused before any standing is read."""
        asked: list[str] = []

        def standing_of(tracker: str) -> str | None:
            asked.append(tracker)
            return None

        preview = RankingPreview(standing_of=standing_of)

        with pytest.raises(AppForbidden):
            preview.preview(_ordinary(frozenset({Right.LIBRARY_READ})), RankingConfig())

        assert asked == []
