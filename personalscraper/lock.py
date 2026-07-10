"""Pipeline lock file — prevents concurrent pipeline executions.

Uses a PID-based lock file in the project data directory (configured
via ``paths.data_dir`` in config.json5, defaults to ``./.data/``).
Detects and cleans up stale locks from crashed processes.

Lock is acquired at CLI command level (not in run_*() functions)
to avoid double-lock when the `run` command calls individual steps.

Two-tier mutual-exclusion model (webui-ux phase 4, scoped scrape locking)
------------------------------------------------------------------------

* **Global pipeline holders** (full run / individual steps / maintenance /
  analyze) take the single ``pipeline.lock`` through :func:`acquire_pipeline_lock`.
  They dispatch/move files, so at most ONE may run at a time AND none may run
  while a ``scrape-resolve`` is mid-writing an item.
* **Scrape-resolve runs** take a **per-staging-item** lock under
  ``scrape_locks_dir`` through :func:`acquire_scrape_resolve_lock`. Two resolves
  on distinct staging paths run in PARALLEL, but any resolve is mutually
  exclusive with any global holder.

Fail-closed ordering (do NOT invert): each side *creates its own claim BEFORE
checking the other side*.  A global holder acquires ``pipeline.lock`` first, THEN
checks the scrape dir; a resolve registers its item lock first, THEN checks
``pipeline.lock``.  In any interleaving at most one side passes its check; if both
race, both back off (safe — never both proceed).  A check-then-claim order would
let both proceed, corrupting an item mid-dispatch.
"""

import hashlib
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


# ---------------------------------------------------------------------------
# Two-tier mutual exclusion — global pipeline lock vs scoped scrape-resolve
# ---------------------------------------------------------------------------


def any_scrape_resolve_active(scrape_locks_dir: Path) -> bool:
    """Return ``True`` when any ``*.lock`` in *scrape_locks_dir* is held live.

    Iterates every ``*.lock`` file in the directory and probes it with
    :func:`is_lock_held` (the same stale-PID detection used by the global
    lock).  A missing directory means no resolve has ever registered a lock →
    ``False``.  Stale locks (dead pid / corrupt / missing) are treated as
    inactive so a crashed resolve never blocks the pipeline forever.

    Args:
        scrape_locks_dir: The directory holding per-staging-item scrape locks
            (``<data_dir>/locks/scrape/``).

    Returns:
        ``True`` when at least one item lock is held by a live process;
        ``False`` when the directory is absent, empty, or holds only stale
        locks.
    """
    if not scrape_locks_dir.is_dir():
        return False
    for item_lock in scrape_locks_dir.glob("*.lock"):
        if is_lock_held(item_lock):
            return True
    return False


def acquire_pipeline_lock(lock_file: Path, scrape_locks_dir: Path) -> bool:
    """Acquire the global ``pipeline.lock``, fail-closed against active resolves.

    Claim-first-then-verify: acquire the global lock FIRST, then check the
    scrape-lock directory.  This ordering (never inverted) makes the mutual
    exclusion with :func:`acquire_scrape_resolve_lock` fail-closed — if a resolve
    races us, at most one side passes its post-claim check; if both race, both
    back off (safe).

    Args:
        lock_file: Path to the global ``pipeline.lock``.
        scrape_locks_dir: The directory holding per-staging-item scrape locks
            (``<data_dir>/locks/scrape/``).

    Returns:
        ``True`` when the global lock was acquired AND no scrape-resolve is
        active; ``False`` when another global holder owns the lock, or when a
        scrape-resolve is active (in which case the just-acquired global lock is
        released before returning so it is never leaked).
    """
    if not acquire_lock(lock_file):
        return False
    # Claim-first-then-verify: the global lock now exists on disk, so a resolve
    # starting concurrently will observe it in ITS post-claim check.  Only after
    # claiming do we check the scrape dir — if a resolve already registered its
    # item lock before we claimed, back off and release the global lock.
    #
    # The probe runs INSIDE try/except (SF5): if any_scrape_resolve_active raises
    # an unexpected error (dir mutated mid-glob, a non-OSError FS failure), the
    # just-claimed global lock must NOT be leaked — release it before re-raising
    # so no exception path leaves pipeline.lock claimed on disk.
    try:
        scrape_active = any_scrape_resolve_active(scrape_locks_dir)
    except Exception:
        release_lock(lock_file)
        raise
    if scrape_active:
        release_lock(lock_file)
        log.warning("pipeline_lock_backoff_scrape_active", scrape_locks_dir=str(scrape_locks_dir))
        return False
    return True


def acquire_scrape_resolve_lock(
    staging_path: Path,
    pipeline_lock: Path,
    scrape_locks_dir: Path,
) -> Path | None:
    """Register a per-staging-item scrape lock, fail-closed against the pipeline.

    Claim-first-then-verify: acquire the per-item lock FIRST, then check the
    global ``pipeline.lock``.  This ordering (never inverted) makes the mutual
    exclusion with :func:`acquire_pipeline_lock` fail-closed — if a global holder
    races us, at most one side passes its post-claim check; if both race, both
    back off (safe).

    The item lock name is ``<sha1(str(staging_path))>.lock`` so two resolves on
    DISTINCT staging paths take distinct locks (parallel), while a second resolve
    on the SAME path collides on the identical name and is refused (idempotent
    guard).

    Args:
        staging_path: The staging directory of the item being resolved.
        pipeline_lock: Path to the global ``pipeline.lock`` (read-checked only —
            never acquired here).
        scrape_locks_dir: The directory holding per-staging-item scrape locks
            (``<data_dir>/locks/scrape/``, created if missing).

    Returns:
        The acquired item-lock :class:`Path` on success; ``None`` when the same
        item is already resolving, or when a global pipeline holder is active (in
        which case the just-acquired item lock is released before returning so it
        is never leaked).
    """
    scrape_locks_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(str(staging_path).encode()).hexdigest()  # noqa: S324 — non-cryptographic key derivation
    item_lock = scrape_locks_dir / f"{digest}.lock"

    if not acquire_lock(item_lock):
        # The SAME staging item is already resolving (identical lock name held
        # by a live process) — refuse the duplicate resolve.
        return None
    # Claim-first-then-verify: the item lock now exists on disk, so a pipeline
    # holder starting concurrently will observe it in ITS post-claim check.  Only
    # after claiming do we check the global lock — if a global holder already
    # acquired pipeline.lock before we claimed, back off and release the item lock.
    if is_lock_held(pipeline_lock):
        release_lock(item_lock)
        log.warning("scrape_resolve_backoff_pipeline_held", pipeline_lock=str(pipeline_lock))
        return None
    return item_lock


def release_scrape_resolve_lock(item_lock: Path) -> None:
    """Release a per-staging-item scrape lock acquired by :func:`acquire_scrape_resolve_lock`.

    Args:
        item_lock: The item-lock path returned by
            :func:`acquire_scrape_resolve_lock`.
    """
    release_lock(item_lock)


def scrape_locks_dir_for(data_dir: Path) -> Path:
    """Return the per-staging-item scrape-lock directory for *data_dir*.

    The directory is ``<data_dir>/locks/scrape/`` — created lazily by
    :func:`acquire_scrape_resolve_lock`, so this helper only computes the path.

    Args:
        data_dir: The configured pipeline data directory (``paths.data_dir``).

    Returns:
        The ``<data_dir>/locks/scrape/`` directory path.
    """
    return data_dir / "locks" / "scrape"
