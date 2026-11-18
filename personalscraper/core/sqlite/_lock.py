# personalscraper/core/sqlite/_lock.py
"""Single-writer flock with PID sidecar and stale-recovery (SSOT).

Event-free: no EventBus.  Logs via core.sqlite.lock.* event names.
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from personalscraper.core.sqlite.errors import SqliteLockError
from personalscraper.logger import get_logger

log = get_logger("core.sqlite.lock")

_POLL_INTERVAL_S = 0.05


@contextmanager
def db_lock(
    path: Path,
    *,
    timeout: float = 0,
    error_factory: Callable[[int], BaseException] | None = None,
) -> Generator[None, None, None]:
    """Acquire the single-writer lock for a SQLite database file.

    Two files are used:

    * ``<path>.lock`` — the flock file (OS-level ``fcntl.flock``).  It is taken
      directly rather than through :class:`filelock.FileLock`, which unlinks
      its lock file on release.
    * ``<path>.lock.json`` — a human-readable JSON sidecar written **after**
      acquiring the OS lock, containing ``{pid, started_at, hostname}``.

    Keeping metadata in a separate file keeps the flock file empty and stable.

    Once the flock is held, a sidecar left on disk is stale (its writer crashed and
    the kernel released the lock): ``core.sqlite.lock.stale_recovered`` is logged
    and the sidecar is overwritten.  The sidecar is never judged before the flock
    is held, since a live holder may be about to write its own.

    On timeout (the flock is still held after ``timeout`` seconds) the lock is
    refused whatever the sidecar says: a dead or unreadable sidecar cannot be told
    apart from a holder that has not written its own yet.  Raise via
    ``error_factory(pid)`` (or a bare :class:`SqliteLockError` if no factory is
    supplied; ``pid`` is ``-1`` when the holder is unknown).

    The flock file itself is **never** unlinked: removing it lets a second
    writer lock a fresh inode while the first still holds the old one.  An
    empty, unlocked flock file is simply a free lock.

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

    lock_metadata = json.dumps(
        {
            "pid": os.getpid(),
            "started_at": time.time(),
            "hostname": socket.gethostname(),
        }
    )

    fd = _try_flock(lock_path, timeout)
    if fd is None:
        # The OS lock is held by another process, whatever its sidecar says: a dead
        # or unreadable sidecar cannot be told apart from a holder that has not
        # written its own yet, and the flock file must not be unlinked.  Refuse.
        held_pid = _read_pid(meta_path)
        raise (
            error_factory(held_pid if held_pid is not None else -1)
            if error_factory is not None
            else SqliteLockError(f"Writer lock held by PID {held_pid}")
        ) from None

    try:
        # Holding the flock, any sidecar still on disk is stale by definition: its writer
        # crashed (the kernel released its lock) or was never alive.  Judging it before the
        # flock is taken would race a live holder writing its own sidecar.  Overwriting it
        # below replaces it; only the recovery is logged here.
        stale_pid = _read_pid(meta_path) if meta_path.exists() else None
        if stale_pid is not None:
            log.warning("core.sqlite.lock.stale_recovered", stale_pid=stale_pid)
        meta_path.write_text(lock_metadata)
        yield
    finally:
        # Drop the sidecar BEFORE releasing: once released another writer may already
        # own the lock and have written its own sidecar.  The flock file is kept.
        _remove_sidecar(meta_path)
        os.close(fd)  # closing the descriptor releases the flock


def _try_flock(lock_path: Path, timeout: float) -> int | None:
    """Take the exclusive flock on ``lock_path``, creating it when absent.

    Args:
        lock_path: Flock file; never unlinked, an existing empty one is a free lock.
        timeout: Seconds to keep trying; ``0`` means a single attempt.

    Returns:
        The open descriptor holding the lock (close it to release), or ``None``
        when the lock is still held by someone else after ``timeout``.
    """
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + max(timeout, 0)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                return None
            time.sleep(_POLL_INTERVAL_S)
        except BaseException:
            os.close(fd)
            raise
        else:
            return fd


def _read_pid(meta_path: Path) -> int | None:
    """Read the holder pid from a metadata sidecar.

    Args:
        meta_path: Path of the ``.lock.json`` sidecar.

    Returns:
        The recorded pid, or ``None`` when the sidecar is missing, unreadable
        or does not name a positive pid.
    """
    try:
        pid = int(json.loads(meta_path.read_text()).get("pid", -1))
    except (OSError, json.JSONDecodeError, ValueError, TypeError, AttributeError):
        return None
    return pid if pid > 0 else None


def _remove_sidecar(meta_path: Path) -> None:
    """Best-effort removal of the metadata sidecar (never the flock file).

    Args:
        meta_path: Path of the ``.lock.json`` sidecar.
    """
    try:
        meta_path.unlink(missing_ok=True)
    except OSError:
        pass
