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


def test_prune_consumed_dest_paths_removes_stale_within_ingest(tmp_path):
    """Drop stale dest_path keys whose recorded file is gone.

    ``prune_consumed_dest_paths`` clears dest_path keys whose recorded
    file inside the ingest staging dir has already been moved by sort.
    """
    from personalscraper.ingest.tracker import IngestTracker

    ingest_dir = tmp_path / "097-TEMP"
    ingest_dir.mkdir()
    consumed_path = ingest_dir / "Show.S01E01.mkv"
    # Note: the file is INTENTIONALLY NOT created — sort already consumed it.

    tracker_path = tmp_path / "ingested.json"
    tracker = IngestTracker(tracker_path)
    tracker.mark_ingested("h1", "Show.S01E01", "copied", dest_path=str(consumed_path))

    pruned = tracker.prune_consumed_dest_paths(ingest_dir)

    assert pruned == 1
    entry = tracker.get_entry("h1")
    assert entry is not None
    assert "dest_path" not in entry
    # Hash-level memory of the torrent stays — only the path field is cleared.
    assert tracker.is_ingested("h1")


def test_prune_consumed_dest_paths_keeps_outside_ingest(tmp_path):
    """Preserve final-destination orphan signal outside ingest dir.

    A dest_path OUTSIDE the ingest dir means the file was placed on a
    storage disk; if that path disappears, it's a real orphan signal —
    pruning would silence it. Must NOT prune.
    """
    from personalscraper.ingest.tracker import IngestTracker

    ingest_dir = tmp_path / "097-TEMP"
    ingest_dir.mkdir()
    final_dest = tmp_path / "Disk1" / "movies" / "Movie (2024)" / "Movie.mkv"
    # Final dest is missing — orphan signal we want to preserve.

    tracker = IngestTracker(tmp_path / "ingested.json")
    tracker.mark_ingested("h1", "Movie", "moved", dest_path=str(final_dest))

    pruned = tracker.prune_consumed_dest_paths(ingest_dir)

    assert pruned == 0
    entry = tracker.get_entry("h1")
    assert entry is not None
    assert entry.get("dest_path") == str(final_dest)


def test_prune_consumed_dest_paths_keeps_existing_files(tmp_path):
    """Keep dest_path entries whose file still exists.

    A dest_path that still exists (sort has not yet run) must not be
    pruned — the path is still meaningful for orphan detection.
    """
    from personalscraper.ingest.tracker import IngestTracker

    ingest_dir = tmp_path / "097-TEMP"
    ingest_dir.mkdir()
    fresh = ingest_dir / "Fresh.mkv"
    fresh.write_bytes(b"x")

    tracker = IngestTracker(tmp_path / "ingested.json")
    tracker.mark_ingested("h1", "Fresh", "copied", dest_path=str(fresh))

    pruned = tracker.prune_consumed_dest_paths(ingest_dir)

    assert pruned == 0
    entry = tracker.get_entry("h1")
    assert entry is not None
    assert entry.get("dest_path") == str(fresh)
