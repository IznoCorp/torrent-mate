"""JSON-based tracker for ingested torrents.

Persists torrent hashes to data_dir/ingested_torrents.json
to avoid re-ingesting already-processed torrents. Uses atomic writes
(write to .tmp then os.replace) to prevent corruption on crash.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("tracker")


def _default_tracker_file() -> Path:
    """Return the default tracker file path from settings.

    Returns:
        Path to ingested_torrents.json inside the configured data directory.
    """
    from personalscraper.config import get_settings

    return get_settings().data_dir / "ingested_torrents.json"


class IngestTracker:
    """Persist the state of already-ingested torrents in a JSON file.

    The JSON structure is a dict mapping torrent hash to metadata:
    ``{"abc123": {"name": "The.Boys.S05E01", "action": "copied", "date": "..."}}``

    Attributes:
        tracker_path: Path to the JSON tracker file.
        _data: In-memory dict of torrent hash to metadata.
    """

    def __init__(self, tracker_path: Path | None = None) -> None:
        """Initialize the tracker.

        Args:
            tracker_path: Path to the JSON file. Defaults to settings.data_dir/ingested_torrents.json.
        """
        if tracker_path is None:
            tracker_path = _default_tracker_file()
        self.tracker_path = tracker_path
        self._data: dict[str, dict] = {}
        self.load()

    def load(self) -> dict[str, dict]:
        """Load tracker data from the JSON file.

        Creates parent directory if missing. Handles missing or corrupted files
        gracefully by starting with an empty dict.

        Returns:
            The loaded tracker data dict.
        """
        self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
        if self.tracker_path.exists():
            try:
                self._data = json.loads(self.tracker_path.read_text())
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                log.error(
                    "tracker_corrupted_or_unreadable",
                    path=str(self.tracker_path),
                    error=str(exc),
                )
                self._data = {}
        else:
            self._data = {}
        return self._data

    def save(self) -> None:
        """Save tracker data to the JSON file atomically.

        Writes to a .tmp file first, then uses os.replace() for an atomic
        rename. This prevents corruption if the process is killed mid-write.
        Logs an error on write failure instead of crashing the ingest loop.
        """
        tmp_path = self.tracker_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(self._data, indent=2))
            os.replace(tmp_path, self.tracker_path)
        except OSError as e:
            log.error("tracker_save_failed", path=str(self.tracker_path), error=str(e))
            # Clean up orphaned .tmp to avoid stale files
            tmp_path.unlink(missing_ok=True)

    def is_ingested(self, torrent_hash: str) -> bool:
        """Check if a torrent has already been ingested.

        Args:
            torrent_hash: The torrent hash to check.

        Returns:
            True if the hash exists in the tracker.
        """
        return torrent_hash in self._data

    def mark_ingested(self, torrent_hash: str, torrent_name: str, action: str) -> None:
        """Record a torrent as ingested and persist to disk.

        Args:
            torrent_hash: The torrent hash identifier.
            torrent_name: Human-readable torrent name.
            action: Transfer action performed ("copied" or "moved").
        """
        self._data[torrent_hash] = {
            "name": torrent_name,
            "action": action,
            "date": datetime.now().isoformat(),
        }
        self.save()
        log.info("torrent_marked", hash=torrent_hash, name=torrent_name, action=action)

    def cleanup(self, active_hashes: set[str]) -> int:
        """Remove entries for torrents no longer in qBittorrent.

        Args:
            active_hashes: Set of torrent hashes currently in qBittorrent.

        Returns:
            Number of stale entries removed.
        """
        stale = set(self._data.keys()) - active_hashes
        for h in stale:
            del self._data[h]
        if stale:
            self.save()
            log.info("tracker_cleaned", removed=len(stale))
        return len(stale)
