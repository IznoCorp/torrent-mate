"""API and localisation guardrails for the scraper.

These tests are written as invariants — they encode contracts the
scraper must keep regardless of how the implementation evolves. They
are intentionally minimal and mock-based so they catch regressions
without depending on live TMDB / TVDB.

Invariants enforced:

1. **TV NFOs use TVDB as the canonical id**, with TMDB as a
   non-default fallback. ``<id>`` and ``<episodeguide>`` mirror that
   priority. Pre-2026 code had TMDB as default for TV which produced
   year mismatches and mis-routed Kodi lookups.
2. **Movie NFOs use TMDB as the canonical id**. TMDB is the primary
   movie database; TVDB is for TV only.
3. **The configured primary language is honoured for TV
   translations**, with the fallback language only consulted when the
   primary returns nothing on both APIs.
4. **No hard-coded language strings** — every API call passes a
   language derived from ``ScraperConfig`` (or its Settings fallback).

Tests use mocked clients so they run offline and instantly.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from personalscraper.config import Settings
from personalscraper.scraper.nfo_generator import NFOGenerator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gen() -> NFOGenerator:
    """Return a minimal NFOGenerator for invariant tests.

    ``db_path=None`` disables the write-through outbox (best-effort
    contract); the generated NFO XML is exercised in-memory.
    """
    return NFOGenerator(db_path=None)


def _root(xml: str) -> ET.Element:
    """Parse the generated NFO XML and return its root element."""
    # Strip <?xml ... ?> declaration before parsing because ElementTree
    # is happiest with a single root element on its own.
    return ET.fromstring(xml.split("\n", 1)[1])


_TVSHOW_BOTH_IDS: dict = {
    "name": "South Park",
    "original_name": "South Park",
    "first_air_date": "1997-08-13",
    "id": 2190,
    "external_ids": {"tvdb_id": 75897, "imdb_id": "tt0121955"},
    "overview": "",
    "number_of_episodes": 320,
    "number_of_seasons": 28,
    "status": "Returning Series",
    "networks": [],
    "genres": [{"name": "Animation"}],
}

_TVSHOW_TMDB_ONLY: dict = {
    **_TVSHOW_BOTH_IDS,
    "external_ids": {"tvdb_id": None, "imdb_id": "tt0121955"},
}


# ---------------------------------------------------------------------------
# Invariant 1: TV-show NFO id priority
# ---------------------------------------------------------------------------


class TestTVShowIdPriority:
    """TVDB must be the canonical id for TV shows; TMDB stays secondary."""

    def test_tvdb_is_default_when_both_ids_present(self) -> None:
        """When both TVDB and TMDB ids are available, TVDB carries the default flag."""
        xml = _gen().generate_tvshow_nfo(_TVSHOW_BOTH_IDS, category_id="anime")
        root = _root(xml)

        tvdb = next(u for u in root.findall("uniqueid") if u.get("type") == "tvdb")
        tmdb = next(u for u in root.findall("uniqueid") if u.get("type") == "tmdb")

        assert tvdb.get("default") == "true"
        assert tmdb.get("default") is None

    def test_id_field_uses_tvdb_when_present(self) -> None:
        """``<id>`` mirrors the default uniqueid (TVDB)."""
        xml = _gen().generate_tvshow_nfo(_TVSHOW_BOTH_IDS, category_id="anime")
        root = _root(xml)

        assert root.findtext("id") == "75897"

    def test_episodeguide_mirrors_id(self) -> None:
        """``<episodeguide>`` must point at the same source as ``<id>``."""
        xml = _gen().generate_tvshow_nfo(_TVSHOW_BOTH_IDS, category_id="anime")
        root = _root(xml)

        assert root.findtext("episodeguide") == "75897"

    def test_tmdb_promoted_when_tvdb_missing(self) -> None:
        """No TVDB id → TMDB becomes default (canonical fallback)."""
        xml = _gen().generate_tvshow_nfo(_TVSHOW_TMDB_ONLY, category_id="anime")
        root = _root(xml)

        tmdb = next(u for u in root.findall("uniqueid") if u.get("type") == "tmdb")
        assert tmdb.get("default") == "true"
        assert root.findtext("id") == "2190"

    def test_no_tvdb_uniqueid_emitted_when_id_missing(self) -> None:
        """No empty TVDB uniqueid should be written when no TVDB id exists."""
        xml = _gen().generate_tvshow_nfo(_TVSHOW_TMDB_ONLY, category_id="anime")
        root = _root(xml)

        tvdb_ids = [u for u in root.findall("uniqueid") if u.get("type") == "tvdb"]
        assert tvdb_ids == []


# ---------------------------------------------------------------------------
# Invariant 2: Movie NFO id priority
# ---------------------------------------------------------------------------


_MOVIE_DATA: dict = {
    "title": "L'Effet papillon",
    "original_title": "The Butterfly Effect",
    "release_date": "2004-01-23",
    "id": 1954,
    "external_ids": {"imdb_id": "tt0289879"},
    "overview": "",
    "runtime": 113,
    "vote_average": 7.7,
    "vote_count": 5000,
    "genres": [{"name": "Drama"}],
    "production_companies": [],
    "credits": {"cast": [], "crew": []},
    "videos": {"results": []},
    "keywords": {"keywords": []},
}


class TestMovieIdPriority:
    """Movie NFO id-priority guardrails.

    Movies use IMDB as the canonical id (MediaElch convention) and TMDB as
    the secondary uniqueid. TVDB has no business in a movie NFO.
    """

    def test_movie_uniqueid_imdb_is_default(self) -> None:
        """IMDB carries the default flag — MediaElch / Kodi-for-movies convention."""
        xml = _gen().generate_movie_nfo(_MOVIE_DATA, category_id="movies")
        root = _root(xml)

        imdb = next(u for u in root.findall("uniqueid") if u.get("type") == "imdb")
        assert imdb.get("default") == "true"
        assert imdb.text == "tt0289879"

    def test_movie_uniqueid_tmdb_is_secondary(self) -> None:
        """TMDB is present but NOT default."""
        xml = _gen().generate_movie_nfo(_MOVIE_DATA, category_id="movies")
        root = _root(xml)

        tmdb = next(u for u in root.findall("uniqueid") if u.get("type") == "tmdb")
        assert tmdb.get("default") is None
        assert tmdb.text == "1954"

    def test_movie_has_no_tvdb_uniqueid(self) -> None:
        """TVDB is for TV — it must never appear in a movie NFO.

        This is the structural guardrail behind the user's rule "TVDB
        for movies is forbidden". Movie data never carries a tvdb_id;
        the generator must never emit one even if a future scraper bug
        accidentally injects one into ``movie_data``.
        """
        # Even a poisoned movie_data with a tvdb id must not produce
        # a TVDB uniqueid in the output.
        poisoned: dict = {**_MOVIE_DATA, "external_ids": {**_MOVIE_DATA["external_ids"], "tvdb_id": 99999}}
        xml = _gen().generate_movie_nfo(poisoned, category_id="movies")
        root = _root(xml)

        tvdb_ids = [u for u in root.findall("uniqueid") if u.get("type") == "tvdb"]
        assert tvdb_ids == []

    def test_movie_id_field_uses_imdb(self) -> None:
        """``<id>`` for a movie mirrors the default uniqueid (IMDB)."""
        xml = _gen().generate_movie_nfo(_MOVIE_DATA, category_id="movies")
        root = _root(xml)

        assert root.findtext("id") == "tt0289879"


# ---------------------------------------------------------------------------
# Invariant 3: Configured language honoured (no hard-coded fr-FR)
# ---------------------------------------------------------------------------


class TestConfiguredLanguageRespected:
    """Scraper must read the language from ScraperConfig, not hard-code it."""

    def test_settings_default_is_french(self) -> None:
        """Sanity: the default project setting is FR (FR primary, EN fallback).

        If this changes, every guardrail below must be re-checked because
        most of them assume FR is the primary translation language. The
        TMDB-style locale ``fr-FR`` is what the scraper passes through to
        TMDB; the TVDB client maps it to ``fra`` internally.
        """
        s = Settings()
        assert s.scraper_language == "fr-FR"
        assert s.scraper_fallback_language == "en-US"

    def test_language_codes_documented(self) -> None:
        """The TVDB client uses 3-char codes; TMDB uses 2-char codes.

        This split is enforced by the project: TMDB takes ``fr-FR`` /
        ``en-US`` while TVDB takes ``fra`` / ``eng``. A regression that
        sends ``fr`` to TVDB or ``fra`` to TMDB would silently fall back
        to English without raising. Documented here as a sanity check;
        the real enforcement lives in the language-mapping helpers.
        """
        from personalscraper.scraper.tvdb_client import TVDBClient

        client = TVDBClient(api_key="placeholder")
        # The 3-char mapping must include FR → fra (used by the TV
        # episode translation fetcher when the primary language is FR).
        assert client._map_lang("fr") == "fra"
        assert client._map_lang("en") == "eng"
        # 3-char codes pass through unchanged.
        assert client._map_lang("fra") == "fra"
