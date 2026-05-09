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


def test_default_tracker_file_uses_loaded_config(tmp_path, monkeypatch):
    """``_default_tracker_file`` resolves the path from Config.paths.data_dir.

    Covers lines 34-37 (the lazy import + load_config path) and line 58
    (constructor default branch when ``tracker_path is None``).
    """
    from unittest.mock import MagicMock

    from personalscraper.ingest import tracker as tracker_module

    fake_config = MagicMock()
    fake_config.paths.data_dir = tmp_path / "data"
    (tmp_path / "data").mkdir(parents=True)

    fake_loader = MagicMock(return_value=fake_config)

    # The tracker imports load_config + resolve_config_path lazily inside
    # _default_tracker_file, so patch the loader module itself.
    import personalscraper.conf.loader as loader_mod

    monkeypatch.setattr(loader_mod, "load_config", fake_loader)
    monkeypatch.setattr(loader_mod, "resolve_config_path", lambda: tmp_path / "config")

    resolved = tracker_module._default_tracker_file()
    assert resolved == fake_config.paths.data_dir / "ingested_torrents.json"

    # Constructor with tracker_path=None should hit the same default branch.
    t = IngestTracker(None)
    assert t.tracker_path == fake_config.paths.data_dir / "ingested_torrents.json"


def test_save_oserror_logs_and_cleans_tmp(tmp_path, caplog):
    """A failing atomic write logs an error and unlinks the tmp file.

    Covers lines 98-100 — the OSError handler in ``IngestTracker.save``.
    """
    import logging as _logging
    from unittest.mock import patch

    tracker_path = tmp_path / "ingested.json"
    tracker = IngestTracker(tracker_path)

    # Pre-create the tmp file so unlink(missing_ok=True) gets a real target.
    tmp_marker = tracker_path.with_suffix(tracker_path.suffix + ".tmp")
    tmp_marker.write_text("{}")

    with patch("personalscraper.ingest.tracker.atomic_write_json", side_effect=OSError("disk full")):
        with caplog.at_level(_logging.ERROR, logger="tracker"):
            tracker.save()

    events = [r.msg for r in caplog.records if isinstance(r.msg, dict)]
    assert any(e.get("event") == "tracker_save_failed" for e in events)
    assert not tmp_marker.exists()


def test_prune_consumed_dest_paths_resolve_oserror_returns_zero(tmp_path):
    """When ingest_dir.resolve() fails, prune returns 0 without modifying state.

    Covers lines 211-212.
    """
    from unittest.mock import patch

    tracker = IngestTracker(tmp_path / "ingested.json")
    tracker.mark_ingested("h1", "Movie", "moved", dest_path=str(tmp_path / "missing"))

    ingest_dir = tmp_path / "097-TEMP"
    ingest_dir.mkdir()

    with patch.object(type(ingest_dir), "resolve", side_effect=OSError("denied")):
        pruned = tracker.prune_consumed_dest_paths(ingest_dir)

    assert pruned == 0
    # Entry untouched
    entry = tracker.get_entry("h1")
    assert entry is not None
    assert entry.get("dest_path") == str(tmp_path / "missing")


def test_prune_consumed_dest_paths_skips_non_string_dest(tmp_path):
    """Entries whose dest_path is missing/empty/non-string are skipped.

    Covers line 217 (the ``continue`` for malformed dest_path).
    """
    tracker_path = tmp_path / "ingested.json"
    # Pre-write a tracker file with a malformed dest_path entry.
    payload = {
        "h_empty": {
            "name": "EmptyDest",
            "action": "moved",
            "date": "2026-01-01T00:00:00",
            "dest_path": "",
        },
        "h_none": {
            "name": "NoDest",
            "action": "moved",
            "date": "2026-01-01T00:00:00",
        },
    }
    tracker_path.write_text(json.dumps(payload))

    tracker = IngestTracker(tracker_path)
    ingest_dir = tmp_path / "097-TEMP"
    ingest_dir.mkdir()

    pruned = tracker.prune_consumed_dest_paths(ingest_dir)

    assert pruned == 0
    # Entries are still there, untouched.
    assert tracker.is_ingested("h_empty")
    assert tracker.is_ingested("h_none")
