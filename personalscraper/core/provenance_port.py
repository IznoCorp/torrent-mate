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

    def set_ingest(self, info_hash: str, *, ingest_path: str, ingested_at: int, run_uid: str | None = None) -> None:
        """Record the staging folder created for *info_hash* at ingest (no-op if untracked).

        ``run_uid`` (F3) is the ingesting run's ``pipeline_run.run_uid`` (hex), or None.
        """
        ...

    def move_path(self, old_path: str, new_path: str) -> None:
        """Re-point a tracked folder old_path → new_path across a sort/rename (path-keyed)."""
        ...

    def set_scrape_run(self, staging_path: str, *, run_uid: str | None, scraped_at: int) -> None:
        """Record the scrape stage for the folder at *staging_path* (path-keyed, F3).

        Advances the row to ``status='scraped'`` + ``scraped_at`` and stamps the scraping
        run. No-op when the folder is untracked. Advisory: never raises.
        """
        ...

    def record_dispatch_by_path(
        self, staging_path: str, *, dispatch_path: str, dispatched_at: int, run_uid: str | None = None
    ) -> None:
        """Record the dispatch of the folder currently at *staging_path* (path-keyed).

        ``run_uid`` (F3) is the dispatching run's ``pipeline_run.run_uid`` (hex), or None.
        """
        ...

    def set_resolution(
        self,
        staging_path: str,
        *,
        state: str,
        resolved_at: int,
        decision_id: int | None = None,
        trigger: str | None = None,
    ) -> None:
        """Project a scrape-arbiter decision verdict onto *staging_path* (path-keyed, F2).

        ``state`` is ``'awaiting'`` | ``'resolved'`` | ``'dismissed'``. No-op when the
        folder is untracked (a manual/direct item — its decision lives only in
        ``scrape_decision``). Advisory: must never raise to the caller.
        """
        ...
