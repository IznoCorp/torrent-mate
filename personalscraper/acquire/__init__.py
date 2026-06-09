"""Acquisition lobe — home of the RP5b orchestrator (future) and the RP5c injection handle.

This package is a peer of ``ingest``, ``sort``, ``dispatch``, and ``indexer``.
At RP5c it contains only the injection context (``AcquireContext``) and the
``AcquireStore`` Protocol seam.  No behaviour is implemented here yet.

Import direction: ``acquire/`` may import downward only (``api/``, ``core/``,
``conf/``, ``events/``). It must never import the triage packages (``ingest``,
``sort``, ``sorter``, ``process``, ``scraper``, ``dispatch``, ``indexer``,
``enforce``, ``verify``, ``insights``, ``maintenance``, ``reports``,
``trailers``, ``pipeline``, ``pipeline_steps``, ``commands``).
"""

from personalscraper.acquire.context import AcquireContext

__all__ = ["AcquireContext"]
