"""Regression tests for DEV #2 of the ``provider-ids`` feature.

DEV #2 (pipeline-monitor run 2026-05-17) : episode-level NFOs are
written *without* any ``<uniqueid>`` tag because the per-episode
provider IDs are never propagated. The five-layer root cause :

1. ``EpisodeInfo`` did not expose the IDs the parsers had access to.
2. ``_tvdb_parsers.parse_episode`` / ``_tmdb_parsers.parse_episode``
   dropped the upstream ``id`` / ``external_ids`` fields.
3. ``TvServiceMixin._build_episode_map._tvdb_fetch`` and
   ``_tmdb_fetch`` built per-episode payloads as
   ``{"title", "still_path"}`` only.
4. ``match_episode_files`` copied a hard-coded subset of keys into the
   ``matched`` dict — anything else was discarded.
5. ``_generate_episode_nfos`` then passed literal ``"tvdb_id": ""``,
   ``"id": ""`` to the NFO generator, which (correctly) omitted the
   ``<uniqueid>`` tag because the values were blank.

This file exercises layers 3, 4 and 5 against the legacy implementation
to prove the bug, then locks in the post-fix shape so the regression
cannot resurface. All tests run without network access — TVDB / TMDB
clients are :class:`unittest.mock.MagicMock`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata._base import EpisodeInfo, SeasonDetails
from personalscraper.naming_patterns import PATTERNS, NamingPatterns
from personalscraper.scraper.confidence import MatchResult
from personalscraper.scraper.episode_manager import match_episode_files
from personalscraper.scraper.nfo_generator import NFOGenerator
from personalscraper.scraper.tv_service import TvServiceMixin

# ---------------------------------------------------------------------------
# Helpers (mirror tests/scraper/test_tv_service_extra.py)
# ---------------------------------------------------------------------------


def _make_mixin(
    *,
    tvdb: Any = None,
    tmdb: Any = None,
    patterns: NamingPatterns | None = None,
) -> TvServiceMixin:
    """Build a :class:`TvServiceMixin` with the minimum attributes the methods touch.

    The mixin instance is constructed via ``__new__`` to skip the
    real constructor (which would require a full ``Config`` + every
    collaborator). Only the methods under test in this regression
    suite are exercised, so the missing attributes never come into
    play.
    """
    mixin = TvServiceMixin.__new__(TvServiceMixin)
    mixin.dry_run = False

    _tvdb_client = tvdb if tvdb is not None else MagicMock()
    _tmdb_client = tmdb if tmdb is not None else MagicMock()
    # Sub-phase 7.2 — the chain iteration path reads ``provider_name`` to
    # dispatch per-provider matching and episode fetching. Set the
    # attribute here so the chain helpers route correctly.
    _tvdb_client.provider_name = "tvdb"
    _tmdb_client.provider_name = "tmdb"
    _registry = MagicMock()
    _registry.get.side_effect = (
        lambda name,
        _cache={  # type: ignore[misc]
            "tmdb": _tmdb_client,
            "tvdb": _tvdb_client,
        }: _cache.get(name, MagicMock())
    )
    _registry.chain.return_value = [_tvdb_client, _tmdb_client]
    _registry._emit_provider_fallback = MagicMock()
    _registry._emit_provider_exhausted = MagicMock()
    mixin._registry = _registry  # type: ignore[assignment]
    mixin._tvdb = _tvdb_client  # type: ignore[assignment]
    mixin._tmdb = _tmdb_client  # type: ignore[assignment]
    mixin._nfo = MagicMock()  # type: ignore[assignment]
    mixin._artwork = MagicMock()  # type: ignore[assignment]
    mixin.config = None  # type: ignore[assignment]
    mixin.patterns = patterns or PATTERNS  # type: ignore[assignment]
    mixin._scraper_language = "fr-FR"
    mixin._scraper_fallback_language = "en-US"
    mixin._tvdb_language = "fra"
    mixin._tvdb_fallback_language = "eng"
    return mixin


# ---------------------------------------------------------------------------
# 2.1 (a) — _tvdb_fetch must surface tvdb_episode_id
# ---------------------------------------------------------------------------


def test_regression_dev2_build_episode_map_propagates_episode_id(tmp_path: Path) -> None:
    """``_build_episode_map`` TVDB branch carries ``tvdb_episode_id`` per episode.

    Failing before the phase 2.2 fix : the legacy ``_tvdb_fetch`` built
    payloads as ``{"title", "still_path"}`` only, dropping the TVDB
    episode ID even though the parser had it. Post-fix : the payload
    exposes ``tvdb_episode_id`` so :func:`match_episode_files` can
    propagate it to the NFO writer.
    """
    show = tmp_path / "Show"
    show.mkdir()
    (show / "Show.S01E01.mkv").write_bytes(b"x")
    tvdb = MagicMock()
    tvdb.get_series_episodes.return_value = SeasonDetails(
        provider="tvdb",
        tv_id="42",
        season_number=1,
        episodes=[
            EpisodeInfo(
                episode_number=1,
                title="Pilot",
                external_ids={"tvdb": "9001", "imdb": "tt0000001"},
            ),
        ],
    )
    mixin = _make_mixin(tvdb=tvdb)
    match = MatchResult(api_id=42, api_title="X", api_year=2020, confidence=0.9, source="tvdb")

    out = mixin._build_episode_map(show, match, tmdb_id=None, episode_default_name="Episode")

    assert (1, 1) in out
    assert out[(1, 1)]["tvdb_episode_id"] == "9001"
    # IMDb piggy-backs on the TVDB payload when the upstream parser surfaces it.
    assert out[(1, 1)]["imdb_episode_id"] == "tt0000001"


# ---------------------------------------------------------------------------
# 2.1 (b) — _tmdb_fetch must surface tmdb_episode_id (+ imdb if available)
# ---------------------------------------------------------------------------


def test_regression_dev2_build_episode_map_propagates_tmdb_and_imdb_episode_id(
    tmp_path: Path,
) -> None:
    """``_build_episode_map`` TMDB branch carries ``tmdb_episode_id`` + ``imdb_episode_id``.

    Failing before the phase 2.2 fix : the legacy ``_tmdb_fetch``
    dropped the ID from the TMDB payload — neither ``tmdb_episode_id``
    nor ``imdb_episode_id`` reached the matched dict.
    """
    show = tmp_path / "Show"
    show.mkdir()
    (show / "Show.S02E05.mkv").write_bytes(b"x")
    tmdb = MagicMock()
    tmdb.get_tv_season.return_value = SeasonDetails(
        provider="tmdb",
        tv_id="100",
        season_number=2,
        episodes=[
            EpisodeInfo(
                episode_number=5,
                title="Five",
                external_ids={"tmdb": "5005", "imdb": "tt0050050"},
            ),
        ],
    )
    mixin = _make_mixin(tmdb=tmdb)
    match = MatchResult(api_id=100, api_title="X", api_year=2020, confidence=0.9, source="tmdb")

    out = mixin._build_episode_map(show, match, tmdb_id=100, episode_default_name="Episode")

    assert (2, 5) in out
    assert out[(2, 5)]["tmdb_episode_id"] == "5005"
    assert out[(2, 5)]["imdb_episode_id"] == "tt0050050"


# ---------------------------------------------------------------------------
# 2.1 (c) — match_episode_files must pass IDs through unchanged
# ---------------------------------------------------------------------------


def test_regression_dev2_match_episode_files_propagates_provider_ids(
    tmp_path: Path,
) -> None:
    """``match_episode_files`` propagates ``*_episode_id`` keys to the matched dict.

    Failing before the phase 2.3 fix : the matcher copied a hard-coded
    subset (``title``, ``still_path``) into the matched dict, so even
    when ``_build_episode_map`` carried the IDs they never reached
    ``_generate_episode_nfos``.
    """
    video = tmp_path / "Show.S01E01.mkv"
    video.write_bytes(b"x")
    api_episodes = {
        (1, 1): {
            "title": "Pilot",
            "still_path": "",
            "tvdb_episode_id": "9001",
            "tmdb_episode_id": "5005",
            "imdb_episode_id": "tt0000001",
        }
    }

    matched = match_episode_files([video], api_episodes)

    assert video in matched
    assert matched[video]["tvdb_episode_id"] == "9001"
    assert matched[video]["tmdb_episode_id"] == "5005"
    assert matched[video]["imdb_episode_id"] == "tt0000001"


# ---------------------------------------------------------------------------
# 2.1 (d) — generate_episode_nfo writes <uniqueid type="tvdb"> when populated
# ---------------------------------------------------------------------------


def test_regression_dev2_generate_episode_nfo_writes_uniqueid_when_id_propagated(
    tmp_path: Path,
) -> None:
    """``_generate_episode_nfos`` forwards propagated IDs to ``generate_episode_nfo``.

    Failing before the phase 2.4 fix : the legacy
    ``_generate_episode_nfos`` body unconditionally set
    ``"id": "", "tvdb_id": ""`` in the ``episode_data`` dict, throwing
    away whatever ``_build_episode_map`` and ``match_episode_files``
    had propagated. The NFO generator then (correctly) omitted the
    ``<uniqueid>`` tag for those blank values. Post-fix : the IDs
    coming from the matched dict reach ``generate_episode_nfo`` and
    the resulting XML carries ``<uniqueid type="tvdb">``.
    """
    show_dir = tmp_path / "Show"
    (show_dir / "Saison 01").mkdir(parents=True)
    video_path = show_dir / "Show.S01E01.mkv"
    video_path.write_bytes(b"x")
    nfo = NFOGenerator()
    nfo_spy = MagicMock(spec=NFOGenerator, wraps=nfo)
    mixin = _make_mixin()
    mixin._nfo = nfo_spy  # type: ignore[assignment]
    mixin.dry_run = True  # skip the on-disk write

    matched = {
        video_path: {
            "season": 1,
            "episode": 1,
            "api_title": "Pilot",
            "still_path": "",
            "fallback": False,
            "tvdb_episode_id": "9001",
            "tmdb_episode_id": "5005",
            "imdb_episode_id": "tt0000001",
        }
    }

    mixin._generate_episode_nfos(matched, show_dir, {"name": "Show", "networks": []})

    assert nfo_spy.generate_episode_nfo.call_count == 1
    episode_data = nfo_spy.generate_episode_nfo.call_args.args[0]
    # The propagated IDs reach the NFO writer rather than being overwritten with "".
    assert episode_data.get("tvdb_id") == "9001"
    assert episode_data.get("id") == "5005" or episode_data.get("tmdb_id") == "5005"


# ---------------------------------------------------------------------------
# Sanity — confirm the legacy behaviour is reproducible (executable doc)
# ---------------------------------------------------------------------------


def test_generate_episode_nfo_omits_uniqueid_when_id_blank() -> None:
    """Blank IDs continue to produce no ``<uniqueid>`` tag (preserves existing semantics).

    This test guards against an overreaction to the DEV #2 fix : the
    NFO writer must still omit the tag when the caller has no valid
    ID. The phase 2 fix only changes what the caller *passes*, not how
    blank values are rendered.
    """
    nfo = NFOGenerator()
    xml = nfo.generate_episode_nfo(
        {
            "name": "Pilot",
            "showtitle": "Show",
            "tvdb_id": "",
            "id": "",
            "season_number": 1,
            "episode_number": 1,
            "overview": "",
            "mpaa": "",
            "studio": "",
            "crew": [],
            "still_path": "",
        }
    )
    assert "<uniqueid" not in xml


# pytest entry-point sanity — ensures the module is picked up.
if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
