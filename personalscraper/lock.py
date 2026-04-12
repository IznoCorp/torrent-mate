"""Pipeline lock file — prevents concurrent pipeline executions.

Uses a PID-based lock file in ~/.personalscraper/ to ensure only one
pipeline instance runs at a time. Detects and cleans up stale locks
from crashed processes.

Lock is acquired at CLI command level (not in run_*() functions)
to avoid double-lock when the `run` command calls individual steps.
"""

import os
from pathlib import Path

from personalscraper.logger import get_logger

LOCK_DIR = Path("~/.personalscraper").expanduser()
LOCK_FILE = LOCK_DIR / "pipeline.lock"

log = get_logger("lock")


def acquire_lock(lock_file: Path = LOCK_FILE) -> bool:
    """Create a lock file with the current process PID.

    Checks for existing locks and handles stale ones (dead process)
    or locks held by other users (PermissionError on os.kill).
    Creates parent directory if it doesn't exist.

    Args:
        lock_file: Path to the lock file. Defaults to ~/.personalscraper/pipeline.lock.

    Returns:
        True if lock was acquired, False if another live instance holds it.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    if lock_file.exists():
        try:
            stored_pid = int(lock_file.read_text().strip())
        except ValueError:
            # Corrupt PID file — remove stale lock
            log.info("stale_lock_removed", lock_file=str(lock_file))
            lock_file.unlink(missing_ok=True)
        else:
            try:
                os.kill(stored_pid, 0)
                # Process is alive → lock is valid
                log.warning("lock_held", pid=stored_pid, lock_file=str(lock_file))
                return False
            except ProcessLookupError:
                # Process dead → stale lock, safe to remove
                log.info("stale_lock_removed", lock_file=str(lock_file))
                lock_file.unlink(missing_ok=True)
            except PermissionError:
                # Process exists but owned by another user — treat as live
                log.warning("lock_held_other_user", pid=stored_pid, lock_file=str(lock_file))
                return False

    lock_file.write_text(str(os.getpid()))
    log.debug("lock_acquired", pid=os.getpid(), lock_file=str(lock_file))
    return True


def release_lock(lock_file: Path = LOCK_FILE) -> None:
    """Remove the lock file.

    Args:
        lock_file: Path to the lock file. Defaults to ~/.personalscraper/pipeline.lock.
    """
    lock_file.unlink(missing_ok=True)
    log.debug("lock_released", lock_file=str(lock_file))
