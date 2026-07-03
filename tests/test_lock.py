"""Tests for personalscraper.lock — PID-based pipeline lock file."""

import os

from personalscraper.lock import acquire_lock, is_lock_held, release_lock


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


def test_toctou_race_lost(tmp_path, monkeypatch):
    """Simulate the narrow race between exists() and O_CREAT|O_EXCL.

    Pre-create the lock file after forcing exists() to report False, so
    acquire_lock passes the stale-check path and reaches os.open(),
    which fails with FileExistsError — the code path that keeps two
    racing processes from both thinking they own the lock.
    """
    lock_file = tmp_path / "pipeline.lock"
    # Competitor PID owns the lock from their perspective
    lock_file.write_text(str(os.getpid() + 1))

    from pathlib import Path as _Path

    real_exists = _Path.exists

    def _fake_exists(self, *args, **kwargs):
        # Hide the lock from the stale-check phase only, keep default
        # behaviour for every other path (mkdir -> exists_ok handling etc.)
        if self == lock_file:
            return False
        return real_exists(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "exists", _fake_exists)

    assert acquire_lock(lock_file) is False
    # Competitor's lock content is preserved — we did not overwrite it
    assert lock_file.read_text().strip() == str(os.getpid() + 1)


def test_default_lock_file_uses_config(tmp_path, monkeypatch):
    """_default_lock_file derives lock path from configured paths.data_dir."""
    from unittest.mock import MagicMock

    fake_config = MagicMock()
    fake_config.paths.data_dir = tmp_path / "data"

    monkeypatch.setattr("personalscraper.conf.loader.resolve_config_path", lambda: tmp_path / "config")
    monkeypatch.setattr("personalscraper.conf.loader.load_config", lambda _path: fake_config)

    from personalscraper.lock import _default_lock_file

    result = _default_lock_file()
    assert result == tmp_path / "data" / "pipeline.lock"


def test_acquire_lock_uses_default_when_none(tmp_path, monkeypatch):
    """acquire_lock(None) falls back to _default_lock_file()."""
    target = tmp_path / "default.lock"

    monkeypatch.setattr("personalscraper.lock._default_lock_file", lambda: target)

    assert acquire_lock(None) is True
    assert target.exists()
    # Cleanup via release_lock(None) — also exercises default path
    monkeypatch.setattr("personalscraper.lock._default_lock_file", lambda: target)
    release_lock(None)
    assert not target.exists()


def test_acquire_lock_permission_error_other_user(tmp_path, monkeypatch):
    """A live lock owned by another user (PermissionError on os.kill) blocks acquisition."""
    lock_file = tmp_path / "pipeline.lock"
    lock_file.write_text("12345")

    def _raise_permission(_pid, _sig):
        raise PermissionError("not allowed")

    monkeypatch.setattr("personalscraper.lock.os.kill", _raise_permission)

    assert acquire_lock(lock_file) is False
    # Lock file untouched
    assert lock_file.read_text().strip() == "12345"


# ---------------------------------------------------------------------------
# is_lock_held — read-only probe (5 direct tests)
# ---------------------------------------------------------------------------


def test_is_lock_held_missing_file_returns_false(tmp_path):
    """is_lock_held returns False when the lock file does not exist."""
    lock_file = tmp_path / "pipeline.lock"
    assert is_lock_held(lock_file) is False


def test_is_lock_held_corrupt_pid_returns_false(tmp_path):
    """is_lock_held returns False when the lock file contains non-integer text."""
    lock_file = tmp_path / "pipeline.lock"
    lock_file.write_text("not_a_number")
    assert is_lock_held(lock_file) is False


def test_is_lock_held_stale_dead_pid_returns_false(tmp_path, monkeypatch):
    """is_lock_held returns False when the stored PID belongs to a dead process."""
    lock_file = tmp_path / "pipeline.lock"
    lock_file.write_text(str(os.getpid()))

    def _raise_process_lookup(_pid, _sig):
        raise ProcessLookupError("no such process")

    monkeypatch.setattr("personalscraper.lock.os.kill", _raise_process_lookup)
    assert is_lock_held(lock_file) is False


def test_is_lock_held_live_pid_returns_true(tmp_path):
    """is_lock_held returns True when the stored PID is the current process."""
    lock_file = tmp_path / "pipeline.lock"
    lock_file.write_text(str(os.getpid()))
    assert is_lock_held(lock_file) is True


def test_is_lock_held_permission_error_returns_true(tmp_path, monkeypatch):
    """is_lock_held returns True on PermissionError — lock held by another user."""
    lock_file = tmp_path / "pipeline.lock"
    lock_file.write_text("12345")

    def _raise_permission(_pid, _sig):
        raise PermissionError("not allowed")

    monkeypatch.setattr("personalscraper.lock.os.kill", _raise_permission)
    assert is_lock_held(lock_file) is True


def test_is_lock_held_oserror_read_failure_returns_false(tmp_path, monkeypatch):
    """is_lock_held returns False on OSError from read_text and logs lock_read_failed.

    Regression test for the watcher loop's is_lock_held probe: when the lock
    file exists but read_text raises OSError (I/O error, not a corrupt PID),
    is_lock_held must return False and log lock_read_failed rather than
    letting the exception propagate to the daemon loop.
    """
    from pathlib import Path as _Path

    lock_file = tmp_path / "pipeline.lock"
    lock_file.write_text("12345")

    real_read_text = _Path.read_text

    def _fake_read_text(self, *args, **kwargs):
        if self == lock_file:
            raise OSError(5, "Input/output error")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "read_text", _fake_read_text)

    assert is_lock_held(lock_file) is False
