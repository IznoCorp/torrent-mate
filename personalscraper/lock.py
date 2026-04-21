"""Pipeline lock file — prevents concurrent pipeline executions.

Uses a PID-based lock file in the project data directory (configurable
via DATA_DIR_NAME in .env, defaults to .personalscraper/ under staging_dir).
Detects and cleans up stale locks from crashed processes.

Lock is acquired at CLI command level (not in run_*() functions)
to avoid double-lock when the `run` command calls individual steps.
"""

import os
from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("lock")


def _default_lock_file() -> Path:
    """Return the default lock file path from settings.

    Returns:
        Path to pipeline.lock inside the configured data directory.
    """
    from pathlib import Path as _Path

    from personalscraper.config import get_settings

    settings = get_settings()
    data_dir = _Path(getattr(settings, "data_dir", ".data"))
    return data_dir / "pipeline.lock"


def acquire_lock(lock_file: Path | None = None) -> bool:
    """Create a lock file with the current process PID.

    Checks for existing locks and handles stale ones (dead process)
    or locks held by other users (PermissionError on os.kill).
    Creates parent directory if it doesn't exist.

    Args:
        lock_file: Path to the lock file. Defaults to settings.data_dir/pipeline.lock.

    Returns:
        True if lock was acquired, False if another live instance holds it.
    """
    if lock_file is None:
        lock_file = _default_lock_file()
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

    # Atomic lock creation — O_CREAT|O_EXCL fails if file already exists,
    # closing the TOCTOU race window between exists() check and write.
    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        # Another process grabbed the lock between our stale check and now
        log.warning("lock_race_lost", lock_file=str(lock_file))
        return False
    log.debug("lock_acquired", pid=os.getpid(), lock_file=str(lock_file))
    return True


def release_lock(lock_file: Path | None = None) -> None:
    """Remove the lock file.

    Args:
        lock_file: Path to the lock file. Defaults to settings.data_dir/pipeline.lock.
    """
    if lock_file is None:
        lock_file = _default_lock_file()
    lock_file.unlink(missing_ok=True)
    log.debug("lock_released", lock_file=str(lock_file))
