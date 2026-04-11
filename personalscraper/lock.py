"""Pipeline lock file — prevents concurrent executions."""

import os
from pathlib import Path

from personalscraper.logger import get_logger

LOCK_DIR = Path("~/.personalscraper").expanduser()
LOCK_FILE = LOCK_DIR / "pipeline.lock"

log = get_logger("lock")


def acquire_lock(lock_file: Path = LOCK_FILE) -> bool:
    """Create a lock file with the current process PID.

    If a lock already exists:
    - Read the stored PID
    - Check if the process is still alive (os.kill(pid, 0))
    - If dead → remove stale lock, take new one
    - If alive → return False (another run is in progress)

    Returns True if lock acquired, False if another instance is running.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    if lock_file.exists():
        try:
            stored_pid = int(lock_file.read_text().strip())
            os.kill(stored_pid, 0)
            # Process is alive → lock is valid
            log.warning("lock_held", pid=stored_pid, lock_file=str(lock_file))
            return False
        except (ValueError, ProcessLookupError, PermissionError):
            # PID invalid or process dead → stale lock
            log.info("stale_lock_removed", lock_file=str(lock_file))
            lock_file.unlink(missing_ok=True)

    lock_file.write_text(str(os.getpid()))
    log.debug("lock_acquired", pid=os.getpid(), lock_file=str(lock_file))
    return True


def release_lock(lock_file: Path = LOCK_FILE) -> None:
    """Remove the lock file."""
    lock_file.unlink(missing_ok=True)
    log.debug("lock_released", lock_file=str(lock_file))
