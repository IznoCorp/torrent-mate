# personalscraper/core/sqlite/_lock.py
"""Single-writer FileLock with PID sidecar and stale-recovery (SSOT).

Event-free: no EventBus.  Logs via core.sqlite.lock.* event names.
"""

from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from personalscraper.core.sqlite.errors import SqliteLockError
from personalscraper.logger import get_logger

log = get_logger("core.sqlite.lock")


@contextmanager
def db_lock(
    path: Path,
    *,
    timeout: float = 0,
    error_factory: Callable[[int], BaseException] | None = None,
) -> Generator[None, None, None]:
    """Acquire the single-writer lock for a SQLite database file.

    Two files are used:

    * ``<path>.lock`` — the :class:`filelock.FileLock` file (OS-level flock/fcntl).
    * ``<path>.lock.json`` — a human-readable JSON sidecar written **after**
      acquiring the OS lock, containing ``{pid, started_at, hostname}``.

    Keeping metadata in a separate file prevents :class:`filelock.FileLock`
    from wiping the content on ``acquire()`` (FileLock truncates the lock file
    when it takes ownership).

    On timeout (``Timeout`` raised by :class:`filelock.FileLock`):

    * Read ``<path>.lock.json``, extract ``pid``.
    * ``os.kill(pid, 0)`` — if the process is dead (``OSError``), log
      ``core.sqlite.lock.stale_recovered``, delete both lock files, and acquire.
    * If the process is alive, raise via ``error_factory(pid)`` (or a
      bare :class:`SqliteLockError` if no factory is supplied).

    Args:
        path: Path of the database file (lock files derived from this).
        timeout: Seconds to wait before declaring a timeout.  ``0`` means
            fail immediately if the lock is unavailable (default).
        error_factory: Optional callable that builds a rich exception from
            the holder PID.  When ``None``, a bare :class:`SqliteLockError`
            with a human-readable message is raised.

    Yields:
        ``None`` — the lock is held for the duration of the ``with`` block.

    Raises:
        SqliteLockError: If the lock is held by a live process and no
            ``error_factory`` is supplied.
        BaseException: Whatever ``error_factory(pid)`` returns, when supplied.
    """
    lock_path = Path(str(path) + ".lock")
    meta_path = Path(str(path) + ".lock.json")
    lock = FileLock(str(lock_path), timeout=timeout)

    lock_metadata = json.dumps(
        {
            "pid": os.getpid(),
            "started_at": time.time(),
            "hostname": socket.gethostname(),
        }
    )

    # --- Pre-acquisition stale check ---
    # If a metadata sidecar exists before we even try to acquire the OS lock, check
    # whether the recorded PID is still alive.  When a process crashes, the kernel
    # releases the fcntl lock but the metadata file is left behind.  Without this
    # check we would acquire silently and overwrite the stale metadata, losing the
    # opportunity to log the recovery and alert the operator.
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text())
            prior_pid = int(data.get("pid", -1))
            try:
                os.kill(prior_pid, 0)
                # PID is alive — this is a live lock (OS lock will block/timeout below)
            except OSError:
                # PID is dead → stale metadata; clean up and log before acquiring
                log.warning("core.sqlite.lock.stale_recovered", stale_pid=prior_pid)
                for stale in (lock_path, meta_path):
                    try:
                        stale.unlink(missing_ok=True)
                    except OSError:
                        pass
        except (json.JSONDecodeError, ValueError, OSError):
            # Unreadable sidecar; clean up defensively
            try:
                meta_path.unlink(missing_ok=True)
            except OSError:
                pass

    try:
        lock.acquire(timeout=timeout)
    except Timeout:
        # --- Timeout handler: OS lock held by another process ---
        held_pid: int | None = None
        try:
            data_t = json.loads(meta_path.read_text())
            held_pid = int(data_t.get("pid", -1))
        except (OSError, json.JSONDecodeError, ValueError):
            pass

        if held_pid is not None:
            try:
                os.kill(held_pid, 0)
                # Process is alive → cannot acquire
                raise (
                    error_factory(held_pid)
                    if error_factory is not None
                    else SqliteLockError(f"Writer lock held by PID {held_pid}")
                )
            except OSError:
                # Process is dead but OS lock is still held (zombie / timing window);
                # log the recovery and try once more without timeout.
                log.warning("core.sqlite.lock.stale_recovered", stale_pid=held_pid)
                for stale in (lock_path, meta_path):
                    try:
                        stale.unlink(missing_ok=True)
                    except OSError:
                        pass
                lock.acquire(timeout=-1)
        else:
            # Cannot read the metadata file; clear both and try to acquire
            for stale in (lock_path, meta_path):
                try:
                    stale.unlink(missing_ok=True)
                except OSError:
                    pass
            lock.acquire(timeout=-1)

    try:
        meta_path.write_text(lock_metadata)
        yield
    finally:
        lock.release()
        for p in (lock_path, meta_path):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
