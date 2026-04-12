"""E2E torrent setup — add .torrent files to qBittorrent and wait for download.

Uses the 'e2e-test' category to isolate test torrents from real ones.
All added torrents are registered for cleanup tracking.
"""

import logging
import time
from pathlib import Path

from tests.e2e.registry import TestRegistry

logger = logging.getLogger(__name__)

# Polling interval for torrent completion checks
_POLL_INTERVAL = 60  # check every minute


class TorrentSetup:
    """Add .torrent files to qBittorrent and wait for download completion.

    Attributes:
        client: qBittorrent API client.
        registry: TestRegistry for tracking created resources.
        timeout: Maximum wait time for all torrents in seconds.
    """

    def __init__(self, client, registry: TestRegistry) -> None:
        """Initialize torrent setup.

        Args:
            client: qbittorrentapi.Client instance (connected).
            registry: TestRegistry for tracking hashes and paths.
        """
        self.client = client
        self.registry = registry

    def add_torrent_files(
        self, torrent_files: list[Path], category: str = "e2e-test",
    ) -> list[str]:
        """Add .torrent files to qBittorrent with a dedicated test category.

        The category allows cleanup to identify and remove test torrents
        without affecting real downloads.

        Args:
            torrent_files: List of paths to .torrent files.
            category: qBittorrent category for test torrents.

        Returns:
            List of info hashes for the added torrents.
        """
        for f in torrent_files:
            self.client.torrents_add(torrent_files=f, category=category)
            logger.info("Added torrent file: %s (category=%s)", f.name, category)

        # Give qBit a moment to register the torrents
        time.sleep(2)

        # Retrieve hashes for torrents in the test category
        hashes = []
        for t in self.client.torrents_info(category=category):
            h = t.hash
            hashes.append(h)
            self.registry.register_torrent(h)
            logger.info("Registered: %s [%s]", t.name, h[:12])

        return hashes

    def wait_for_completion(self, hashes: list[str]) -> None:
        """Wait for all test torrents to finish downloading.

        Polls qBittorrent every 60 seconds until ALL torrents are complete.
        No timeout — waits as long as needed (private trackers can be slow).
        Logs progress each minute with per-torrent download percentage.

        Args:
            hashes: Info hashes to monitor.

        Raises:
            KeyboardInterrupt: If the user interrupts (Ctrl+C).
        """
        pending = set(hashes)
        elapsed = 0

        while pending:
            for t in self.client.torrents_info():
                if t.hash in pending and t.state_enum.is_complete:
                    pending.discard(t.hash)
                    logger.info("Torrent completed: %s", t.name)

            if not pending:
                break

            # Log per-torrent progress
            for t in self.client.torrents_info():
                if t.hash in pending:
                    pct = t.progress * 100
                    speed = t.dlspeed / (1024 * 1024)
                    logger.info(
                        "  %s: %.1f%% (%.1f MB/s) [%s]",
                        t.name[:50], pct, speed, t.state_enum.name,
                    )
            logger.info(
                "Waiting... %d/%d remaining (%dm elapsed)",
                len(pending), len(hashes), elapsed // 60,
            )
            time.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

    def get_downloaded_paths(self, hashes: list[str]) -> list[Path]:
        """Get filesystem paths of downloaded torrent content.

        Args:
            hashes: Info hashes to look up.

        Returns:
            List of paths where torrent content was saved.
        """
        paths = []
        for t in self.client.torrents_info():
            if t.hash in hashes:
                paths.append(Path(t.content_path))
        return paths

    def get_torrent_names(self, hashes: list[str]) -> dict[str, str]:
        """Get torrent names by hash.

        Args:
            hashes: Info hashes to look up.

        Returns:
            Dict mapping hash to torrent name.
        """
        names = {}
        for t in self.client.torrents_info():
            if t.hash in hashes:
                names[t.hash] = t.name
        return names
