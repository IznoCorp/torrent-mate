import json
import time

from personalscraper.logger import cleanup_old_logs, configure_logging, get_logger


def test_configure_logging_creates_logs_dir(tmp_path, monkeypatch):
    """configure_logging creates logs/ directory if missing."""
    import personalscraper.logger as logger_mod

    monkeypatch.setattr(logger_mod, "LOGS_DIR", tmp_path / "logs")
    configure_logging()
    assert (tmp_path / "logs").exists()


def test_log_writes_json_file(tmp_path, monkeypatch):
    """Logging writes valid JSON Lines to the log file."""
    import personalscraper.logger as logger_mod

    logs_dir = tmp_path / "logs"
    monkeypatch.setattr(logger_mod, "LOGS_DIR", logs_dir)
    configure_logging()
    log = get_logger("test")
    log.info("test_event", key="value")

    log_file = logs_dir / "personalscraper.json"
    assert log_file.exists()
    line = log_file.read_text().strip().split("\n")[-1]
    data = json.loads(line)
    assert data["event"] == "test_event"
    assert data["key"] == "value"
    assert "timestamp" in data
    assert data["level"] == "info"


def test_cleanup_old_logs_deletes_old_files(tmp_path):
    """cleanup_old_logs removes files older than retention_days."""
    old_file = tmp_path / "old.json"
    new_file = tmp_path / "new.json"
    old_file.write_text("old")
    new_file.write_text("new")

    # Make old_file appear 60 days old
    old_time = time.time() - (60 * 86400)
    import os

    os.utime(old_file, (old_time, old_time))

    deleted = cleanup_old_logs(tmp_path, retention_days=30)
    assert deleted == 1
    assert not old_file.exists()
    assert new_file.exists()


def test_cleanup_old_logs_empty_dir(tmp_path):
    """cleanup_old_logs handles empty directory."""
    deleted = cleanup_old_logs(tmp_path, retention_days=30)
    assert deleted == 0


def test_cleanup_old_logs_missing_dir(tmp_path):
    """cleanup_old_logs handles missing directory."""
    deleted = cleanup_old_logs(tmp_path / "nonexistent", retention_days=30)
    assert deleted == 0
