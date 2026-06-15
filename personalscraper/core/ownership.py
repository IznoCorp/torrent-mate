"""Neutral ownership-checker port (RP6).

Import direction: stdlib + typing only (mirrors core/delete_permit.py).
Never imported by indexer/ at the top level — inject via the composition root.

The acquire lobe depends ONLY on these core port types. The concrete
IndexerOwnershipChecker implementation (indexer/ownership.py) is injected
at the composition root. This ensures acquire/ never imports indexer/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from personalscraper.core.identity import MediaRef


@runtime_checkable
class OwnershipChecker(Protocol):
    """Protocol for ownership-check implementations.

    An ``OwnershipChecker`` answers "does the library already contain this
    work?" Implementations MUST be fail-open: any lookup error → False
    (not owned). False is only returned on a positively-known live file;
    True means ownership is confirmed.
    """

    def owns(
        self,
        media_ref: "MediaRef",
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Return True iff the library contains a live file for this work.

        Args:
            media_ref: Provider IDs for the work (tvdb primary, tmdb fallback,
                imdb last resort).
            kind: ``"movie"`` or ``"episode"``.
            season: Season number; required when ``kind="episode"``.
            episode: Episode number; required when ``kind="episode"``.

        Returns:
            ``True`` if a live (non-soft-deleted) file exists for the work;
            ``False`` otherwise, including on any lookup error (fail-open).
        """
        ...


class NullOwnershipChecker:
    """Fail-open no-op OwnershipChecker — always returns False.

    Used as the default for tests, for commands when no library.db is
    configured, and as the fallback when the DB connection is unavailable.
    Returning False ("not owned") keeps the pipeline safe: a wanted item
    is never silently skipped because ownership could not be verified.
    """

    def owns(
        self,
        media_ref: "MediaRef",
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Always return False (not owned).

        Args:
            media_ref: Ignored.
            kind: Ignored.
            season: Ignored.
            episode: Ignored.

        Returns:
            Always ``False``.
        """
        return False


__all__ = [
    "NullOwnershipChecker",
    "OwnershipChecker",
]
