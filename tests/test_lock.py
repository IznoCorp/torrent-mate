"""Tests for personalscraper.lock — PID-based pipeline lock file."""

import os

from personalscraper.lock import acquire_lock, release_lock


def test_acquire_creates_lock(tmp_path):
    """acquire_lock creates a lock file containing the current PID."""
    lock_file = tmp_path / "pipeline.lock"
    assert acquire_lock(lock_file)
    assert lock_file.exists()
    assert lock_file.read_text().strip() == str(os.getpid())


def test_release_removes_lock(tmp_path):
    """release_lock deletes the lock file."""
    lock_file = tmp_path / "pipeline.lock"
    acquire_lock(lock_file)
    release_lock(lock_file)
    assert not lock_file.exists()


def test_stale_lock_detected(tmp_path):
    """A lock from a dead process is treated as stale and overwritten."""
    lock_file = tmp_path / "pipeline.lock"
    lock_file.write_text("999999999")  # Non-existent PID
    assert acquire_lock(lock_file)
    assert lock_file.read_text().strip() == str(os.getpid())


def test_live_lock_blocks(tmp_path):
    """A lock from a live process (ourselves) blocks acquisition."""
    lock_file = tmp_path / "pipeline.lock"
    lock_file.write_text(str(os.getpid()))  # Our own PID — alive
    assert not acquire_lock(lock_file)


def test_release_missing_file(tmp_path):
    """Releasing a non-existent lock does not raise."""
    lock_file = tmp_path / "pipeline.lock"
    release_lock(lock_file)  # Should not raise


def test_acquire_creates_parent_dir(tmp_path):
    """acquire_lock creates parent directory if missing."""
    lock_file = tmp_path / "subdir" / "pipeline.lock"
    assert acquire_lock(lock_file)
    assert lock_file.exists()


def test_invalid_pid_in_lock(tmp_path):
    """A lock with invalid content is treated as stale."""
    lock_file = tmp_path / "pipeline.lock"
    lock_file.write_text("not_a_number")
    assert acquire_lock(lock_file)
