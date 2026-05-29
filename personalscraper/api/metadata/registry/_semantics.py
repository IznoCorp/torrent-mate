"""Capability → Mode mapping for the provider registry (DESIGN §4, §5.1).

Each capability Protocol is assigned to exactly one semantic mode:
chain, fan_out, locked, or direct. Adding a new Protocol requires updating
exactly one set in this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.api.metadata._contracts import (
    ArtworkProvider,
    EpisodeFetcher,
    IDCrossRef,
    IDValidator,
    KeywordProvider,
    MovieDetailsProvider,
    RatingProvider,
    RecommendationProvider,
    Searchable,
    TvDetailsProvider,
    VideoProvider,
)
from personalscraper.api.metadata.registry._errors import WrongSemanticBug

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import (
        Mode,
    )

# Frozen sets — one place to update when adding a new Protocol.
CHAIN_CAPABILITIES: frozenset[type] = frozenset(
    {
        Searchable,
        MovieDetailsProvider,
        TvDetailsProvider,
        EpisodeFetcher,
    }
)
FAN_OUT_CAPABILITIES: frozenset[type] = frozenset({RatingProvider})
LOCKED_CAPABILITIES: frozenset[type] = frozenset(
    {
        ArtworkProvider,
        KeywordProvider,
        VideoProvider,
        RecommendationProvider,
    }
)
DIRECT_CAPABILITIES: frozenset[type] = frozenset({IDValidator, IDCrossRef})

ALL_CAPABILITIES: frozenset[type] = (
    CHAIN_CAPABILITIES | FAN_OUT_CAPABILITIES | LOCKED_CAPABILITIES | DIRECT_CAPABILITIES
)

# Stable string key → Protocol type (used by ProvidersConfig parser).
CAPABILITY_KEYS: dict[str, type] = {
    "Searchable": Searchable,
    "MovieDetailsProvider": MovieDetailsProvider,
    "TvDetailsProvider": TvDetailsProvider,
    "EpisodeFetcher": EpisodeFetcher,
    "RatingProvider": RatingProvider,
    "ArtworkProvider": ArtworkProvider,
    "KeywordProvider": KeywordProvider,
    "VideoProvider": VideoProvider,
    "RecommendationProvider": RecommendationProvider,
    "IDValidator": IDValidator,
    "IDCrossRef": IDCrossRef,
}


def mode_for(capability: type) -> Mode:
    """Return the dispatch mode for a capability.

    Args:
        capability: A capability Protocol type (e.g. ``Searchable``).

    Returns:
        The corresponding ``Mode`` enum value.

    Raises:
        WrongSemanticBug: If the capability is not a known registry capability.
    """
    from personalscraper.api.metadata.registry import (
        Mode,
    )

    if capability in CHAIN_CAPABILITIES:
        return Mode.CHAIN
    if capability in FAN_OUT_CAPABILITIES:
        return Mode.FAN_OUT
    if capability in LOCKED_CAPABILITIES:
        return Mode.LOCKED
    if capability in DIRECT_CAPABILITIES:
        return Mode.DIRECT
    raise WrongSemanticBug(f"{capability.__name__} is not a known registry capability")
