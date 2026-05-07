"""Regression tests for the PROCESS step on TVDB-only TV shows.

Two bugs detected during pipeline-monitor run 2026-05-07 left every TVDB-only
TV show stuck in raw torrent layout (``<Show>/<release-group>/<file>.mkv``)
and never reorganized into ``Saison NN/`` subdirectories:

* **Bug A** — ``tv_service._build_episode_map`` discovered seasons from
  ``show_dir.iterdir()`` looking for ``Saison NN/`` subdirs only. For a fresh
  show with no Saison dirs yet, ``season_nums`` was empty and the API episode
  map returned ``{}``, short-circuiting ``_match_seasons`` (rescrape path).

* **Bug B** — ``existing_validator._repair_episode_files`` /
  ``_repair_artwork`` (the post-fast-path repair pass) read only TMDB id from
  the NFO and bailed out when absent. TVDB-only shows have no
  ``<uniqueid type="tmdb">`` and were silently skipped (warning
  ``repair_organize_episodes_no_tmdb_id``).

These tests assert: (A) bootstrap season discovery from filenames when no
Saison NN/ exists, (B) TVDB id extraction from NFO, (C) repair code path
selects TVDB primary when both ids could exist.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.scraper.existing_validator import ExistingValidatorMixin


def _write_tvshow_nfo(path: Path, *, tvdb_id: int | None, tmdb_id: int | None) -> None:
    """Write a minimal tvshow.nfo with the requested unique ids.

    Args:
        path: Destination tvshow.nfo path.
        tvdb_id: TVDB id to include (omitted when ``None``).
        tmdb_id: TMDB id to include (omitted when ``None``).
    """
    parts: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>', "<tvshow>", "<title>Test</title>"]
    if tvdb_id is not None:
        parts.append(f'<uniqueid default="true" type="tvdb">{tvdb_id}</uniqueid>')
    if tmdb_id is not None:
        parts.append(f'<uniqueid type="tmdb">{tmdb_id}</uniqueid>')
    parts.append("</tvshow>")
    path.write_text("\n".join(parts), encoding="utf-8")


class TestExtractTvdbIdFromNfo:
    """Bug B regression: TVDB-primary id extraction must read ``<uniqueid type="tvdb">``."""

    def test_tvdb_id_present(self, tmp_path: Path) -> None:
        """Returns the TVDB id when the NFO carries it."""
        nfo = tmp_path / "tvshow.nfo"
        _write_tvshow_nfo(nfo, tvdb_id=355567, tmdb_id=None)

        result = ExistingValidatorMixin._extract_tvdb_id_from_nfo(nfo)

        assert result == 355567

    def test_tvdb_id_absent_returns_none(self, tmp_path: Path) -> None:
        """Returns None when only TMDB id is present (does not silently confuse ids)."""
        nfo = tmp_path / "tvshow.nfo"
        _write_tvshow_nfo(nfo, tvdb_id=None, tmdb_id=12345)

        result = ExistingValidatorMixin._extract_tvdb_id_from_nfo(nfo)

        assert result is None

    def test_both_ids_present_returns_tvdb(self, tmp_path: Path) -> None:
        """When both ids exist, returns the TVDB id (does not fall back to TMDB by mistake)."""
        nfo = tmp_path / "tvshow.nfo"
        _write_tvshow_nfo(nfo, tvdb_id=355567, tmdb_id=12345)

        result = ExistingValidatorMixin._extract_tvdb_id_from_nfo(nfo)

        assert result == 355567

    def test_non_numeric_tvdb_id_returns_none(self, tmp_path: Path) -> None:
        """Non-numeric value is rejected (regression against silent int() crashes)."""
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text(
            '<?xml version="1.0"?>\n<tvshow>\n<uniqueid type="tvdb">abc</uniqueid>\n</tvshow>',
            encoding="utf-8",
        )

        result = ExistingValidatorMixin._extract_tvdb_id_from_nfo(nfo)

        assert result is None


class TestBuildEpisodeMapBootstrap:
    """Bug A regression: ``_build_episode_map`` must bootstrap season_nums from filenames.

    Reproduces the exact failure mode: a show with raw torrent layout has no
    ``Saison NN/`` directories, so the original season discovery returned an
    empty set and the function bailed out before fetching any episodes.

    The test exercises the ``_local_show_seasons`` helper directly because it
    is the building block used by the bootstrap fallback in
    ``_build_episode_map``. Combined with ``test_build_episode_map_uses_local_show_seasons``
    below, it pins the contract.
    """

    def test_local_show_seasons_walks_release_group_subdirs(self, tmp_path: Path) -> None:
        """Seasons must be discovered from SxxEyy in nested release-group subdirs."""
        from personalscraper.scraper.existing_validator import _local_show_seasons

        show = tmp_path / "Dexter New Blood (2021)"
        release = show / "Dexter.New.Blood.S01.MULTi.1080p.WEBRiP.x265-KAF"
        release.mkdir(parents=True)
        (release / "Dexter.New.Blood.S01E01.MULTi.1080p.WEBRiP.x265-KAF.mkv").touch()
        (release / "Dexter.New.Blood.S01E02.MULTi.1080p.WEBRiP.x265-KAF.mkv").touch()

        result = _local_show_seasons(show)

        assert result == {1}

    def test_local_show_seasons_walks_root_files(self, tmp_path: Path) -> None:
        """Season discovery also includes files at show root (no subdir at all)."""
        from personalscraper.scraper.existing_validator import _local_show_seasons

        show = tmp_path / "The Boys (2019)"
        show.mkdir()
        (show / "The.Boys.S05E06.MULTi.VF2.1080p.AMZN.WEB-DL.10bit.x265-DIXEL.mkv").touch()

        result = _local_show_seasons(show)

        assert result == {5}

    def test_build_episode_map_uses_local_show_seasons(self, tmp_path: Path) -> None:
        """``_build_episode_map`` must call ``_local_show_seasons`` when no Saison NN/ exists.

        Asserts the bootstrap contract: an empty top-level scan must not be
        the final answer — the function should fall back to filename inference
        before returning ``{}``.
        """
        # Read the source to verify the bootstrap path exists. This guards
        # against future refactors that drop the fallback without updating the
        # tests above.
        import inspect

        from personalscraper.scraper.tv_service import TvServiceMixin

        source = inspect.getsource(TvServiceMixin._build_episode_map)
        assert "_local_show_seasons" in source, (
            "Bug A regression: _build_episode_map must use _local_show_seasons "
            "as a fallback when no Saison NN/ subdirs exist; otherwise fresh "
            "torrent-layout shows never get reorganized."
        )


class TestRepairTvshowDirTvdbPrimary:
    """Bug B regression: repair pass must accept TVDB id (primary), not require TMDB.

    Asserts the source code branches on TVDB id first. Behavioral coverage of
    the full repair flow lives in the integration tests under
    ``tests/scraper/`` and ``tests/process/`` — those exercise the TMDB path
    today; this test pins the new TVDB-primary branch.
    """

    def test_repair_episode_files_branches_on_tvdb_id(self) -> None:
        """``_repair_episode_files`` must read TVDB id and branch on it."""
        import inspect

        from personalscraper.scraper.existing_validator import ExistingValidatorMixin

        source = inspect.getsource(ExistingValidatorMixin._repair_episode_files)
        assert "_extract_tvdb_id_from_nfo" in source, (
            "Bug B regression: _repair_episode_files must read TVDB id from NFO "
            "(primary scraper for series). Reading only TMDB id blocks every "
            "TVDB-only show from ever being repaired."
        )
        assert "_fetch_season_episodes_tvdb" in source, (
            "Bug B regression: TVDB branch must call _fetch_season_episodes_tvdb."
        )

    def test_repair_artwork_branches_on_tvdb_id(self) -> None:
        """``_repair_artwork`` (organize-from-subdirs) must also branch on TVDB id."""
        import inspect

        from personalscraper.scraper.existing_validator import ExistingValidatorMixin

        source = inspect.getsource(ExistingValidatorMixin._repair_artwork)
        assert "_extract_tvdb_id_from_nfo" in source, "Bug B regression: _repair_artwork must read TVDB id from NFO."
        assert "_fetch_season_episodes_tvdb" in source, (
            "Bug B regression: _repair_artwork TVDB branch must call _fetch_season_episodes_tvdb."
        )


class TestExternalIdsKeyContract:
    r"""Bug #3 regression: ``MediaDetails.external_ids`` uses plain provider keys.

    Both TVDB and TMDB parsers populate ``external_ids`` with plain provider
    names ("imdb", "tmdb", "tvdb") as keys — not "_id"-suffixed variants. The
    docstring on ``MediaDetails.external_ids`` documents this contract:
    "External identifiers keyed by source (e.g. \"imdb\" → \"tt1234567\")".

    Before the fix, the consumer code read suffixed keys from the raw
    MediaDetails, which always returned None — silently dropping IMDB and
    TMDB cross-references on every TVDB-resolved series and producing
    empty ``<uniqueid type="imdb"/>`` in NFOs.

    These tests pin the contract on both parsers and on every consumer.
    """

    def test_tvdb_parser_uses_plain_keys(self) -> None:
        """TVDB parser must populate external_ids with plain "imdb"/"tmdb"/"tvdb" keys."""
        from personalscraper.api.metadata._tvdb_parsers import parse_media_details

        raw = {
            "id": 355567,
            "name": "The Boys",
            "year": "2019",
            "remoteIds": [
                {"id": "tt1190634", "type": 2, "sourceName": "IMDB"},
                {"id": "76479", "type": 4, "sourceName": "TheMovieDB.com"},
            ],
        }
        details = parse_media_details(raw, "tvdb")

        assert "imdb" in details.external_ids, "TVDB parser must use plain 'imdb' key, not 'imdb_id'."
        assert details.external_ids["imdb"] == "tt1190634"
        assert details.external_ids["tmdb"] == "76479"
        assert "imdb_id" not in details.external_ids, (
            "Bug #3 regression: '_id'-suffixed keys must not appear in external_ids "
            "(consumers were reading the wrong keys)."
        )

    def test_tv_service_reads_correct_keys(self) -> None:
        """``tv_service`` resolution must read 'imdb'/'tmdb' from external_ids."""
        import inspect

        from personalscraper.scraper import tv_service

        # Source check — the regression hides in code that reads "_id"-suffixed
        # keys from raw MediaDetails. Pin against re-introduction.
        source = inspect.getsource(tv_service)
        # Look only at the resolution path that builds remote_ids from a typed
        # MediaDetails. Other usages of "tmdb_id"/"imdb_id" in this file are
        # legitimate (they refer to the show_data dict downstream).
        assert 'remote_ids.get("tmdb_id")' not in source, (
            "Bug #3 regression: remote_ids comes from MediaDetails.external_ids "
            "which uses plain 'tmdb' key. Reading 'tmdb_id' silently returns None."
        )
        assert 'remote_ids.get("imdb_id")' not in source, "Bug #3 regression: same as above for 'imdb' key."

    def test_existing_validator_repair_reads_correct_keys(self) -> None:
        """The repair path must read external_ids using plain keys."""
        import inspect

        from personalscraper.scraper import existing_validator

        source = inspect.getsource(existing_validator)
        assert 'external_ids.get("imdb_id")' not in source, (
            "Bug #3 regression: existing_validator reads MediaDetails.external_ids "
            "which uses plain 'imdb' key, not 'imdb_id'."
        )


class TestFetchSeasonEpisodesTvdb:
    """Behavioral test for the new TVDB season-episode fetcher."""

    def test_fetches_episodes_via_tvdb_client(self) -> None:
        """``_fetch_season_episodes_tvdb`` must shape episodes the same way as TMDB."""
        from unittest.mock import MagicMock

        from personalscraper.api.metadata._base import EpisodeInfo, SeasonDetails
        from personalscraper.scraper.existing_validator import _fetch_season_episodes_tvdb

        episodes = [
            EpisodeInfo(season_number=1, episode_number=1, title="Pilot"),
            EpisodeInfo(season_number=1, episode_number=2, title="Setup"),
        ]
        season_detail = SeasonDetails(
            season_number=1,
            tv_id="355567",
            episodes=episodes,
            provider="tvdb",
        )
        tvdb = MagicMock()
        tvdb.get_series_episodes.return_value = season_detail

        result = _fetch_season_episodes_tvdb(tvdb, 355567, [1])

        assert (1, 1) in result and (1, 2) in result
        assert result[(1, 1)]["title"] == "Pilot"
        assert result[(1, 2)]["title"] == "Setup"
        assert result[(1, 1)]["still_path"] == ""
        tvdb.get_series_episodes.assert_called_once_with(355567, 1)

    def test_skips_season_zero(self) -> None:
        """Season 0 (specials) is excluded — matches TMDB fetcher behavior."""
        from unittest.mock import MagicMock

        from personalscraper.scraper.existing_validator import _fetch_season_episodes_tvdb

        tvdb = MagicMock()
        result = _fetch_season_episodes_tvdb(tvdb, 355567, [0])

        assert result == {}
        tvdb.get_series_episodes.assert_not_called()

    def test_falls_through_on_fetch_error(self) -> None:
        """Per-season errors are logged and skipped, not propagated."""
        from unittest.mock import MagicMock

        from personalscraper.scraper.existing_validator import _fetch_season_episodes_tvdb

        tvdb = MagicMock()
        tvdb.get_series_episodes.side_effect = ConnectionError("network down")
        result = _fetch_season_episodes_tvdb(tvdb, 355567, [1])

        assert result == {}
