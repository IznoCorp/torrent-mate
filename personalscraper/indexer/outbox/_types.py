"""Public types for the outbox drainer: OutboxPayloadError and DrainStats."""

from __future__ import annotations

from dataclasses import dataclass, field


class OutboxPayloadError(ValueError):
    """Raised when an outbox payload contains an invalid or unexpected value.

    Used to signal defensive validation failures before any DB write is attempted,
    e.g. an unknown ``kind`` in an ``artwork_write`` payload.
    """


@dataclass
class DrainStats:
    """Summary statistics produced by a single drainer run.

    Args:
        applied: Number of rows applied to the indexer tables.
        deduped: Number of rows skipped as stale duplicates (marked done without applying).
        deferred: Number of rows moved to ``pending_op`` because their disk was unreachable.
        failed: Number of rows that exhausted retries and were marked failed.
        replayed: Number of ``pending_op`` rows replayed on remount.
    """

    applied: int = field(default=0)
    deduped: int = field(default=0)
    deferred: int = field(default=0)
    failed: int = field(default=0)
    replayed: int = field(default=0)
