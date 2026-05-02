"""JSON-based tracker for ingested torrents.

Persists torrent hashes to data_dir/ingested_torrents.json
to avoid re-ingesting already-processed torrents. Uses atomic writes
(write to .tmp then os.replace) to prevent corruption on crash.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from personalscraper.io_utils import atomic_write_json
from personalscraper.logger import get_logger

log = get_logger("tracker")


def _default_tracker_file() -> Path:
    """Return the default tracker file path from the loaded Config.

    The tracker used to read ``Settings.data_dir`` (legacy, CWD-relative,
    silently defaulted to ``./.data``). That path diverged from
    ``Config.paths.data_dir`` (json5, absolute, under the staging area),
    producing two tracker files that gradually fell out of sync.

    Now resolves from Config so the tracker follows the staging layout
    the rest of the pipeline uses. Callers that want a different path
    should pass ``tracker_path`` explicitly to :class:`IngestTracker`.

    Returns:
        Path to ingested_torrents.json inside ``Config.paths.data_dir``.
    """
    from personalscraper.conf.loader import load_config, resolve_config_path

    config = load_config(resolve_config_path())
    return config.paths.data_dir / "ingested_torrents.json"


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
        self._data: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> dict[str, dict[str, Any]]:
        """Load tracker data from the JSON file.

        Creates parent directory if missing. Handles missing or corrupted files
        gracefully by starting with an empty dict.

        Returns:
            The loaded tracker data dict.
        """
        self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
        if self.tracker_path.exists():
            try:
                self._data = json.loads(self.tracker_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                log.error(
                    "tracker_corrupted_or_unreadable",
                    path=str(self.tracker_path),
                    error=str(exc),
                    exc_info=True,
                )
                self._data = {}
        else:
            self._data = {}
        return self._data

    def save(self) -> None:
        """Save tracker data to the JSON file atomically and durably.

        Writes via ``atomic_write_json`` (tmp + fsync + rename + parent
        dir fsync) so the result survives a crash mid-write. Logs an
        error on write failure instead of crashing the ingest loop.
        """
        tmp_path = self.tracker_path.with_suffix(self.tracker_path.suffix + ".tmp")
        try:
            atomic_write_json(self.tracker_path, self._data)
        except OSError as e:
            log.error("tracker_save_failed", path=str(self.tracker_path), error=str(e))
            tmp_path.unlink(missing_ok=True)

    def is_ingested(self, torrent_hash: str) -> bool:
        """Check if a torrent has already been ingested.

        Args:
            torrent_hash: The torrent hash to check.

        Returns:
            True if the hash exists in the tracker.
        """
        return torrent_hash in self._data

    def get_entry(self, torrent_hash: str) -> dict[str, Any] | None:
        """Return the tracker dict for a torrent hash, or ``None`` if absent.

        Used by the orphan-detection probe in
        :func:`personalscraper.ingest.ingest._torrent_present_downstream` to
        read back the recorded ``dest_path`` (when present) without relying
        on a separate filename heuristic.

        Args:
            torrent_hash: Torrent hash to look up.

        Returns:
            The full entry dict (``name``, ``action``, ``date``,
            optionally ``dest_path``) or ``None`` when the hash is unknown.
        """
        entry = self._data.get(torrent_hash)
        return dict(entry) if entry is not None else None

    def mark_ingested(
        self,
        torrent_hash: str,
        torrent_name: str,
        action: str,
        dest_path: str | None = None,
    ) -> None:
        """Record a torrent as ingested and persist to disk.

        Args:
            torrent_hash: The torrent hash identifier.
            torrent_name: Human-readable torrent name.
            action: Transfer action performed ("copied" or "moved").
            dest_path: Optional absolute path the content was written to
                (typically inside ``097-TEMP``). When set, future ingest
                runs cross-check this path's existence to detect orphan
                tracker entries left behind by a silent dispatch failure.
        """
        entry: dict[str, Any] = {
            "name": torrent_name,
            "action": action,
            "date": datetime.now().isoformat(),
        }
        if dest_path is not None:
            entry["dest_path"] = dest_path
        self._data[torrent_hash] = entry
        self.save()
        log.info(
            "torrent_marked",
            hash=torrent_hash,
            name=torrent_name,
            action=action,
            dest_path=dest_path,
        )

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

    def prune_consumed_dest_paths(self, ingest_dir: Path) -> int:
        """Drop stale ``dest_path`` keys after sort consumes the ingest copy.

        Removes ``dest_path`` keys whose recorded file inside the ingest
        staging directory has been moved away by a downstream step.

        After ``ingest`` writes a fresh copy under ``097-TEMP`` it records
        ``dest_path = 097-TEMP/<file>`` so a future probe can detect a
        silent dispatch failure (the file disappears without ending up on
        a storage disk). Once ``sort`` actually consumes the file and
        moves it into a category dir (``002-TVSHOWS/<show>/...``) the
        recorded path no longer exists — but it stays in the JSON forever
        unless we prune it. This method removes those stale dest_path
        keys without touching the hash entry itself, so the tracker
        keeps remembering the torrent was ingested while no longer
        carrying a misleading recorded path.

        Args:
            ingest_dir: Absolute path of the ingest staging dir
                (typically ``097-TEMP``). Only dest_paths inside this
                root are considered for pruning — paths outside it
                represent final-destination state we want to preserve.

        Returns:
            Number of entries whose ``dest_path`` field was removed.
        """
        try:
            ingest_root = ingest_dir.resolve()
        except OSError:
            return 0
        pruned = 0
        for entry in self._data.values():
            raw = entry.get("dest_path")
            if not isinstance(raw, str) or not raw:
                continue
            dest = Path(raw)
            if dest.exists():
                continue
            try:
                dest.resolve().relative_to(ingest_root)
            except (OSError, ValueError):
                # Outside the staging dir — not consumed by sort, keep
                # the orphan signal intact.
                continue
            del entry["dest_path"]
            pruned += 1
        if pruned:
            self.save()
            log.info("tracker_dest_path_pruned", removed=pruned)
        return pruned
