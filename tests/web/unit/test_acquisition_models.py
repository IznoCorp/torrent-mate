"""Unit tests for acquisition API Pydantic models (acq-watch feature).

Focused on the server-side ``FollowedSeriesItem.status`` derivation — the single
source of truth the UI maps to a badge tone/label without re-deriving business
state in JSX.

Translated to the five-state model (acq-states phase 4): the raw
``wanted_pending`` / ``wanted_grabbed`` counters no longer derive anything, so
the two former counter-driven cases now pin the OPPOSITE guarantee — a card with
no catalogue knowledge reads ``unverified`` whatever the counters say.
"""

from __future__ import annotations

import pytest

from personalscraper.web.models.acquisition import (
    FollowedSeriesItem,
    MediaRefResponse,
)


def _item(*, active: bool, wanted_pending: int) -> FollowedSeriesItem:
    """Build a minimal followed item with the given active/pending flags."""
    return FollowedSeriesItem(
        id=1,
        title="Show",
        media_ref=MediaRefResponse(tvdb_id=360001),
        active=active,
        added_at=1_750_000_000.0,
        wanted_pending=wanted_pending,
    )


class TestFollowedStatusDerivation:
    """``FollowedSeriesItem.status`` is derived from the five-state facts."""

    @pytest.mark.parametrize("pending", [0, 1, 7])
    def test_disabled_when_inactive(self, pending: int) -> None:
        """An inactive series is ``disabled`` regardless of pending count."""
        assert _item(active=False, wanted_pending=pending).status == "disabled"

    def test_raw_pending_counter_does_not_drive_status(self) -> None:
        """Pending wanted rows alone no longer produce a state.

        Was ``pending`` when the counter drove the derivation. A queue volume
        says nothing about what is owned, aired or searched — with no catalogue
        the card must admit it does not know.
        """
        assert _item(active=True, wanted_pending=3).status == "unverified"

    def test_idle_without_catalog_is_unverified_never_up_to_date(self) -> None:
        """An active series with no catalogue and no queue is ``unverified``.

        Was ``up_to_date`` — the founding incident's exact shape: zero wanted
        rows read as « À jour » while aired episodes were missing.
        """
        assert _item(active=True, wanted_pending=0).status == "unverified"

    def test_status_is_serialised(self) -> None:
        """The computed field is present in the serialised payload."""
        dumped = _item(active=True, wanted_pending=0).model_dump()
        assert dumped["status"] == "unverified"
