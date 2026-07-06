"""Cooperative pause checkpoint for the pipeline engine.

Polls a sentinel file at step boundaries: when the sentinel is present,
the pipeline blocks until it is cleared or a shutdown is signalled.

.. code-block:: none

   ┌──────────────┐     pause_file exists?     ┌──────────────┐
   │ _run_step()  │ ───────────────────────────▶│ checkpoint() │
   │ (step boundary)│                            │ poll + sleep │
   └──────────────┘                            └──────┬───────┘
                                            clear / shutdown

Design contract: the pause is **between steps** — an in-flight step
is never interrupted by pause (only Kill/SIGTERM stops mid-step).
This is documented in DESIGN §3.1.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger


class PauseController:
    """Cooperative pause sentinel for the pipeline engine.

    Polls a sentinel file (``pipeline.pause``, next to ``pipeline.lock``)
    at each step boundary. When the file exists the controller emits
    :class:`~personalscraper.pipeline_events.PipelinePaused`, blocks
    until the file is cleared or a shutdown is signalled, then emits
    :class:`~personalscraper.pipeline_events.PipelineResumed`.

    No new dependency: pure :mod:`pathlib` + :mod:`time` + the existing
    shutdown/interrupt mechanism already in :class:`Pipeline`.

    Attributes:
        pause_file: Path to the sentinel file.
        poll_interval: Seconds between sentinel existence checks.
    """

    def __init__(
        self,
        pause_file: Path,
        event_bus: EventBus,
        poll_interval: float = 0.5,
        shutdown_check: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the pause controller.

        Args:
            pause_file: Absolute path to the sentinel file. The file's
                mere existence triggers a pause; its absence allows the
                pipeline to proceed.
            event_bus: The process-level event bus for emitting
                ``PipelinePaused`` / ``PipelineResumed``.
            poll_interval: Seconds between sentinel existence checks
                during the pause loop. Must be > 0.
            shutdown_check: Optional callable checked on each poll
                iteration during a pause. It should raise
                ``_PipelineInterrupted`` (or a subclass) when the
                pipeline has been asked to shut down. Defaults to a
                no-op for isolated testing.
        """
        self._pause_file = pause_file
        self._event_bus = event_bus
        self._poll_interval = poll_interval
        self._shutdown_check: Callable[[], None] = shutdown_check if shutdown_check is not None else lambda: None
        self._log = get_logger("pause")

    def checkpoint(self) -> None:
        """Block at a step boundary if the pause sentinel is present.

        If the sentinel file does not exist, returns immediately (no-op —
        no events are emitted). When the sentinel **does** exist:

        1. Emit ``PipelinePaused``.
        2. Loop: if a shutdown has been requested (checked via the
           :class:`Pipeline`'s existing ``_shutdown_requested`` flag
           passed through ``_shutdown_check``), raise the interrupt
           exception. Otherwise sleep ``poll_interval`` seconds and
           re-check the sentinel.
        3. When the sentinel is cleared, emit ``PipelineResumed`` and
           return.

        Raises:
            _PipelineInterrupted: If the shutdown callback raises it
                during the pause loop.
        """
        if not self._pause_file.exists():
            return

        # Lazy import to avoid circular dependency — the pipeline module
        # imports from this module (PauseController), and pipeline_events
        # is already available.
        from personalscraper.pipeline_events import PipelinePaused

        self._log.info("pipeline_paused", pause_file=str(self._pause_file))
        self._event_bus.emit(PipelinePaused())

        while self._pause_file.exists():
            self._shutdown_check()
            time.sleep(self._poll_interval)

        from personalscraper.pipeline_events import PipelineResumed

        self._log.info("pipeline_resumed")
        self._event_bus.emit(PipelineResumed())

    def is_paused(self) -> bool:
        """Return ``True`` if the pause sentinel currently exists.

        Read-only probe intended for the web status route
        (``GET /api/pipeline/status``). The pause file is consumed by
        the checkpoint loop, not by this method.
        """
        return self._pause_file.exists()
