"""Tests for the interactive-search result cache.

Paging through search results used to re-query the providers from scratch on
every page: asking for offset=30 replayed the whole TMDB + TVDB fan-out, ranked
all ~130 candidates again, and then threw away everything outside the 30-row
window. Walking four pages of one search meant four full provider sweeps for a
result set that had not changed.

The cache holds the RANKED CANDIDATE LIST per (query, kind) so every page after
the first is served from memory.
"""

from __future__ import annotations

import pytest

from personalscraper.api.metadata._base import SearchResult
from personalscraper.scraper.search_ranking import RankedResult
from personalscraper.web.acquisition.search_cache import SearchResultCache


def _row(provider_id: str, title: str = "X") -> RankedResult:
    """Build a minimal ranked candidate.

    Args:
        provider_id: The provider id.
        title: The title.

    Returns:
        A RankedResult wrapping a minimal SearchResult.
    """
    return RankedResult(
        result=SearchResult(provider="tmdb", provider_id=provider_id, title=title, media_type="movie"),
        score=0.9,
    )


class TestHitAndMiss:
    """The cache serves a stored lot and reports a miss otherwise."""

    def test_miss_on_unknown_query(self) -> None:
        """An unseen query is a miss."""
        cache = SearchResultCache(ttl_seconds=60, max_entries=8)
        assert cache.get("monarch", None, now=1000.0) is None

    def test_hit_after_put(self) -> None:
        """A stored lot comes back intact."""
        cache = SearchResultCache(ttl_seconds=60, max_entries=8)
        rows = [_row("1"), _row("2")]
        cache.put("monarch", None, rows, now=1000.0)
        assert cache.get("monarch", None, now=1001.0) == rows

    def test_kind_is_part_of_the_key(self) -> None:
        """« Tout », « Films » and « Séries » are three different result sets."""
        cache = SearchResultCache(ttl_seconds=60, max_entries=8)
        cache.put("monarch", "movie", [_row("1")], now=1000.0)
        assert cache.get("monarch", "tv", now=1000.0) is None
        assert cache.get("monarch", None, now=1000.0) is None
        assert cache.get("monarch", "movie", now=1000.0) is not None

    def test_query_is_normalised(self) -> None:
        """Case and surrounding spaces must not split the cache.

        The operator retyping « Monarch » after « monarch » is the same search;
        treating them as different entries would replay the provider sweep for
        nothing.
        """
        cache = SearchResultCache(ttl_seconds=60, max_entries=8)
        cache.put("  Monarch ", None, [_row("1")], now=1000.0)
        assert cache.get("monarch", None, now=1000.0) is not None


class TestExpiry:
    """Entries go stale so a search never serves indefinitely-old provider data."""

    def test_entry_expires_after_ttl(self) -> None:
        """Past the TTL the entry is gone."""
        cache = SearchResultCache(ttl_seconds=60, max_entries=8)
        cache.put("monarch", None, [_row("1")], now=1000.0)
        assert cache.get("monarch", None, now=1061.0) is None

    def test_entry_alive_just_before_ttl(self) -> None:
        """Just inside the TTL it still serves."""
        cache = SearchResultCache(ttl_seconds=60, max_entries=8)
        cache.put("monarch", None, [_row("1")], now=1000.0)
        assert cache.get("monarch", None, now=1059.0) is not None

    def test_expired_entry_is_evicted_not_merely_hidden(self) -> None:
        """A stale entry must not keep occupying a slot forever."""
        cache = SearchResultCache(ttl_seconds=60, max_entries=8)
        cache.put("monarch", None, [_row("1")], now=1000.0)
        cache.get("monarch", None, now=2000.0)
        assert cache.size() == 0


class TestBounded:
    """The web process is long-lived — the cache must not grow without limit."""

    def test_evicts_least_recently_used(self) -> None:
        """Past the cap, the least recently USED entry goes, not the oldest written."""
        cache = SearchResultCache(ttl_seconds=600, max_entries=2)
        cache.put("a", None, [_row("1")], now=1000.0)
        cache.put("b", None, [_row("2")], now=1001.0)
        # Touch "a" so "b" becomes the least recently used.
        assert cache.get("a", None, now=1002.0) is not None
        cache.put("c", None, [_row("3")], now=1003.0)
        assert cache.size() == 2
        assert cache.get("b", None, now=1004.0) is None
        assert cache.get("a", None, now=1004.0) is not None

    def test_size_never_exceeds_the_cap(self) -> None:
        """Hammering the cache cannot blow the bound."""
        cache = SearchResultCache(ttl_seconds=600, max_entries=3)
        for i in range(50):
            cache.put(f"q{i}", None, [_row(str(i))], now=1000.0 + i)
        assert cache.size() == 3


class TestConcurrency:
    """FastAPI runs sync endpoints in a threadpool — concurrent access is normal."""

    def test_parallel_put_and_get_do_not_corrupt(self) -> None:
        """Many threads hammering the cache leave it consistent and bounded."""
        from concurrent.futures import ThreadPoolExecutor

        cache = SearchResultCache(ttl_seconds=600, max_entries=16)

        def hammer(i: int) -> None:
            cache.put(f"q{i % 20}", None, [_row(str(i))], now=1000.0 + i)
            cache.get(f"q{i % 20}", None, now=1000.0 + i)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(hammer, range(400)))

        assert cache.size() <= 16


class TestInvalidate:
    """A cache the operator cannot clear is a cache that lies after a config change."""

    def test_clear_empties_everything(self) -> None:
        """clear() drops every entry."""
        cache = SearchResultCache(ttl_seconds=600, max_entries=8)
        cache.put("a", None, [_row("1")], now=1000.0)
        cache.put("b", "tv", [_row("2")], now=1000.0)
        cache.clear()
        assert cache.size() == 0


class TestRejectsEmptyLots:
    """A failed provider sweep must not be cached as 'no results'."""

    def test_empty_result_is_not_stored(self) -> None:
        """Caching an empty lot would pin a provider outage for the whole TTL.

        A degraded sweep (both providers down → zero rows) looks exactly like a
        genuine no-match. Storing it would keep serving "nothing found" for
        minutes after the providers recovered.
        """
        cache = SearchResultCache(ttl_seconds=600, max_entries=8)
        cache.put("monarch", None, [], now=1000.0)
        assert cache.get("monarch", None, now=1000.0) is None


@pytest.mark.parametrize("kind", [None, "movie", "tv"])
def test_round_trip_for_every_kind(kind: str | None) -> None:
    """Every kind the route accepts round-trips through the cache."""
    cache = SearchResultCache(ttl_seconds=60, max_entries=8)
    cache.put("q", kind, [_row("1")], now=1000.0)
    assert cache.get("q", kind, now=1000.0) is not None
