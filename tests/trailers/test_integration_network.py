"""End-to-end integration test for the trailers feature.

Requires TRAILER_INTEGRATION_TESTS=1 (real network) and TMDB_API_KEY in env.
Downloads a known-stable trailer to a tmpdir to verify the full stack:
TrailerFinder -> YtdlpDownloader -> placement.trailer_exists().

Skipped in CI by default.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_HAS_TMDB_KEY = bool(os.environ.get("TMDB_READ_ACCESS_TOKEN") or os.environ.get("TMDB_API_KEY"))


@pytest.mark.network
@pytest.mark.skipif(not _HAS_TMDB_KEY, reason="TMDB_READ_ACCESS_TOKEN or TMDB_API_KEY not set")
def test_trailer_finder_and_download_e2e(tmp_path: Path) -> None:
    api_key = os.environ.get("TMDB_READ_ACCESS_TOKEN") or os.environ.get("TMDB_API_KEY")
    assert api_key is not None  # guarded by skipif, here for type narrowing

    from personalscraper.scraper.circuit_breaker import CircuitBreaker
    from personalscraper.scraper.json_ttl_cache import JsonTTLCache
    from personalscraper.scraper.tmdb_client import TMDBClient
    from personalscraper.scraper.trailer_finder import TrailerFinder
    from personalscraper.scraper.trailers_cache import TrailersCache
    from personalscraper.scraper.youtube_search import YoutubeSearch
    from personalscraper.scraper.ytdlp_downloader import DownloadStatus, YtdlpDownloader
    from personalscraper.trailers.placement import trailer_exists, trailer_path_for

    # Big Buck Bunny TMDB ID -- a freely licensed Blender Foundation film,
    # stable since 2017 on the Blender Foundation channel (aqz-KE-bpKQ).
    TMDB_ID = 10378
    TITLE = "Big Buck Bunny"
    YEAR = 2008
    MIN_SIZE = 100 * 1024  # 100 KiB

    # Wire up the discovery stack.
    client = TMDBClient(api_key=api_key, language="en-US")
    cache = TrailersCache(tmp_path / "test_trailers_cache.json")
    searcher = YoutubeSearch(
        query_format="{title} {year} trailer",
        api_key=os.environ.get("YOUTUBE_API_KEY", ""),
        quota_cache=JsonTTLCache(tmp_path / "quota.json"),
        breaker=CircuitBreaker(name="youtube-network-test", failure_threshold=5, cooldown_seconds=60),
    )
    finder = TrailerFinder(
        tmdb_client=client,
        youtube_search=searcher,
        cache=cache,
        languages=["en-US"],
    )

    url = finder.find(TMDB_ID, "movie", title=TITLE, year=YEAR)
    assert url is not None, "TrailerFinder returned None -- no trailer found for Big Buck Bunny"

    # Download to tmpdir.
    movie_dir = tmp_path / f"{TITLE} ({YEAR})"
    movie_dir.mkdir()
    output_path = trailer_path_for(movie_dir, f"{TITLE} ({YEAR})", ext="mp4")

    downloader = YtdlpDownloader(
        output_dir=tmp_path,
        ytdlp_format="worst[ext=mp4]/worst",  # Smallest format for test speed.
        socket_timeout_sec=60,
        retries=2,
        cookie_config=None,
    )
    result = downloader.download(url, output_path)

    assert result.status == DownloadStatus.SUCCESS, (
        f"Download failed with status={result.status}: {result.error_message}"
    )
    assert trailer_exists(output_path, min_size_bytes=MIN_SIZE), f"Trailer file missing or too small: {output_path}"
