"""Pydantic models for the decisions API (scrape-arbiter feature).

See docs/features/scrape-arbiter/DESIGN.md §6 for the route contracts these
models serve.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from personalscraper.scraper.decision_candidate import DecisionCandidate as DecisionCandidate

# DecisionCandidate is re-exported from personalscraper.scraper.decision_candidate
# (single source of truth — created in phase 1.2).  Web models reference it
# directly; downstream consumers may import it from here for convenience.


class DecisionListItem(BaseModel):
    """Summary row for the decisions list endpoint.

    Represents one ``scrape_decision`` row at the list level, without the
    full ``candidates_json`` payload.

    Attributes:
        id: The auto-increment primary key of the ``scrape_decision`` row.
        staging_path: Absolute path to the staging folder, NFC-normalized.
        media_kind: ``"movie"`` or ``"tvshow"``.
        extracted_title: Title guessed from the folder name.
        extracted_year: Release year guessed from the folder name, or
            ``None`` when no year was extractable.
        trigger: What caused the enqueue —
            ``"below_threshold"``, ``"mid_band"``, or ``"ambiguous"``.
        candidates_count: Number of candidates in ``candidates_json``
            (computed at query time, not stored).
        status: ``"pending"``, ``"resolved"``, ``"dismissed"``, or
            ``"superseded"``.
        created_at: Epoch seconds when the row was created (``time.time()``).
    """

    id: int
    staging_path: str
    media_kind: str
    extracted_title: str
    extracted_year: int | None = None
    trigger: str
    candidates_count: int
    status: str
    created_at: float


class DecisionsResponse(BaseModel):
    """Paginated response for the ``GET /api/decisions`` endpoint.

    Attributes:
        items: Decision list items for the current page.
        pending_count: Total number of decisions with ``status='pending'``
            (independent of pagination — the shell badge value).
        total: Total number of decisions matching the current filter
            (all statuses, for pagination).
        page: Current page number (1-indexed).
        page_size: Number of items per page.
    """

    items: list[DecisionListItem]
    pending_count: int
    total: int
    page: int
    page_size: int


class DecisionActivityItem(BaseModel):
    """One scrape currently in progress (a running scrape-resolve run).

    Attributes:
        decision_id: The ``scrape_decision.id`` being resolved.
        title: The folder-derived title shown to the operator.
        started_at: Unix-epoch seconds when the resolve run started.
        queued: ``True`` while the resolve runner waits for ``pipeline.lock``
            (a pipeline run is active) — the queue must be VISIBLE (#249
            post-mortem), never a 409 (operator directive 2026-07-15).
    """

    decision_id: int
    title: str
    started_at: float
    queued: bool = False


class DecisionActivityResponse(BaseModel):
    """Live activity for the scraping surface: what runs now + how many wait.

    Attributes:
        in_progress: The scrapes running right now (most recent first).
        pending_count: Number of decisions still waiting in the queue.
    """

    in_progress: list[DecisionActivityItem]
    pending_count: int


class DecisionDetail(DecisionListItem):
    """Full detail for a single ``scrape_decision`` row.

    Extends :class:`DecisionListItem` with the full candidate list and the
    resolution metadata (when resolved).

    Attributes:
        candidates: The full candidate list deserialized from
            ``candidates_json``.
        resolution_json: The resolution metadata deserialized from
            ``resolution_json``, or ``None`` when the decision is still
            pending, dismissed, or superseded.
    """

    candidates: list[DecisionCandidate]
    resolution_json: dict[str, Any] | None = None


class SearchRequest(BaseModel):
    """Request body for ``POST /api/decisions/{id}/search``.

    Triggers a live search against TMDB/TVDB for a given title and optional
    year.  Read-only — no state change.

    Attributes:
        title: The title to search for on the metadata providers.
        year: An optional release year to narrow the search.
    """

    title: str
    year: int | None = None


class SearchResponse(BaseModel):
    """Response body for ``POST /api/decisions/{id}/search``.

    Wraps the fresh candidate list returned by the live provider search.

    Attributes:
        candidates: Fresh ``DecisionCandidate`` list from the live provider
            search.
    """

    candidates: list[DecisionCandidate]


class ResolveRequest(BaseModel):
    """Request body for ``POST /api/decisions/{id}/resolve``.

    Pins a chosen provider identity and launches a targeted re-scrape.

    Attributes:
        provider: The metadata provider to use for the re-scrape
            (``"tmdb"`` or ``"tvdb"``).
        provider_id: The numeric identifier assigned by the chosen provider.
        via: How the operator chose this identity — ``"pick"`` for a candidate
            from the original queue snapshot, ``"search_override"`` for a
            candidate returned by a live title/year search override.  Persisted
            in ``resolution_json.via`` (coherence study F09/F40).
    """

    provider: Literal["tmdb", "tvdb"]
    provider_id: int
    via: Literal["pick", "search_override"] = "pick"


class ResolveResponse(BaseModel):
    """Response body for a successful ``POST /api/decisions/{id}/resolve``.

    Returned as HTTP 202 (Accepted) — the re-scrape is launched asynchronously.

    Attributes:
        run_uid: The unique identifier of the launched scrape-resolve run.
    """

    run_uid: str
