"""Tests for E2E test markers — placement, verification, and lifecycle."""

import shutil

from tests.e2e.markers import (
    MARKER_FILENAME,
    find_orphan_markers,
    place_marker,
    verify_marker,
)
from tests.e2e.registry import TestRegistry


class TestPlaceMarker:
    """Tests for place_marker()."""

    def test_creates_marker_file(self, tmp_path):
        """place_marker creates the marker file with session_id content."""
        test_dir = tmp_path / "movie"
        test_dir.mkdir()
        place_marker(test_dir, "uuid-abc")

        marker = test_dir / MARKER_FILENAME
        assert marker.exists()
        assert marker.read_text() == "uuid-abc"


class TestVerifyMarker:
    """Tests for verify_marker() triple check."""

    def _make_registry(self, tmp_path, session_id, *dirs):
        """Helper: create a registry with given directories registered."""
        reg = TestRegistry(session_id=session_id, base_dir=tmp_path)
        for d in dirs:
            reg.register(d)
        return reg

    def test_all_checks_pass(self, tmp_path):
        """Returns True when marker exists, UUID matches, and path in registry."""
        test_dir = tmp_path / "good"
        test_dir.mkdir()
        place_marker(test_dir, "session-1")
        reg = self._make_registry(tmp_path, "session-1", test_dir)

        assert verify_marker(test_dir, "session-1", reg) is True

    def test_fails_no_marker(self, tmp_path):
        """Returns False when marker file is missing."""
        test_dir = tmp_path / "nomarker"
        test_dir.mkdir()
        reg = self._make_registry(tmp_path, "session-1", test_dir)

        assert verify_marker(test_dir, "session-1", reg) is False

    def test_fails_wrong_uuid(self, tmp_path):
        """Returns False when marker has a different session_id."""
        test_dir = tmp_path / "wronguuid"
        test_dir.mkdir()
        place_marker(test_dir, "session-OLD")
        reg = self._make_registry(tmp_path, "session-NEW", test_dir)

        assert verify_marker(test_dir, "session-NEW", reg) is False

    def test_fails_not_in_registry(self, tmp_path):
        """Returns False when directory is not in the registry."""
        test_dir = tmp_path / "unregistered"
        test_dir.mkdir()
        place_marker(test_dir, "session-1")
        # Empty registry (no paths registered)
        reg = TestRegistry(session_id="session-1", base_dir=tmp_path)

        assert verify_marker(test_dir, "session-1", reg) is False


class TestFindOrphanMarkers:
    """Tests for find_orphan_markers()."""

    def test_finds_orphan(self, tmp_path):
        """Finds a marker file left by a previous session."""
        orphan_dir = tmp_path / "old_movie"
        orphan_dir.mkdir()
        place_marker(orphan_dir, "old-session")

        result = find_orphan_markers([tmp_path])
        assert orphan_dir in result

    def test_finds_nested_orphan(self, tmp_path):
        """Finds a marker deep in a directory tree."""
        deep = tmp_path / "001-MOVIES" / "Movie Name (2024)"
        deep.mkdir(parents=True)
        place_marker(deep, "old-session")

        result = find_orphan_markers([tmp_path])
        assert deep in result

    def test_no_orphans(self, tmp_path):
        """Returns empty list when no markers exist."""
        (tmp_path / "clean_dir").mkdir()
        assert find_orphan_markers([tmp_path]) == []

    def test_skips_nonexistent_paths(self, tmp_path):
        """Gracefully handles non-existent base paths."""
        result = find_orphan_markers([tmp_path / "does_not_exist"])
        assert result == []


class TestMarkerLifecycle:
    """Critical test: verify markers survive all pipeline operations.

    Simulates the full journey of a marker through the pipeline:
    V2 sort (shutil.move), V3 rename (Path.rename), V5 dispatch (shutil.copytree).
    """

    def test_marker_survives_pipeline(self, tmp_path):
        """Marker survives move, rename, and copytree — full pipeline simulation."""
        session_id = "lifecycle-test-uuid"
        reg = TestRegistry(session_id=session_id, base_dir=tmp_path)

        # Setup: create a movie folder with a marker (simulates post-ingest state)
        original = tmp_path / "staging" / "The.Matrix.1999"
        original.mkdir(parents=True)
        (original / "The.Matrix.mkv").write_text("fake video")
        place_marker(original, session_id)
        reg.register(original)

        # V2 Sort: shutil.move (same FS = atomic rename)
        sorted_dir = tmp_path / "001-MOVIES" / "The.Matrix.1999"
        sorted_dir.parent.mkdir(parents=True)
        shutil.move(str(original), str(sorted_dir))
        reg.register(sorted_dir)

        assert (sorted_dir / MARKER_FILENAME).exists()
        assert (sorted_dir / MARKER_FILENAME).read_text() == session_id

        # V3 Scrape: Path.rename (add year to folder name)
        renamed_dir = sorted_dir.parent / "The Matrix (1999)"
        sorted_dir.rename(renamed_dir)
        reg.register(renamed_dir)

        assert (renamed_dir / MARKER_FILENAME).exists()
        assert (renamed_dir / MARKER_FILENAME).read_text() == session_id

        # V5 Dispatch: shutil.copytree (cross-filesystem copy)
        disk_dir = tmp_path / "Disk1" / "films" / "The Matrix (1999)"
        disk_dir.parent.mkdir(parents=True)
        shutil.copytree(str(renamed_dir), str(disk_dir))
        reg.register(disk_dir)

        assert (disk_dir / MARKER_FILENAME).exists()
        assert (disk_dir / MARKER_FILENAME).read_text() == session_id

        # Final verify: marker on disk passes triple check
        assert verify_marker(disk_dir, session_id, reg) is True
