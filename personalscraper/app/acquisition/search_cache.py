"""In-process cache for interactive-search results.

Paging through a search used to replay the entire provider sweep: asking for
``offset=30`` re-queried TMDB (up to five pages) plus both TV providers, re-ranked
all ~130 candidates, and then discarded everything outside the requested window.
Walking four pages of one search cost four full sweeps of a result set that had
not changed in the meantime.

This cache stores the RANKED CANDIDATE LIST per ``(query, kind)``, so every page
after the first is served from memory. What it deliberately does NOT store is
anything derived per request — the ``already_owned`` library flag is recomputed on
every call from the indexer, because the library changes while a search sits on
screen and a stale "already owned" badge would drive a wrong decision.

Bounded and TTL'd: the web process is long-lived, so an unbounded cache is a slow
memory leak, and provider data that never expires is data that silently drifts.

The web process runs a single uvicorn worker, so a process-local cache is the
whole cache. It is still lock-guarded: FastAPI runs sync endpoints in a
threadpool, so concurrent access is the normal case, not the exception.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

from personalscraper.scraper.search_ranking import RankedResult

#: How long a ranked lot stays servable. Long enough that paging and refining a
#: search is free, short enough that a newly-released title shows up the same day.
DEFAULT_TTL_SECONDS = 300

#: Maximum distinct (query, kind) lots held at once. A search lot is ~100 small
#: dataclasses, so this bounds the cache at a few MB in the worst case.
DEFAULT_MAX_ENTRIES = 64


@dataclass(frozen=True)
class _Entry:
    """One cached lot.

    Attributes:
        rows: The ranked candidates, scores included.
        stored_at: Unix timestamp the lot was stored at.
    """

    rows: list[RankedResult]
    stored_at: float


class SearchResultCache:
    """A bounded, TTL'd, thread-safe LRU cache of ranked search candidates."""

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        """Initialise an empty cache.

        Args:
            ttl_seconds: Lifetime of an entry, in seconds.
            max_entries: Maximum number of lots held at once.
        """
        self._ttl = ttl_seconds
        self._max = max_entries
        self._entries: OrderedDict[tuple[str, str], _Entry] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _key(query: str, kind: str | None) -> tuple[str, str]:
        """Build the cache key for a query/kind pair.

        The query is normalised (trimmed + lowercased) so « Monarch » and
        « monarch » share one entry — retyping a search with different casing is
        the same search, and splitting it would replay the provider sweep for
        nothing.

        Args:
            query: The raw operator query.
            kind: ``"movie"``, ``"tv"``, or None for both.

        Returns:
            The cache key.
        """
        return (query.strip().casefold(), kind or "all")

    def get(self, query: str, kind: str | None, *, now: float | None = None) -> list[RankedResult] | None:
        """Return a cached lot, or None on a miss or an expired entry.

        Args:
            query: The operator query.
            kind: The kind restriction, or None.
            now: Reference timestamp (injected by tests; defaults to the clock).

        Returns:
            The cached rows, or None.
        """
        stamp = time.time() if now is None else now
        key = self._key(query, kind)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if stamp - entry.stored_at >= self._ttl:
                # Drop it rather than merely reporting a miss: a stale entry that
                # is never evicted keeps occupying a slot forever.
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return entry.rows

    def put(
        self,
        query: str,
        kind: str | None,
        rows: list[RankedResult],
        *,
        now: float | None = None,
    ) -> None:
        """Store a ranked lot, evicting the least recently used entry if needed.

        An EMPTY lot is deliberately not stored. A degraded provider sweep (both
        providers failing → zero rows) is indistinguishable from a genuine
        no-match, and caching it would keep serving "nothing found" for the whole
        TTL after the providers recovered.

        Args:
            query: The operator query.
            kind: The kind restriction, or None.
            rows: The ranked candidates to store.
            now: Reference timestamp (injected by tests; defaults to the clock).
        """
        if not rows:
            return
        stamp = time.time() if now is None else now
        key = self._key(query, kind)
        with self._lock:
            self._entries[key] = _Entry(rows=rows, stored_at=stamp)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        """Drop every entry."""
        with self._lock:
            self._entries.clear()

    def size(self) -> int:
        """Return the number of entries currently held.

        Returns:
            The entry count.
        """
        with self._lock:
            return len(self._entries)


#: Process-wide cache used by the acquisition search route. One uvicorn worker
#: means one cache; a future multi-worker deployment would need a shared store.
SEARCH_CACHE = SearchResultCache()
