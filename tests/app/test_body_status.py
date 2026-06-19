"""Tests for the fail-soft body-top status orchestrator (:mod:`kanbanmate.app.body_status`, FIX 5).

These pin the seeder-None no-op, the body-diff gate (no write when unchanged), the single
``update_issue_body`` with the fetched node id, and the fail-soft swallow of fetch/patch errors.
The pure transform is tested in :mod:`tests.core.test_body_edit`; here we exercise the I/O wiring.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from kanbanmate.adapters.github.types import IssueRef
from kanbanmate.app.body_status import update_body_status
from kanbanmate.core.body_edit import STATUS_BEGIN


def _ref(body: str = "", node_id: str = "ISSUE_NODE_7", number: int = 7) -> IssueRef:
    """Build an :class:`IssueRef` carrying ``body`` + ``node_id`` for the fake seeder."""
    return IssueRef(node_id=node_id, number=number, title="[A1] X", body=body)


def test_seeder_none_is_noop() -> None:
    """``seeder is None`` → no fetch, no write (the unwired body-writer no-op)."""
    # No seeder; the call must not raise and must do nothing observable.
    update_body_status(None, 7, stage="Design", state="running", summary="x", now=1000.0)


def test_unchanged_body_skips_update() -> None:
    """The body-diff gate: when the rendered body equals the current one, NO update_issue_body."""
    seeder = MagicMock()
    # First render the block once, feed it back so a second identical render is a no-op.
    seeder.fetch_issue.return_value = _ref("")
    update_body_status(seeder, 7, stage="Design", state="running", summary="x", now=1000.0)
    assert seeder.update_issue_body.call_count == 1
    written_body = seeder.update_issue_body.call_args.args[1]
    # Now the stored body already carries the identical block → the diff gate skips the write.
    seeder.reset_mock()
    seeder.fetch_issue.return_value = _ref(written_body)
    update_body_status(seeder, 7, stage="Design", state="running", summary="x", now=1000.0)
    seeder.update_issue_body.assert_not_called()


def test_changed_body_writes_with_fetched_node_id() -> None:
    """A changed body → exactly one update_issue_body with the node id from fetch_issue."""
    seeder = MagicMock()
    seeder.fetch_issue.return_value = _ref("existing body", node_id="ISSUE_NODE_42")
    update_body_status(seeder, 7, stage="Plan", state="done", summary="stage complete", now=1000.0)
    seeder.update_issue_body.assert_called_once()
    node_id, new_body = seeder.update_issue_body.call_args.args
    assert node_id == "ISSUE_NODE_42"
    assert new_body.startswith(STATUS_BEGIN)
    assert "existing body" in new_body  # original content preserved below the header


def test_latest_progress_surfaced_in_header() -> None:
    """BUG A: a non-empty ``latest_progress`` is rendered AS the header summary (not the static one)."""
    seeder = MagicMock()
    seeder.fetch_issue.return_value = _ref("")
    update_body_status(
        seeder,
        7,
        stage="Design",
        state="running",
        summary="agent dispatched (docs)",
        now=1000.0,
        latest_progress="wrote DESIGN §3 module map",
    )
    seeder.update_issue_body.assert_called_once()
    new_body = seeder.update_issue_body.call_args.args[1]
    # The milestone is the visible header text; the static summary is NOT used when progress exists.
    assert "wrote DESIGN §3 module map" in new_body
    assert "agent dispatched (docs)" not in new_body


def test_none_progress_falls_back_to_static_summary() -> None:
    """BUG A: ``latest_progress=None`` falls back to the static summary (no blank-header regression)."""
    seeder = MagicMock()
    seeder.fetch_issue.return_value = _ref("")
    update_body_status(
        seeder,
        7,
        stage="Design",
        state="done",
        summary="stage complete",
        now=1000.0,
        latest_progress=None,
    )
    seeder.update_issue_body.assert_called_once()
    new_body = seeder.update_issue_body.call_args.args[1]
    assert "stage complete" in new_body


def test_empty_progress_falls_back_to_static_summary() -> None:
    """BUG A: an EMPTY ``latest_progress`` ("") also falls back (treated like a miss)."""
    seeder = MagicMock()
    seeder.fetch_issue.return_value = _ref("")
    update_body_status(
        seeder,
        7,
        stage="Plan",
        state="waiting",
        summary="waiting for your input",
        now=1000.0,
        latest_progress="",
    )
    seeder.update_issue_body.assert_called_once()
    new_body = seeder.update_issue_body.call_args.args[1]
    assert "waiting for your input" in new_body


def test_fetch_issue_error_swallowed() -> None:
    """A ``fetch_issue`` failure is swallowed — never raises into the caller."""
    seeder = MagicMock()
    seeder.fetch_issue.side_effect = RuntimeError("boom")
    # Must not raise.
    update_body_status(seeder, 7, stage="Design", state="running", summary="x", now=1000.0)
    seeder.update_issue_body.assert_not_called()


def test_update_issue_body_error_swallowed() -> None:
    """An ``update_issue_body`` failure is swallowed — never raises into the caller."""
    seeder = MagicMock()
    seeder.fetch_issue.return_value = _ref("body")
    seeder.update_issue_body.side_effect = RuntimeError("patch failed")
    # Must not raise.
    update_body_status(seeder, 7, stage="Design", state="running", summary="x", now=1000.0)
