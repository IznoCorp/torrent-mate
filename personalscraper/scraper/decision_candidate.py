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

from pydantic import BaseModel, ConfigDict, field_validator


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
        poster_url: The provider poster URL (``http``/``https`` only), or
            ``None`` when no poster is available or the URL had an untrusted
            scheme.
        overview: A short plot summary, or ``None`` when the provider
            did not return one.
    """

    # extra="forbid" makes the persisted candidates_json shape strict — an
    # unknown key (writer bug / hand-edited row) fails validation loudly rather
    # than being silently dropped, matching the indexer-json-shapes.md contract
    # (coherence study F48).
    model_config = ConfigDict(extra="forbid")

    provider: Literal["tmdb", "tvdb"]
    provider_id: int
    title: str
    year: int | None = None
    score: float
    poster_url: str | None = None
    overview: str | None = None

    @field_validator("poster_url")
    @classmethod
    def _validate_poster_scheme(cls, value: str | None) -> str | None:
        """Drop a ``poster_url`` whose scheme is not ``http``/``https`` (F44).

        Provider responses are passed through into an ``<img src>`` in the web
        UI; a non-http(s) scheme (``javascript:``, ``data:``, ``file:``) has no
        legitimate poster use and is nulled here at every write boundary
        (batch enqueue + live search) rather than trusted in the frontend.

        Args:
            value: The candidate ``poster_url`` (may be ``None``).

        Returns:
            The URL when it is a well-formed ``http``/``https`` URL, else
            ``None``.
        """
        if value is None or value == "":
            return None
        lowered = value.strip().lower()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            return value
        return None
