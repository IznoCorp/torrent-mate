"""Pydantic model for scrape-decision candidates (scrape-arbiter feature).

Each ``scrape_decision`` row stores a ``candidates_json`` column whose
elements conform to the ``DecisionCandidate`` shape defined here.  The
model is used by ``DecisionWriter`` (sub-phase 1.3) for serialization
validation and by REST routes (phase 3) for response models.

See docs/features/scrape-arbiter/DESIGN.md §3 for the table schema and
column contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DecisionCandidate(BaseModel):
    """A single scored search-result candidate for a scrape-decision row.

    Represents one provider match that the operator can inspect and
    resolve.  Stored as an element of the ``candidates_json`` JSON array
    in the ``scrape_decision`` table.

    Attributes:
        provider: The metadata provider that returned this candidate
            (``"tmdb"`` or ``"tvdb"``).
        provider_id: The numeric identifier assigned by the provider.
        title: The candidate title as returned by the provider.
        year: The release year, or ``None`` when the provider did not
            return one.
        score: The confidence score (0.0–1.0) assigned by the matching
            engine.
        poster_url: The provider poster URL, or ``None`` when no poster
            is available.
        overview: A short plot summary, or ``None`` when the provider
            did not return one.
    """

    provider: Literal["tmdb", "tvdb"]
    provider_id: int
    title: str
    year: int | None = None
    score: float
    poster_url: str | None = None
    overview: str | None = None
