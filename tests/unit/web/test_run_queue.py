"""Unit tests for the shared §6 visible-queue wait loop (``web/run_queue.py``).

The loop is the generalized #287 pattern: a held ``pipeline.lock`` is never a
refusal — the runner waits with a VISIBLE ``queue`` step on its run row, and a
passed deadline finalizes the row ``error`` with a French reason.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from personalscraper.web.run_queue import (
    QUEUE_STEP_NAME,
    QUEUE_WAITING_STATUS,
    wait_in_visible_queue,
)


def _call(writer: MagicMock, *, try_proceed, deadline: float, output_tail=None) -> bool:
    """Invoke the wait loop with test-friendly defaults.

    Args:
        writer: The mocked ``PipelineRunWriter``.
        try_proceed: The proceed predicate under test.
        deadline: Absolute monotonic deadline.
        output_tail: Optional ring-buffer callable.

    Returns:
        The loop's boolean outcome.
    """
    return wait_in_visible_queue(
        try_proceed=try_proceed,
        writer=writer,
        run_uid="uid123",
        deadline_monotonic=deadline,
        timeout_s=1800.0,
        timeout_error="Délai d'attente dépassé — test.",
        log_event_prefix="test_runner",
        log_context={"command": "library-repair"},
        output_tail=output_tail,
    )


class TestImmediateProceed:
    """No wait needed — the loop is invisible."""

    def test_no_step_written_when_free(self) -> None:
        """try_proceed True on the first probe → True, zero writer calls."""
        writer = MagicMock()
        assert _call(writer, try_proceed=lambda: True, deadline=time.monotonic() + 60) is True
        writer.update_step.assert_not_called()
        writer.finalize.assert_not_called()


class TestVisibleWait:
    """A real wait opens the queue step, then closes it truthfully."""

    def test_queue_step_opened_then_closed(self) -> None:
        """False → True: one 'waiting' entry then one 'done' entry, result True."""
        writer = MagicMock()
        answers = iter([False, True])
        with patch("personalscraper.web.run_queue.time.sleep"):
            result = _call(writer, try_proceed=lambda: next(answers), deadline=time.monotonic() + 60)
        assert result is True
        assert writer.update_step.call_count == 2
        first = writer.update_step.call_args_list[0][0]
        second = writer.update_step.call_args_list[1][0]
        assert first[1] == QUEUE_STEP_NAME
        assert first[4] == QUEUE_WAITING_STATUS
        assert second[1] == QUEUE_STEP_NAME
        assert second[4] == "done"
        # The closing entry records the true wait window (start <= end).
        assert second[2] <= second[3]
        writer.finalize.assert_not_called()


class TestDeadline:
    """A passed deadline finalizes 'error' in French and returns False."""

    def test_timeout_finalizes_error_with_reason(self) -> None:
        """Deadline in the past → queue step written, then finalize('error')."""
        writer = MagicMock()
        result = _call(
            writer,
            try_proceed=lambda: False,
            deadline=time.monotonic() - 1,
            output_tail=lambda: "tail-contents",
        )
        assert result is False
        # The wait was still made visible before giving up.
        assert writer.update_step.call_count == 1
        writer.finalize.assert_called_once_with(
            "uid123",
            "error",
            error="Délai d'attente dépassé — test.",
            output_tail="tail-contents",
        )

    def test_timeout_without_ring_buffer_passes_none(self) -> None:
        """No output_tail callable → finalize receives output_tail=None."""
        writer = MagicMock()
        assert _call(writer, try_proceed=lambda: False, deadline=time.monotonic() - 1) is False
        assert writer.finalize.call_args.kwargs["output_tail"] is None
