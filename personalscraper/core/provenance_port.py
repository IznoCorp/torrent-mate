"""Core port for the advisory acquisition-provenance registry (feature ``provenance``).

The pipeline steps (ingest / sort / dispatch) live BELOW the acquire lobe in the
layering and must not import ``acquire/`` (same rule as
:class:`~personalscraper.core.delete_permit.SeedObligationChecker`). They receive a
provenance WRITER through this structural port instead — the concrete
``personalscraper.acquire._provenance_store._ProvenanceSubStore`` satisfies it by
shape, injected at the composition root.

Every method is **advisory / best-effort by contract**: an implementation must never
raise to its caller (a provenance write must never fail a pipeline step), and a call
for an untracked info-hash (a manual/direct grab) is a silent no-op. Consumers still
guard the call defensively so a non-conforming writer can never break the step.
"""

from __future__ import annotations

from typing import Protocol


class StagingProvenanceWriter(Protocol):
    """The provenance writes a pipeline step performs on the staging journey."""

    def set_ingest(self, info_hash: str, *, ingest_path: str, ingested_at: int) -> None:
        """Record the staging folder created for *info_hash* at ingest (no-op if untracked)."""
        ...

    def set_current_path(self, info_hash: str, *, path: str) -> None:
        """Keep the live folder path in sync across a sort/rename (no-op if untracked)."""
        ...

    def set_dispatch(self, info_hash: str, *, dispatch_path: str, dispatched_at: int) -> None:
        """Record the final destination for *info_hash* at dispatch (no-op if untracked)."""
        ...
