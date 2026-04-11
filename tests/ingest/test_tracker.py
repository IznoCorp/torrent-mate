"""Tests for personalscraper.ingest.tracker — IngestTracker persistence."""

import json

from personalscraper.ingest.tracker import IngestTracker


def test_mark_and_check(tmp_path):
    """mark_ingested records a hash and is_ingested finds it."""
    tracker = IngestTracker(tmp_path / "tracker.json")
    tracker.mark_ingested("abc123", "The.Boys.S05E01", "copied")
    assert tracker.is_ingested("abc123")
    assert not tracker.is_ingested("unknown")


def test_persistence_across_instances(tmp_path):
    """Data persists when creating a new IngestTracker with the same file."""
    path = tmp_path / "tracker.json"
    t1 = IngestTracker(path)
    t1.mark_ingested("abc123", "Test", "moved")

    t2 = IngestTracker(path)
    assert t2.is_ingested("abc123")


def test_cleanup_removes_stale(tmp_path):
    """Cleanup removes entries not in the active_hashes set."""
    tracker = IngestTracker(tmp_path / "tracker.json")
    tracker.mark_ingested("keep1", "Keep1", "copied")
    tracker.mark_ingested("keep2", "Keep2", "moved")
    tracker.mark_ingested("stale1", "Stale1", "copied")

    removed = tracker.cleanup(active_hashes={"keep1", "keep2"})
    assert removed == 1
    assert tracker.is_ingested("keep1")
    assert tracker.is_ingested("keep2")
    assert not tracker.is_ingested("stale1")


def test_cleanup_no_stale(tmp_path):
    """Cleanup returns 0 when all entries are still active."""
    tracker = IngestTracker(tmp_path / "tracker.json")
    tracker.mark_ingested("abc", "Test", "copied")
    removed = tracker.cleanup(active_hashes={"abc"})
    assert removed == 0


def test_corrupted_json_recovers(tmp_path):
    """A corrupted JSON file is handled gracefully (starts fresh)."""
    path = tmp_path / "tracker.json"
    path.write_text("{invalid json!!")
    tracker = IngestTracker(path)
    assert not tracker.is_ingested("anything")


def test_missing_file_starts_empty(tmp_path):
    """A missing tracker file starts with an empty tracker."""
    tracker = IngestTracker(tmp_path / "nonexistent" / "tracker.json")
    assert not tracker.is_ingested("anything")


def test_atomic_save(tmp_path):
    """Save writes valid JSON that can be re-loaded."""
    path = tmp_path / "tracker.json"
    tracker = IngestTracker(path)
    tracker.mark_ingested("h1", "Name1", "copied")
    tracker.mark_ingested("h2", "Name2", "moved")

    data = json.loads(path.read_text())
    assert "h1" in data
    assert data["h1"]["name"] == "Name1"
    assert data["h2"]["action"] == "moved"
    assert "date" in data["h1"]
