"""Pipeline lock file — prevents concurrent pipeline executions.

Uses a PID-based lock file in the project data directory (configured
via ``paths.data_dir`` in config.json5, defaults to ``./.data/``).
Detects and cleans up stale locks from crashed processes.

Lock is acquired at CLI command level (not in run_*() functions)
to avoid double-lock when the `run` command calls individual steps.
"""

import os
from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("lock")


def _default_lock_file() -> Path:
    """Return the default lock file path from config.

    Returns:
        Path to pipeline.lock inside the configured data directory.
    """
    from personalscraper.conf.loader import load_config, resolve_config_path

    config = load_config(resolve_config_path())
    return config.paths.data_dir / "pipeline.lock"


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


def is_lock_held(lock_file: Path | None = None) -> bool:
    """Return ``True`` if *lock_file* is held by a live process (read-only probe).

    Implements the SAME stale-PID detection as :func:`acquire_lock` — exists +
    valid PID integer + ``os.kill(pid, 0)`` alive → ``True``; missing / stale /
    corrupt → ``False`` (with no write and no unlink); owned by another user
    (``PermissionError`` on ``os.kill``) → ``True`` (lock held by another
    user's live process, mirroring :func:`acquire_lock`).

    Safe to call every poll cycle from a long-lived daemon (the Watcher loop)
    that must not mutate a lock owned by a concurrent pipeline run.

    Args:
        lock_file: Path to the lock file.  Defaults to
            ``paths.data_dir / "pipeline.lock"`` resolved from config.

    Returns:
        ``True`` when the lock file exists AND contains a PID of a live process
        reachable by the current user; ``False`` otherwise.
    """
    if lock_file is None:
        lock_file = _default_lock_file()
    if not lock_file.exists():
        return False
    try:
        stored_pid = int(lock_file.read_text().strip())
    except ValueError:
        # Corrupt PID text — lock is effectively not held.
        return False
    except OSError as exc:
        # Unreadable file — log the error, treat as not held.
        log.warning(
            "lock_read_failed",
            lock_file=str(lock_file),
            errno=exc.errno,
            exc_info=True,
        )
        return False
    try:
        os.kill(stored_pid, 0)
        # Process is alive — lock is valid.
        return True
    except ProcessLookupError:
        # Process dead — lock is stale.
        return False
    except PermissionError:
        # Process exists but owned by another user — treat as held.
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
