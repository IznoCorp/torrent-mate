"""E2E test registry — tracks all files and torrents created during a test session.

Persists to JSON so cleanup can recover from crashes or interrupted sessions.
Registry file lives in the project data directory (settings.data_dir).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path


def _default_registry_dir() -> Path:
    """Return the default registry directory from settings.

    Returns:
        Path to the configured data directory.
    """
    # ``data_dir`` migrated from ``Settings`` to ``Config.paths`` in P6.1.
    from personalscraper.conf.loader import load_config, resolve_config_path

    return load_config(resolve_config_path()).paths.data_dir


@dataclass
class TestRegistry:
    """Tracks all paths and torrent hashes created by an E2E test session.

    Persists immediately on every register() call so that cleanup can
    recover even if the test crashes mid-pipeline.

    Attributes:
        session_id: UUID unique to this test session.
        base_dir: Directory where registry JSON is stored.
        created_paths: Filesystem paths created by the test (in creation order).
        torrent_hashes: qBittorrent info hashes added by the test.
    """

    session_id: str
    base_dir: Path = field(default_factory=_default_registry_dir)
    created_paths: list[str] = field(default_factory=list)
    torrent_hashes: list[str] = field(default_factory=list)

    @property
    def registry_path(self) -> Path:
        """Path to the JSON registry file for this session.

        Returns:
            Path to {base_dir}/e2e-test-registry-{uuid}.json.
        """
        return self.base_dir / f"e2e-test-registry-{self.session_id}.json"

    def register(self, path: Path) -> None:
        """Register a filesystem path created by the test.

        Persists immediately to JSON so crash recovery works.

        Args:
            path: Absolute path to the created file or directory.
        """
        path_str = str(path.resolve())
        if path_str not in self.created_paths:
            self.created_paths.append(path_str)
            self.save()

    def register_torrent(self, torrent_hash: str) -> None:
        """Register a torrent hash added to qBittorrent.

        Args:
            torrent_hash: Info hash of the torrent.
        """
        if torrent_hash not in self.torrent_hashes:
            self.torrent_hashes.append(torrent_hash)
            self.save()

    def save(self) -> None:
        """Persist the registry to JSON.

        Creates the parent directory if it doesn't exist.
        """
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "created_paths": self.created_paths,
            "torrent_hashes": self.torrent_hashes,
        }
        self.registry_path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, registry_path: Path) -> "TestRegistry":
        """Load an existing registry from JSON.

        Args:
            registry_path: Path to the JSON registry file.

        Returns:
            A TestRegistry instance with the loaded data.

        Raises:
            FileNotFoundError: If the registry file doesn't exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        data = json.loads(registry_path.read_text())
        reg = cls(
            session_id=data["session_id"],
            base_dir=registry_path.parent,
        )
        reg.created_paths = data.get("created_paths", [])
        reg.torrent_hashes = data.get("torrent_hashes", [])
        return reg

    def get_cleanup_order(self) -> list[Path]:
        """Return registered paths in reverse order (children first).

        Cleanup must delete children before parents to avoid
        "directory not empty" errors.

        Returns:
            List of Path objects in reverse registration order.
        """
        return [Path(p) for p in reversed(self.created_paths)]

    def contains(self, path: Path) -> bool:
        """Check if a path is registered.

        Args:
            path: Path to check.

        Returns:
            True if the path (resolved) is in the registry.
        """
        return str(path.resolve()) in self.created_paths

    def cleanup(self) -> None:
        """Delete the registry JSON file itself.

        Call this after all tracked files have been cleaned up.
        """
        if self.registry_path.exists():
            self.registry_path.unlink()
