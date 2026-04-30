"""SIGTERM clean-shutdown machinery for the media indexer scanner.

DESIGN §11.9 / sub-phase 4.9: when the host (launchd, systemd, an
operator) sends ``SIGTERM`` to a running scan, the scanner must finish
the file currently being processed, commit the current disk's
transaction, write the ``scan_run.last_path`` checkpoint, and exit ``0``.
A subsequent run resumes transparently from the checkpoint (the same
mechanism Phase 3 already uses for budget exhaustion).

This module exposes the primitives the scanner uses to wire that flow:

* :data:`_shutdown_event` — a process-global :class:`threading.Event`
  the signal handler sets and the walk loop polls.
* :func:`is_shutdown_requested` — the read side, called at every file
  boundary inside :func:`personalscraper.indexer.scanner._walker._walk_dir`.
* :func:`request_shutdown` / :func:`reset_shutdown` — explicit set / clear
  hooks used by tests (and by the SIGTERM handler).
* :func:`install_sigterm_handler` — registers the handler at scan start
  and returns a callable that restores the previous handler at scan end.

Why a process-global event
--------------------------

Threading the event through every walk function would change ~10 call
sites and break the existing budget-exhaustion plumbing (which already
uses a single-element list).  A module-level :class:`threading.Event`
is naturally shared across the :class:`~concurrent.futures.ThreadPoolExecutor`
workers spawned by the parallel path (sub-phase 4.3) — they all see the
same event without explicit propagation.

Signal-handler-from-thread caveat
---------------------------------

CPython only allows :func:`signal.signal` from the main thread.  When
``scan()`` is invoked from a worker thread (e.g. inside a unit test that
runs scans on a background thread), the handler registration silently
falls back to a no-op — :func:`request_shutdown` can still be called
directly to drive shutdown, so tests are unaffected.
"""

from __future__ import annotations

import signal
import threading
from collections.abc import Callable
from typing import Any, cast

from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

# Module-level Event shared across every scanner thread.  Modules that
# poll the flag must NOT cache its value — the whole point is that the
# signal handler can flip it asynchronously and the next file-boundary
# check sees the new state.
_shutdown_event: threading.Event = threading.Event()


def is_shutdown_requested() -> bool:
    """Return ``True`` when a clean shutdown has been requested.

    Polled by the per-file iteration of the scanner walk.  Cheap (one
    atomic read on the underlying lock), so safe to call inside a tight
    loop.

    Returns:
        ``True`` once :func:`request_shutdown` (or the SIGTERM handler)
        has fired; ``False`` otherwise.
    """
    return _shutdown_event.is_set()


def request_shutdown() -> None:
    """Set the shutdown flag.  Idempotent; subsequent calls are no-ops.

    Called from:

    * The SIGTERM handler installed by :func:`install_sigterm_handler`.
    * Tests that want to drive a clean shutdown without raising a real
      signal.
    """
    _shutdown_event.set()


def reset_shutdown() -> None:
    """Clear the shutdown flag.

    ``scan()`` calls this at the start of every run so a stale flag from
    a previous in-process scan (or from a test that left the event set)
    does not abort the new scan immediately.  Tests use the same hook
    for inter-test isolation.
    """
    _shutdown_event.clear()


def _sigterm_handler(_signum: int, _frame: Any) -> None:
    """Bridge between the OS signal and :data:`_shutdown_event`.

    Sets the flag and logs the event — the scanner does the rest at the
    next file boundary.  We intentionally do NOT call any non-async-safe
    code (no logging beyond a single structlog call, which is async-safe
    via stdlib ``logging``).

    Args:
        _signum: The signal number (always ``signal.SIGTERM``).  Unused.
        _frame: Current stack frame.  Unused.
    """
    request_shutdown()
    log.info("indexer.scan.sigterm_received")


def install_sigterm_handler() -> Callable[[], None]:
    """Register the SIGTERM handler and return a restore callable.

    The returned callable restores the previous handler (typically
    :data:`signal.SIG_DFL` or whatever the host process had installed
    before the scan began).  Callers SHOULD invoke the restore in a
    ``finally`` block so the scanner does not leak its handler across
    scans or onto the host process.

    When ``signal.signal`` raises (e.g. invoked from a worker thread —
    CPython forbids this), this function logs a debug event and returns
    a no-op restore.  :func:`request_shutdown` and the Event-based
    machinery still work; only the OS-signal bridge is unavailable.

    Returns:
        A zero-argument callable that restores the previous SIGTERM
        handler.  Always safe to call; idempotent in the no-op fallback.
    """
    try:
        previous = signal.signal(signal.SIGTERM, _sigterm_handler)
    except ValueError:
        # Raised when called from a non-main thread.  This is expected
        # under some test harnesses; treat as no-op and continue.
        log.debug("indexer.scan.sigterm_handler_skipped", reason="non-main thread")
        return lambda: None

    def _restore() -> None:
        """Restore the previous SIGTERM handler.  Safe to call once."""
        try:
            # ``signal.signal`` accepts SIG_IGN/SIG_DFL/Callable; the
            # previous-value type-stub is strict so we cast for mypy.
            signal.signal(signal.SIGTERM, cast(Any, previous))
        except (ValueError, OSError):
            # If we cannot restore, the worst case is the scanner's
            # handler stays in place — still benign because the Event is
            # cleared by the next reset_shutdown().
            pass

    return _restore
