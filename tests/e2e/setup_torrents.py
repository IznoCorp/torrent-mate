"""E2E torrent setup — add test magnets to qBittorrent and wait for download.

Uses the 'e2e-test' category to isolate test torrents from real ones.
All added torrents are registered for cleanup tracking.
"""

import json
import logging
import time
from pathlib import Path

from tests.e2e.registry import TestRegistry

logger = logging.getLogger(__name__)

# Default polling interval and timeout for torrent completion
_POLL_INTERVAL = 30  # seconds
_DEFAULT_TIMEOUT = 3600  # 1 hour


class TorrentSetup:
    """Add test magnets to qBittorrent and wait for download completion.

    Attributes:
        client: qBittorrent API client.
        registry: TestRegistry for tracking created resources.
        timeout: Maximum wait time per torrent in seconds.
    """

    def __init__(self, client, registry: TestRegistry, timeout: int = _DEFAULT_TIMEOUT) -> None:
        """Initialize torrent setup.

        Args:
            client: qbittorrentapi.Client instance (connected).
            registry: TestRegistry for tracking hashes and paths.
            timeout: Seconds to wait for each torrent to complete.
        """
        self.client = client
        self.registry = registry
        self.timeout = timeout

    def load_magnets(self, config_path: Path) -> list[dict]:
        """Load and validate test magnet configuration.

        Args:
            config_path: Path to test_magnets.json.

        Returns:
            List of magnet dicts with keys: name, magnet, type, expected_category.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If a magnet entry is missing required fields.
        """
        data = json.loads(config_path.read_text())
        required = {"name", "magnet", "type", "expected_category"}
        for entry in data:
            missing = required - set(entry.keys())
            if missing:
                raise ValueError(f"Magnet '{entry.get('name', '?')}' missing fields: {missing}")
        return data

    def add_magnets(self, magnets: list[dict], category: str = "e2e-test") -> list[str]:
        """Add magnets to qBittorrent with a dedicated test category.

        The category allows cleanup to identify and remove test torrents
        without affecting real downloads.

        Args:
            magnets: List of magnet dicts (must have 'magnet' key).
            category: qBittorrent category for test torrents.

        Returns:
            List of info hashes for the added torrents.
        """
        hashes = []
        for m in magnets:
            self.client.torrents_add(urls=m["magnet"], category=category)
            logger.info("Added magnet: %s (category=%s)", m["name"], category)

        # Give qBit a moment to register the torrents
        time.sleep(2)

        # Retrieve hashes for torrents in the test category
        for t in self.client.torrents_info(category=category):
            h = t.hash
            hashes.append(h)
            self.registry.register_torrent(h)
            logger.info("Registered torrent hash: %s", h)

        return hashes

    def wait_for_completion(self, hashes: list[str]) -> dict[str, bool]:
        """Wait for all test torrents to finish downloading.

        Polls qBittorrent every 30 seconds until all torrents complete
        or the timeout expires.

        Args:
            hashes: Info hashes to monitor.

        Returns:
            Dict mapping hash to completion status (True=completed).
        """
        status = {h: False for h in hashes}
        deadline = time.time() + self.timeout

        while time.time() < deadline and not all(status.values()):
            for t in self.client.torrents_info():
                if t.hash in status and t.state_enum.is_complete:
                    status[t.hash] = True
                    logger.info("Torrent completed: %s", t.name)

            if all(status.values()):
                break

            remaining = int(deadline - time.time())
            logger.info(
                "Waiting for torrents... %d/%d complete, %ds remaining",
                sum(status.values()), len(status), remaining,
            )
            time.sleep(_POLL_INTERVAL)

        return status

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
