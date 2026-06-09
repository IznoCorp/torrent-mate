"""Port protocols for the acquire lobe — RP5c structural seam.

Only the lifecycle contract is defined here.  RP3 will extend
``AcquireStore`` with query/write methods when the database is wired.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AcquireStore(Protocol):
    """Minimal store contract — lifecycle only.

    RP3 supplies the concrete implementation and fills the
    ``AcquireContext.store`` slot.  The only obligation RP5c needs
    is ``close()`` so the context's lifecycle can propagate it.
    """

    def close(self) -> None:
        """Release all resources held by the store (connections, threads, …)."""
        ...


__all__ = ["AcquireStore"]
