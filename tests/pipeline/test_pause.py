"""``PauseController`` unit tests: sentinel present → polls, cleared → proceeds.

Covers the three scenarios from DESIGN §3.1:
- Sentinel absent → ``checkpoint()`` returns immediately (no events).
- Sentinel present then cleared → ``PipelinePaused`` + ``PipelineResumed`` fired.
- Shutdown requested while paused → ``_PipelineInterrupted`` raised.

All tests mock ``time.sleep`` via ``monkeypatch`` so the pause loop never
actually blocks.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from personalscraper.core.event_bus import Event, EventBus
from personalscraper.pause import PauseController
from personalscraper.pipeline_events import PipelinePaused, PipelineResumed
from tests.fixtures.event_bus import CollectingSubscriber


class TestPauseController:
    """Unit tests for :class:`PauseController`."""

    @pytest.fixture
    def tmp_pause_file(self, tmp_path: Path) -> Path:
        """Return a path inside a temporary directory."""
        return tmp_path / "pipeline.pause"

    @pytest.fixture
    def event_bus(self) -> EventBus:
        """Return a real :class:`EventBus` for verifying emits."""
        return EventBus()

    def make_controller(self, pause_file: Path, event_bus: EventBus) -> PauseController:
        """Build a :class:`PauseController` with a fast poll interval."""
        return PauseController(
            pause_file=pause_file,
            event_bus=event_bus,
            poll_interval=0.01,
        )

    # --- Sentinel absent → no-op -----------------------------------------

    def test_sentinel_absent_returns_immediately_no_events(self, tmp_pause_file: Path, event_bus: EventBus) -> None:
        """When the pause file does not exist, checkpoint() is a no-op."""
        ctrl = self.make_controller(tmp_pause_file, event_bus)

        with CollectingSubscriber(event_bus, event_type=Event) as sub:
            ctrl.checkpoint()

        assert sub.received == []
        assert not tmp_pause_file.exists()

    # --- Sentinel present → cleared → proceeds --------------------------

    def test_sentinel_present_then_cleared_emits_paused_and_resumed(
        self,
        tmp_pause_file: Path,
        event_bus: EventBus,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pause file exists, then is removed → Paused + Resumed events fire."""
        tmp_pause_file.touch()
        ctrl = self.make_controller(tmp_pause_file, event_bus)

        # After one sleep cycle, clear the sentinel so the loop exits.
        call_count = 0
        original_sleep = time.sleep

        def _sleep_and_clear(secs: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                tmp_pause_file.unlink()
            original_sleep(secs)

        monkeypatch.setattr(time, "sleep", _sleep_and_clear)

        with CollectingSubscriber(event_bus, event_type=Event) as sub:
            ctrl.checkpoint()

        assert len(sub.received) == 2
        assert isinstance(sub.received[0], PipelinePaused)
        assert isinstance(sub.received[1], PipelineResumed)

    # --- Shutdown requested while paused ---------------------------------

    def test_shutdown_while_paused_raises_interrupt(
        self,
        tmp_pause_file: Path,
        event_bus: EventBus,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A shutdown signal during the pause loop raises the interrupt."""
        from personalscraper.pipeline import _PipelineInterrupted

        tmp_pause_file.touch()
        ctrl = self.make_controller(tmp_pause_file, event_bus)

        call_count = 0
        original_sleep = time.sleep

        def _sleep_then_count(secs: float) -> None:
            nonlocal call_count
            call_count += 1
            original_sleep(secs)

        monkeypatch.setattr(time, "sleep", _sleep_then_count)

        # Wire the shutdown gate: after the first sleep, raise.
        def _shutdown_after_first_sleep() -> None:
            if call_count >= 1:
                raise _PipelineInterrupted("shutdown_requested")

        ctrl._shutdown_check = _shutdown_after_first_sleep

        with pytest.raises(_PipelineInterrupted):
            ctrl.checkpoint()

    # --- is_paused probe -------------------------------------------------

    def test_is_paused_reads_sentinel_existence(self, tmp_pause_file: Path, event_bus: EventBus) -> None:
        """``is_paused()`` returns True iff the sentinel file exists."""
        ctrl = self.make_controller(tmp_pause_file, event_bus)

        assert ctrl.is_paused() is False
        tmp_pause_file.touch()
        assert ctrl.is_paused() is True
        tmp_pause_file.unlink()
        assert ctrl.is_paused() is False
