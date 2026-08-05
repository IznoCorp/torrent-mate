#!/usr/bin/env python3
"""Capture live provider search payloads as golden fixtures for the search ranking.

The search-ranking golden set (``tests/scraper/test_search_ranking.py``) asserts that
a real-world query surfaces the media a human meant. Asserting that against
hand-written mocks would prove nothing — the whole defect it guards against was a
scoring rule that looked reasonable in isolation and collapsed on real payload
shapes. So the fixtures are captured ONCE from the live providers and committed.

Run it only to refresh the corpus (a provider changing its response shape, or a new
golden query being added). It performs read-only GETs.

Usage:
    python scripts/capture_search_fixtures.py [--out tests/fixtures/search]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# (query, provider, endpoint, label) tuples backing the golden set. Every entry must
# correspond to a media that genuinely exists at the provider — a fabricated
# target would make the golden test assert nothing.
#
# ``label`` is an ASCII slug used for the FILENAME, deliberately decoupled from the
# query: a filename holding CJK characters is stored NFD by macOS and NFC by Linux,
# so a fixture named after a non-Latin query resolves on the dev machine and 404s in
# CI. The query itself lives inside the payload and in the test.
CAPTURES: tuple[tuple[str, str, str, str], ...] = (
    ("monarch", "tmdb", "/search/movie", "monarch"),
    ("monarch", "tmdb", "/search/tv", "monarch"),
    ("monarch", "tvdb", "/search", "monarch"),
    ("spiderman", "tmdb", "/search/movie", "spiderman"),
    ("spiderman", "tvdb", "/search", "spiderman"),
    ("spider man", "tmdb", "/search/movie", "spider-man"),
    ("matrix", "tmdb", "/search/movie", "matrix"),
    ("top chef", "tmdb", "/search/tv", "top-chef"),
    ("top chef", "tvdb", "/search", "top-chef"),
    ("les evades", "tmdb", "/search/movie", "les-evades"),
    ("기생충", "tmdb", "/search/movie", "hangul-parasite"),
    ("進撃の巨人", "tmdb", "/search/tv", "kanji-attack-on-titan"),
)


def _slug(label: str, provider: str, endpoint: str) -> str:
    """Build a filesystem-safe fixture name from a capture entry.

    Args:
        label: ASCII label for the query (never the raw query — see CAPTURES).
        provider: Provider name ("tmdb" or "tvdb").
        endpoint: Provider endpoint path.

    Returns:
        A slug such as ``tmdb-search-movie-monarch``.
    """
    ep = endpoint.strip("/").replace("/", "-")
    return f"{provider}-{ep}-{label}"


def _fetch(registry: Any, query: str, provider: str, endpoint: str) -> Any:
    """Perform one read-only provider search call.

    Args:
        registry: The built provider registry.
        query: The search query.
        provider: Provider name.
        endpoint: Endpoint path.

    Returns:
        The raw JSON payload returned by the provider.
    """
    client = registry.get(provider)
    if provider == "tvdb":
        params: dict[str, Any] = {"query": query, "type": "series"}
    else:
        params = {"query": query, "language": "fr-FR", "page": 1}
    return client._transport.get(endpoint, params=params)  # noqa: SLF001 — capture tool


def main() -> int:
    """Capture every configured payload into the fixture directory.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="tests/fixtures/search", type=Path)
    args = parser.parse_args()

    from personalscraper.cli_helpers import _build_app_context
    from personalscraper.conf.loader import load_config
    from personalscraper.config import Settings

    args.out.mkdir(parents=True, exist_ok=True)
    context = _build_app_context(load_config(), Settings())
    try:
        for query, provider, endpoint, label in CAPTURES:
            payload = _fetch(context.provider_registry, query, provider, endpoint)
            target = args.out / f"{_slug(label, provider, endpoint)}.json"
            target.write_text(
                json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"captured {target}")
    finally:
        context.provider_registry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
