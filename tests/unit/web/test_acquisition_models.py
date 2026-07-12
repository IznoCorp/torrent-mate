"""Unit tests for acquisition API Pydantic models (acq-watch feature).

Focused on the C14 server-side ``FollowedSeriesItem.status`` derivation — the
single source of truth the UI maps to a badge tone/label without re-deriving
business state in JSX.
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
    """``FollowedSeriesItem.status`` is derived from active + wanted_pending."""

    @pytest.mark.parametrize("pending", [0, 1, 7])
    def test_disabled_when_inactive(self, pending: int) -> None:
        """An inactive series is ``disabled`` regardless of pending count."""
        assert _item(active=False, wanted_pending=pending).status == "disabled"

    def test_pending_when_active_with_pending(self) -> None:
        """An active series with pending searches is ``pending``."""
        assert _item(active=True, wanted_pending=3).status == "pending"

    def test_up_to_date_when_active_and_idle(self) -> None:
        """An active series with nothing pending is ``up_to_date``."""
        assert _item(active=True, wanted_pending=0).status == "up_to_date"

    def test_status_is_serialised(self) -> None:
        """The computed field is present in the serialised payload."""
        dumped = _item(active=True, wanted_pending=0).model_dump()
        assert dumped["status"] == "up_to_date"
