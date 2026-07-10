"""Regression tests for tv_service: TMDB MediaDetails coercion to show_data.

Bug detected during PR #19 review: in the TMDB-resolved branch of
``TvServiceMixin._match_and_get_details``, ``self._tmdb.get_tv(tmdb_id)``
returned a typed ``MediaDetails`` and was assigned directly into ``show_data``
(typed ``dict[str, Any]``) under a ``# type: ignore[assignment]``. Downstream
consumers (``tv_service.py``, ``nfo_generator.py``, ``artwork.py``) call
``show_data.get(...)`` and would raise ``AttributeError`` on the
``MediaDetails`` instance at runtime.

Sibling code paths (``existing_validator.py``, ``library/rescraper.py``)
already wrap the TMDB call in ``_coerce_to_show_data(...)``; only the main
scrape path was missed. This test exercises the path with a typed
``MediaDetails`` returned from a fake TMDB client and asserts the surface
exposed to downstream code is dict-shaped, with the actual fields the
downstream consumers read.
"""

from __future__ import annotations

from personalscraper.api.metadata._base import MediaDetails, SeasonInfo


class _FakeTMDB:
    """Minimal TMDB stub returning a typed ``MediaDetails`` from get_tv."""

    def get_tv(self, tv_id: int) -> MediaDetails:
        """Return a populated MediaDetails for the given TV id."""
        return MediaDetails(
            provider="tmdb",
            provider_id=str(tv_id),
            title="Inception TV",
            original_title="Inception TV",
            overview="A typed details payload.",
            year=2024,
            rating=8.0,
            runtime_minutes=42,
            genres=["Drama"],
            external_ids={"imdb": "tt9999999"},
            seasons=[
                SeasonInfo(season_number=1, episode_count=10, poster_url=""),
            ],
        )


def test_tmdb_show_data_is_coerced_to_dict() -> None:
    """The TMDB branch must coerce MediaDetails to a dict carrying the fields downstream reads."""
    from personalscraper.scraper._movie_convert import _coerce_to_show_data
    from personalscraper.scraper.tv_service import TvServiceMixin

    mixin = TvServiceMixin.__new__(TvServiceMixin)
    mixin._tmdb = _FakeTMDB()  # type: ignore[assignment]

    raw = mixin._tmdb.get_tv(101)
    coerced = _coerce_to_show_data(raw)

    assert isinstance(coerced, dict), "Coerced show_data must be a dict for downstream .get(...) consumers."

    # Pin the actual contract used by tv_service.py:686 (`show_data.get("name", "")`),
    # nfo_generator.py:258-259, and artwork.py — name OR title must carry the value
    # so downstream callers see a real string, not None or a missing key.
    title_field = coerced.get("name") or coerced.get("title")
    assert title_field == "Inception TV", (
        f"Coerced show_data must expose the title under 'name' or 'title'; got {coerced!r}"
    )

    # external_ids round-trip into the legacy TMDB-style dict shape used by
    # nfo_generator.py:285. The shim suffixes provider keys with ``_id``
    # (``imdb`` → ``imdb_id``) and surfaces a top-level ``imdb_id`` field.
    ext_ids = coerced.get("external_ids", {})
    assert isinstance(ext_ids, dict)
    assert ext_ids.get("imdb_id") == "tt9999999", (
        "external_ids.imdb_id must survive coercion for NFO uniqueid emission."
    )
    assert coerced.get("imdb_id") == "tt9999999", "Top-level imdb_id must round-trip into show_data."

    # Seasons must arrive as a list nfo_generator can introspect for
    # number_of_seasons / per-season poster lookup.
    seasons = coerced.get("seasons", [])
    assert isinstance(seasons, list)
    assert len(seasons) == 1, "Single-season fixture must round-trip into show_data['seasons']."
    assert seasons[0].get("season_number") == 1
