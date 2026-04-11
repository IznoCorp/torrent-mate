"""Tests for E2E test registry — file tracking and persistence."""

import json

from tests.e2e.registry import TestRegistry


class TestTestRegistry:
    """Tests for TestRegistry dataclass."""

    def test_register_path(self, tmp_path):
        """register() adds a path and persists immediately."""
        reg = TestRegistry(session_id="test-uuid-123", base_dir=tmp_path)
        test_dir = tmp_path / "media"
        test_dir.mkdir()
        reg.register(test_dir)

        assert str(test_dir.resolve()) in reg.created_paths
        assert reg.registry_path.exists()

    def test_register_torrent(self, tmp_path):
        """register_torrent() adds a hash."""
        reg = TestRegistry(session_id="test-uuid-456", base_dir=tmp_path)
        reg.register_torrent("abc123def")
        assert "abc123def" in reg.torrent_hashes

    def test_no_duplicates(self, tmp_path):
        """Registering the same path/hash twice doesn't create duplicates."""
        reg = TestRegistry(session_id="test-uuid-789", base_dir=tmp_path)
        test_dir = tmp_path / "dup"
        test_dir.mkdir()
        reg.register(test_dir)
        reg.register(test_dir)
        assert len(reg.created_paths) == 1

        reg.register_torrent("hash1")
        reg.register_torrent("hash1")
        assert len(reg.torrent_hashes) == 1

    def test_save_and_load(self, tmp_path):
        """Registry persists to JSON and reloads correctly."""
        reg = TestRegistry(session_id="save-test", base_dir=tmp_path)
        test_dir = tmp_path / "saved"
        test_dir.mkdir()
        reg.register(test_dir)
        reg.register_torrent("hash-save")

        loaded = TestRegistry.load(reg.registry_path)
        assert loaded.session_id == "save-test"
        assert str(test_dir.resolve()) in loaded.created_paths
        assert "hash-save" in loaded.torrent_hashes

    def test_get_cleanup_order_reverses(self, tmp_path):
        """get_cleanup_order() returns paths in reverse (children first)."""
        reg = TestRegistry(session_id="order-test", base_dir=tmp_path)
        parent = tmp_path / "parent"
        parent.mkdir()
        child = parent / "child"
        child.mkdir()

        reg.register(parent)
        reg.register(child)

        order = reg.get_cleanup_order()
        assert order[0] == child.resolve()
        assert order[1] == parent.resolve()

    def test_contains(self, tmp_path):
        """contains() checks if a path is registered."""
        reg = TestRegistry(session_id="contains-test", base_dir=tmp_path)
        test_dir = tmp_path / "exists"
        test_dir.mkdir()
        reg.register(test_dir)

        assert reg.contains(test_dir) is True
        assert reg.contains(tmp_path / "nope") is False

    def test_cleanup_removes_registry_file(self, tmp_path):
        """cleanup() deletes the registry JSON file."""
        reg = TestRegistry(session_id="cleanup-test", base_dir=tmp_path)
        reg.save()
        assert reg.registry_path.exists()

        reg.cleanup()
        assert not reg.registry_path.exists()

    def test_json_format(self, tmp_path):
        """Saved JSON has the expected structure."""
        reg = TestRegistry(session_id="json-test", base_dir=tmp_path)
        reg.save()

        data = json.loads(reg.registry_path.read_text())
        assert data["session_id"] == "json-test"
        assert isinstance(data["created_paths"], list)
        assert isinstance(data["torrent_hashes"], list)

    def test_registry_path_uses_session_id(self, tmp_path):
        """registry_path includes the session UUID."""
        reg = TestRegistry(session_id="my-uuid", base_dir=tmp_path)
        assert "my-uuid" in reg.registry_path.name
