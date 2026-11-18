# personalscraper/core/sqlite/_serialised.py
"""Serialise the use of one shared connection across threads.

A connection opened with ``check_same_thread=False`` may be handed to several threads (the
web's threadpool), but Python's ``sqlite3`` does not make concurrent use of one connection
safe: two threads executing on it at once can crash the interpreter. A store over such a
connection holds a lock around every public method that touches it.

Event-free: no EventBus, no domain imports.
"""

from __future__ import annotations

import functools
import threading
from collections.abc import Callable
from typing import Concatenate, Protocol


class HoldsConnectionLock(Protocol):
    """A store whose connection is guarded by ``_lock``."""

    _lock: threading.RLock


def serialised[S: HoldsConnectionLock, **P, R](
    method: Callable[Concatenate[S, P], R],
) -> Callable[Concatenate[S, P], R]:
    """Run a store method under the store's connection lock.

    The lock is re-entrant: a method calling another, or a transaction spanning several
    calls in one thread, takes it again without blocking itself.

    Args:
        method: The method touching the connection.

    Returns:
        The method, run with ``self._lock`` held.
    """

    @functools.wraps(method)
    def locked(self: S, /, *args: P.args, **kwargs: P.kwargs) -> R:
        """Call the method with the lock held.

        Args:
            self: The store.
            *args: The method's positional arguments.
            **kwargs: The method's keyword arguments.

        Returns:
            What the method returns.
        """
        with self._lock:
            return method(self, *args, **kwargs)

    return locked
