"""Trailers orchestrator — Phase 6 stub.

Full implementation is in Phase 6. This stub is present so that
``personalscraper.trailers.step`` can be imported and tested in Phase 5
before the orchestrator is built.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class TrailersOrchestrator:
    """Stub TrailersOrchestrator — replaced by full implementation in Phase 6.

    The real orchestrator manages discovery, YouTube search, yt-dlp downloads,
    and state tracking for all staged media items.

    Attributes:
        config: Pipeline configuration.
        staging_dir: Staging area path.
        failed_items: Per-item failure list populated by run().
    """

    def __init__(self, config: Any, staging_dir: Path) -> None:
        """Initialise stub orchestrator.

        Args:
            config: Loaded pipeline Config (used by the real implementation).
            staging_dir: Path to the staging area.
        """
        self.config = config
        self.staging_dir = staging_dir
        self.failed_items: list[tuple[str, str, str]] = []

    def run(self) -> dict[str, int]:
        """Run trailer discovery and download.

        Returns:
            Counts dict with keys: downloaded, already_present, no_trailer,
            bot_detected, error, skipped_by_state. All zeros in this stub.
        """
        # Stub — Phase 6 provides the real implementation.
        return {
            "downloaded": 0,
            "already_present": 0,
            "no_trailer": 0,
            "bot_detected": 0,
            "error": 0,
            "skipped_by_state": 0,
        }
