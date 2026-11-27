"""``RankingPreview.known_trackers``: the configured trackers a tracker-keyed criterion is offered."""

from __future__ import annotations

from personalscraper.app.acquisition.ranking import RankingPreview


def test_the_known_trackers_are_the_configured_ones_sorted() -> None:
    """The names come back sorted, whatever order the configuration listed them in."""
    preview = RankingPreview(standing_of=lambda _tracker: None, known_trackers=["tr4ker", "c411"])

    assert preview.known_trackers == ("c411", "tr4ker")


def test_no_configured_tracker_is_an_empty_roster() -> None:
    """With none configured the roster is empty, never missing."""
    assert RankingPreview(standing_of=lambda _tracker: None).known_trackers == ()
