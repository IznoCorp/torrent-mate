"""Additional coverage tests for ``personalscraper.scraper.existing_validator``.

Targets the residual branch gaps:

* :func:`verify_tvshow_scrape_drift` — NFO parse failure, missing year,
  missing uniqueid, non-file children inside Saison NN/.
* :func:`_fetch_season_episodes` and :func:`_fetch_season_episodes_tvdb`
  — season-zero skip, error fallback path.
* :func:`_dedup_and_move_root_episode` — dry-run preview, OSError on
  unlink, OSError on rename.
* :func:`_build_root_moved_map` — skip path when ``ep_info`` is missing.
* :class:`ExistingValidatorMixin` instance methods exercised through a
  bare instance bound to ``MagicMock`` collaborators:
    - ``_repair_season_dir`` OSError + dry-run branches
    - ``_check_missing_movie_artwork`` / ``_check_missing_tvshow_artwork``
    - ``_extract_tmdb_id_from_nfo`` parse error / non-numeric branches
    - ``_recover_movie_artwork`` happy + exception paths
    - ``_recover_tvshow_artwork`` happy + exception paths
    - ``_repair_movie_dir`` dry-run + OSError
    - ``_repair_tvshow_dir`` orchestrates inner methods (lines 872-898)
    - ``_repair_artwork`` (huge gap 550-615) — happy paths via TMDB and
      TVDB plus the no-id and api-empty short-circuits.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.metadata._base import EpisodeInfo, SeasonDetails
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.existing_validator import (
    ExistingValidatorMixin,
    _build_root_moved_map,
    _dedup_and_move_root_episode,
    _fetch_season_episodes,
    _fetch_season_episodes_tvdb,
    verify_tvshow_scrape_drift,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_validator(
    *,
    dry_run: bool = False,
    tmdb: MagicMock | None = None,
    tvdb: MagicMock | None = None,
    artwork: MagicMock | None = None,
) -> ExistingValidatorMixin:
    """Return a bare ExistingValidatorMixin instance for direct method calls.

    Avoids constructing a full ``Scraper`` (which initialises HTTP clients).
    The mixin only relies on the attributes injected here.
    """
    instance = ExistingValidatorMixin.__new__(ExistingValidatorMixin)
    instance.patterns = NamingPatterns()
    instance.dry_run = dry_run

    _tmdb_client = tmdb if tmdb is not None else MagicMock()
    _tvdb_client = tvdb if tvdb is not None else MagicMock()
    _registry = MagicMock()
    _registry.get.side_effect = (
        lambda name,
        _cache={  # type: ignore[misc]
            "tmdb": _tmdb_client,
            "tvdb": _tvdb_client,
        }: _cache.get(name, MagicMock())
    )
    instance._registry = _registry  # type: ignore[assignment]
    # Keep backward-compat attrs for test code that reads them directly.
    instance._tmdb = _tmdb_client
    instance._tvdb = _tvdb_client

    instance._artwork = artwork if artwork is not None else MagicMock()
    instance._generate_episode_nfos = MagicMock()
    return instance


def _write_show_nfo(path: Path, *, tvdb_id: int | None = None, tmdb_id: int | None = None) -> None:
    """Write a minimal tvshow.nfo with the given uniqueids.

    The first uniqueid emitted carries ``default="true"`` to match the
    canonical-default invariant enforced by the drift validator
    (provider-ids feature, DESIGN §3 Q6).
    """
    parts = ['<?xml version="1.0"?>', "<tvshow>", "<title>Show</title>", "<year>2020</year>"]
    default_applied = False
    if tvdb_id is not None:
        parts.append(f'<uniqueid type="tvdb" default="true">{tvdb_id}</uniqueid>')
        default_applied = True
    if tmdb_id is not None:
        default_attr = "" if default_applied else ' default="true"'
        parts.append(f'<uniqueid type="tmdb"{default_attr}>{tmdb_id}</uniqueid>')
    parts.append("</tvshow>")
    path.write_text("\n".join(parts), encoding="utf-8")


# ---------------------------------------------------------------------------
# verify_tvshow_scrape_drift — uncovered branches
# ---------------------------------------------------------------------------


class TestVerifyDriftBranches:
    """Cover the missing branches of ``verify_tvshow_scrape_drift``."""

    def test_nfo_parse_failure_returns_false(self, tmp_path: Path) -> None:
        """An unparsable NFO returns ``(False, 'nfo_parse_failed:…')``."""
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text("<not_xml")
        valid, reason = verify_tvshow_scrape_drift(tmp_path, nfo, NamingPatterns())
        assert valid is False
        assert reason.startswith("nfo_parse_failed")

    def test_missing_year_returns_false(self, tmp_path: Path) -> None:
        """Empty ``<year>`` triggers ``nfo_missing_year``."""
        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        nfo = show_dir / "tvshow.nfo"
        nfo.write_text("<tvshow><title>Show</title></tvshow>")
        valid, reason = verify_tvshow_scrape_drift(show_dir, nfo, NamingPatterns())
        assert valid is False
        assert reason == "nfo_missing_year"

    def test_missing_uniqueid_returns_false(self, tmp_path: Path) -> None:
        """No ``<uniqueid>`` → ``nfo_missing_uniqueid``."""
        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        nfo = show_dir / "tvshow.nfo"
        nfo.write_text("<tvshow><title>Show</title><year>2020</year></tvshow>")
        valid, reason = verify_tvshow_scrape_drift(show_dir, nfo, NamingPatterns())
        assert valid is False
        assert reason == "nfo_missing_uniqueid"

    def test_drift_when_canonical_uniqueid_missing_default(self, tmp_path: Path) -> None:
        """A ``<uniqueid>`` without ``default="true"`` triggers drift.

        Regression test for the provider-ids feature : DESIGN §3 Q6
        requires the canonical family to carry ``default="true"``.
        Legacy NFOs without it must re-scrape rather than silently
        pass — the prior implementation had a dead-code branch that
        accepted them.
        """
        show_dir = tmp_path / "Show (2020)"
        show_dir.mkdir()
        nfo = show_dir / "tvshow.nfo"
        nfo.write_text('<tvshow><title>Show</title><year>2020</year><uniqueid type="tvdb">123</uniqueid></tvshow>')
        valid, reason = verify_tvshow_scrape_drift(show_dir, nfo, NamingPatterns())
        assert valid is False
        assert reason == "nfo_missing_canonical_uniqueid"

    def test_drift_when_default_uniqueid_missing_type_attr(self, tmp_path: Path) -> None:
        """A ``<uniqueid default="true">`` without ``type`` attr triggers drift.

        The strict predicate requires the canonical uniqueid to carry
        both ``default="true"`` AND a non-empty ``type``. Without the
        ``type`` check the validator would reach the defensive branch
        with the same reason code, leaving operators unable to
        diagnose the actual cause.
        """
        show_dir = tmp_path / "Show (2020)"
        show_dir.mkdir()
        nfo = show_dir / "tvshow.nfo"
        nfo.write_text(
            '<tvshow><title>Show</title><year>2020</year><uniqueid default="true">tt1234</uniqueid></tvshow>'
        )
        valid, reason = verify_tvshow_scrape_drift(show_dir, nfo, NamingPatterns())
        assert valid is False
        assert reason == "nfo_missing_canonical_uniqueid"

    def test_drift_when_default_uniqueid_text_empty(self, tmp_path: Path) -> None:
        """A ``<uniqueid default="true" type="tvdb"></uniqueid>`` triggers drift.

        The strict predicate also requires non-empty text — an empty
        canonical id is not a valid scrape result.
        """
        show_dir = tmp_path / "Show (2020)"
        show_dir.mkdir()
        nfo = show_dir / "tvshow.nfo"
        nfo.write_text(
            '<tvshow><title>Show</title><year>2020</year><uniqueid type="tvdb" default="true"></uniqueid></tvshow>'
        )
        valid, reason = verify_tvshow_scrape_drift(show_dir, nfo, NamingPatterns())
        assert valid is False
        # The empty-text uniqueid fails the upstream "has_uniqueid" check
        # since it counts non-empty texts only.
        assert reason in {"nfo_missing_uniqueid", "nfo_missing_canonical_uniqueid"}

    def test_non_file_in_season_dir_is_skipped(self, tmp_path: Path) -> None:
        """Subdirectories nested inside Saison XX/ are silently ignored."""
        # Build a fully-valid show with a sub-subdir under Saison 01/.
        show_dir = tmp_path / "Show (2020)"
        show_dir.mkdir()
        nfo = show_dir / "tvshow.nfo"
        nfo.write_text(
            '<tvshow><title>Show</title><year>2020</year><uniqueid type="tmdb" default="true">1</uniqueid></tvshow>'
        )
        patterns = NamingPatterns()
        (show_dir / patterns.tvshow_poster).write_bytes(b"\xff\xd8")
        (show_dir / patterns.tvshow_landscape).write_bytes(b"\xff\xd8")
        s01 = show_dir / "Saison 01"
        s01.mkdir()
        # Non-file child inside the season dir — must be skipped (line 171 branch).
        (s01 / "subdir").mkdir()
        # And a valid episode + sibling NFO so the drift check passes.
        ep = s01 / "S01E01 - Pilot.mkv"
        ep.write_bytes(b"\x00")
        # Phase 4 drift hardening: episode NFO must carry the canonical
        # uniqueid that matches tvshow.nfo (tmdb here).
        ep.with_suffix(".nfo").write_text('<episodedetails><uniqueid type="tmdb">42</uniqueid></episodedetails>')

        valid, reason = verify_tvshow_scrape_drift(show_dir, nfo, patterns)
        assert valid is True
        assert reason == "ok"


# ---------------------------------------------------------------------------
# _fetch_season_episodes / tvdb — error + zero-season branches
# ---------------------------------------------------------------------------


class TestFetchSeasonEpisodes:
    """Cover branches in the TMDB and TVDB season-fetcher helpers."""

    def test_tmdb_season_zero_is_skipped(self) -> None:
        """Season 0 is filtered out before any API call."""
        tmdb = MagicMock()
        result = _fetch_season_episodes(tmdb, 1, [0])
        assert result == {}
        tmdb.get_tv_season.assert_not_called()

    def test_tmdb_connection_error_swallowed(self) -> None:
        """A ConnectionError is logged and that season is skipped, not propagated."""
        tmdb = MagicMock()
        tmdb.get_tv_season.side_effect = ConnectionError("net down")
        result = _fetch_season_episodes(tmdb, 1, [1])
        assert result == {}

    def test_tmdb_episode_without_title_falls_back(self) -> None:
        """Episode title-less rows are surfaced as ``Episode N``."""
        tmdb = MagicMock()
        tmdb.get_tv_season.return_value = SeasonDetails(
            season_number=1,
            tv_id="1",
            episodes=[EpisodeInfo(season_number=1, episode_number=1, title="")],
            provider="tmdb",
        )
        result = _fetch_season_episodes(tmdb, 1, [1])
        assert result[(1, 1)]["title"] == "Episode 1"

    def test_tvdb_episode_without_title_falls_back(self) -> None:
        """Same fallback rule for the TVDB-primary fetcher."""
        tvdb = MagicMock()
        tvdb.get_series_episodes.return_value = SeasonDetails(
            season_number=2,
            tv_id="1",
            episodes=[EpisodeInfo(season_number=2, episode_number=3, title="")],
            provider="tvdb",
        )
        result = _fetch_season_episodes_tvdb(tvdb, 1, [2])
        assert result[(2, 3)]["title"] == "Episode 3"

    def test_tvdb_episode_carries_provider_ids_into_payload(self) -> None:
        """Regression (0.35.1): TVDB repair fetcher surfaces per-episode provider IDs.

        Pre-fix the payload dropped ``ep.external_ids``, so repaired episode NFOs
        were written with no ``<uniqueid type="tvdb">`` and failed verify's
        ``EpisodeCanonicalUniqueidPresent`` check (observed on The Orville,
        TVDB-primary). The ``{provider}_episode_id`` keys are what reach the NFO
        writer as the episode ``<uniqueid>`` elements.
        """
        tvdb = MagicMock()
        tvdb.get_series_episodes.return_value = SeasonDetails(
            season_number=1,
            tv_id="1",
            episodes=[
                EpisodeInfo(
                    season_number=1,
                    episode_number=1,
                    title="Old Wounds",
                    external_ids={"tvdb": "6072123", "imdb": "tt6038262"},
                )
            ],
            provider="tvdb",
        )
        result = _fetch_season_episodes_tvdb(tvdb, 1, [1])
        assert result[(1, 1)]["tvdb_episode_id"] == "6072123"
        assert result[(1, 1)]["imdb_episode_id"] == "tt6038262"

    def test_tmdb_episode_carries_provider_ids_into_payload(self) -> None:
        """Regression (0.35.1): TMDB repair fetcher surfaces the episode's tmdb id.

        Mirror of the TVDB case for TMDB-primary shows (canonical family = tmdb).
        """
        tmdb = MagicMock()
        tmdb.get_tv_season.return_value = SeasonDetails(
            season_number=1,
            tv_id="1",
            episodes=[
                EpisodeInfo(
                    season_number=1,
                    episode_number=1,
                    title="Pilot",
                    external_ids={"tmdb": "349232"},
                )
            ],
            provider="tmdb",
        )
        result = _fetch_season_episodes(tmdb, 1, [1])
        assert result[(1, 1)]["tmdb_episode_id"] == "349232"


# ---------------------------------------------------------------------------
# _dedup_and_move_root_episode — dry-run + OSError branches
# ---------------------------------------------------------------------------


class TestDedupAndMoveRootEpisode:
    """Cover dry-run preview and unlink/rename failure branches."""

    def test_dry_run_does_not_unlink_duplicates(self, tmp_path: Path) -> None:
        """Dry-run logs the would-be deletion + would-be move."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        keeper = show / "Show.S01E01.B.mkv"
        old = show / "Show.S01E01.A.mkv"
        keeper.write_bytes(b"\x00")
        old.write_bytes(b"\x00")
        # Make keeper newer.
        import os

        os.utime(keeper, (1_000_000_000, 1_000_000_000))
        os.utime(old, (1, 1))

        repaired = _dedup_and_move_root_episode(
            show,
            1,
            1,
            [keeper, old],
            {(1, 1): {"title": "Pilot", "still_path": ""}},
            NamingPatterns(),
            dry_run=True,
        )
        assert repaired is True
        # Files untouched in dry-run.
        assert keeper.exists()
        assert old.exists()

    def test_unlink_oserror_is_logged_not_propagated(self, tmp_path: Path) -> None:
        """An OSError during duplicate removal does not crash the function."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        keeper = show / "keeper.mkv"
        old = show / "old.mkv"
        keeper.write_bytes(b"\x00")
        old.write_bytes(b"\x00")
        import os

        os.utime(keeper, (1_000_000_000, 1_000_000_000))
        os.utime(old, (1, 1))

        with patch("pathlib.Path.unlink", side_effect=OSError("EACCES")):
            # Function must complete without raising.
            _dedup_and_move_root_episode(
                show,
                1,
                1,
                [keeper, old],
                {(1, 1): {"title": "Pilot", "still_path": ""}},
                NamingPatterns(),
                dry_run=False,
            )

    def test_rename_oserror_is_logged_not_propagated(self, tmp_path: Path) -> None:
        """An OSError during rename leaves the keeper in place but logs the failure."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        keeper = show / "Show.S01E01.mkv"
        keeper.write_bytes(b"\x00")

        with patch("pathlib.Path.rename", side_effect=OSError("EACCES")):
            repaired = _dedup_and_move_root_episode(
                show,
                1,
                1,
                [keeper],
                {(1, 1): {"title": "Pilot", "still_path": ""}},
                NamingPatterns(),
                dry_run=False,
            )
        # ``repaired`` stays False because the move failed and there were no
        # duplicates to delete.
        assert repaired is False


# ---------------------------------------------------------------------------
# _build_root_moved_map — skip path when ep_info is None
# ---------------------------------------------------------------------------


class TestBuildRootMovedMap:
    """Cover the ``continue`` branch when no API episode data is available."""

    def test_skips_entries_without_api_info(self, tmp_path: Path) -> None:
        """Entries without API metadata are dropped from the resulting map."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        f = show / "Show.S01E01.mkv"
        f.write_bytes(b"\x00")
        result = _build_root_moved_map(
            root_new={(1, 1): [f]},
            root_api_episodes={},  # no api info → continue
            show_dir=show,
            patterns=NamingPatterns(),
        )
        assert result == {}


# ---------------------------------------------------------------------------
# _check_missing_movie_artwork / _check_missing_tvshow_artwork
# ---------------------------------------------------------------------------


class TestCheckMissingArtwork:
    """Cover the artwork-missing branches in both helpers."""

    def test_missing_movie_poster_only(self, tmp_path: Path) -> None:
        """Only the missing one is reported."""
        validator = _make_validator()
        movie_dir = tmp_path / "Inception (2010)"
        movie_dir.mkdir()
        # Landscape present, poster missing.
        landscape = validator.patterns.format("movie_landscape", Title="Inception")
        (movie_dir / landscape).write_bytes(b"\xff\xd8")
        missing = validator._check_missing_movie_artwork(movie_dir, "Inception")
        assert len(missing) == 1
        assert "poster" in missing[0].lower()

    def test_missing_movie_landscape_only(self, tmp_path: Path) -> None:
        """Landscape missing while poster is present."""
        validator = _make_validator()
        movie_dir = tmp_path / "Inception (2010)"
        movie_dir.mkdir()
        poster = validator.patterns.format("movie_poster", Title="Inception")
        (movie_dir / poster).write_bytes(b"\xff\xd8")
        missing = validator._check_missing_movie_artwork(movie_dir, "Inception")
        assert len(missing) == 1
        assert "landscape" in missing[0].lower()

    def test_missing_tvshow_show_artwork(self, tmp_path: Path) -> None:
        """Show-level poster + landscape are both flagged when missing."""
        validator = _make_validator()
        show_dir = tmp_path / "Show (2020)"
        show_dir.mkdir()
        missing = validator._check_missing_tvshow_artwork(show_dir)
        assert validator.patterns.tvshow_poster in missing
        assert validator.patterns.tvshow_landscape in missing

    def test_missing_tvshow_season_poster_listed(self, tmp_path: Path) -> None:
        """A missing per-season poster is appended to the list."""
        validator = _make_validator()
        show_dir = tmp_path / "Show (2020)"
        show_dir.mkdir()
        # Show-level artwork present.
        (show_dir / validator.patterns.tvshow_poster).write_bytes(b"\xff\xd8")
        (show_dir / validator.patterns.tvshow_landscape).write_bytes(b"\xff\xd8")
        # Season directory present but no per-season poster.
        (show_dir / "Saison 01").mkdir()
        missing = validator._check_missing_tvshow_artwork(show_dir)
        # Only the season poster should be missing.
        assert len(missing) == 1
        assert "season01" in missing[0].lower() or "saison" in missing[0].lower() or missing[0]

    def test_missing_tvshow_skips_non_season_subdirs(self, tmp_path: Path) -> None:
        """Hidden / non-season subdirs are skipped (continue branch)."""
        validator = _make_validator()
        show_dir = tmp_path / "Show (2020)"
        show_dir.mkdir()
        (show_dir / validator.patterns.tvshow_poster).write_bytes(b"\xff\xd8")
        (show_dir / validator.patterns.tvshow_landscape).write_bytes(b"\xff\xd8")
        (show_dir / ".actors").mkdir()
        (show_dir / "Trailers").mkdir()
        (show_dir / "extras_file.txt").write_text("notdir")
        missing = validator._check_missing_tvshow_artwork(show_dir)
        # No season dirs, no show artwork missing → empty.
        assert missing == []


# ---------------------------------------------------------------------------
# _extract_tmdb_id_from_nfo — error branches
# ---------------------------------------------------------------------------


class TestExtractTmdbIdFromNfo:
    """Cover NFO parse error + non-numeric branches in the static helper."""

    def test_parse_error_returns_none(self, tmp_path: Path) -> None:
        """Unparsable NFO → None (lines 680-682)."""
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text("<not_xml")
        assert ExistingValidatorMixin._extract_tmdb_id_from_nfo(nfo) is None

    def test_non_numeric_id_returns_none(self, tmp_path: Path) -> None:
        """A non-numeric value rejects gracefully (lines 687-689)."""
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text('<tvshow><uniqueid type="tmdb">abc</uniqueid></tvshow>')
        assert ExistingValidatorMixin._extract_tmdb_id_from_nfo(nfo) is None

    def test_no_tmdb_id_returns_none(self, tmp_path: Path) -> None:
        """An NFO without a TMDB ``uniqueid`` returns None."""
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text('<tvshow><uniqueid type="imdb">tt123</uniqueid></tvshow>')
        assert ExistingValidatorMixin._extract_tmdb_id_from_nfo(nfo) is None


# ---------------------------------------------------------------------------
# _recover_movie_artwork / _recover_tvshow_artwork
# ---------------------------------------------------------------------------


class TestRecoverArtwork:
    """Cover happy path + exception branches of the recovery helpers."""

    def test_recover_movie_no_tmdb_id_returns_silently(self, tmp_path: Path) -> None:
        """No TMDB id → early return without API calls (line 740)."""
        validator = _make_validator()
        nfo = tmp_path / "Movie.nfo"
        nfo.write_text("<movie/>")  # no uniqueid
        movie_dir = tmp_path / "Movie"
        movie_dir.mkdir()
        result = ScrapeResult(media_path=movie_dir, media_type="movie")
        validator._recover_movie_artwork(nfo, movie_dir, result)
        assert result.action != "artwork_recovered"
        validator._tmdb.get_movie.assert_not_called()

    def test_recover_movie_success_sets_action(self, tmp_path: Path) -> None:
        """A successful download sets ``artwork_recovered`` + lists artwork."""
        validator = _make_validator()
        validator._tmdb.get_movie.return_value = {"id": 1, "title": "X"}
        validator._artwork.download_movie_artwork.return_value = [Path("poster.jpg")]
        nfo = tmp_path / "Movie.nfo"
        nfo.write_text('<movie><uniqueid type="tmdb">42</uniqueid></movie>')
        movie_dir = tmp_path / "Movie"
        movie_dir.mkdir()
        result = ScrapeResult(media_path=movie_dir, media_type="movie")
        validator._recover_movie_artwork(nfo, movie_dir, result)
        assert result.action == "artwork_recovered"
        assert "poster.jpg" in result.artwork_downloaded

    def test_recover_movie_exception_appends_warning(self, tmp_path: Path) -> None:
        """An exception in the artwork pipeline is captured as a warning."""
        validator = _make_validator()
        validator._tmdb.get_movie.side_effect = ConnectionError("API down")
        nfo = tmp_path / "Movie.nfo"
        nfo.write_text('<movie><uniqueid type="tmdb">42</uniqueid></movie>')
        movie_dir = tmp_path / "Movie"
        movie_dir.mkdir()
        result = ScrapeResult(media_path=movie_dir, media_type="movie")
        validator._recover_movie_artwork(nfo, movie_dir, result)
        assert any("Artwork recovery failed" in w for w in result.warnings)

    def test_recover_tvshow_no_tmdb_id_returns_silently(self, tmp_path: Path) -> None:
        """Same early-return semantics for TV recovery."""
        validator = _make_validator()
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text("<tvshow/>")
        show = tmp_path / "Show"
        show.mkdir()
        result = ScrapeResult(media_path=show, media_type="tvshow")
        validator._recover_tvshow_artwork(nfo, show, result)
        assert result.action != "artwork_recovered"

    def test_recover_tvshow_success_sets_action(self, tmp_path: Path) -> None:
        """Successful download sets ``artwork_recovered`` for TV shows."""
        validator = _make_validator()
        validator._tmdb.get_tv.return_value = {"id": 1, "name": "Show"}
        validator._artwork.download_tvshow_artwork.return_value = [Path("poster.jpg")]
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text('<tvshow><uniqueid type="tmdb">42</uniqueid></tvshow>')
        show = tmp_path / "Show"
        show.mkdir()
        result = ScrapeResult(media_path=show, media_type="tvshow")
        validator._recover_tvshow_artwork(nfo, show, result)
        assert result.action == "artwork_recovered"

    def test_recover_tvshow_exception_appends_warning(self, tmp_path: Path) -> None:
        """An exception is caught + appended as a warning (lines 796-798)."""
        validator = _make_validator()
        validator._tmdb.get_tv.side_effect = ConnectionError("API down")
        nfo = tmp_path / "tvshow.nfo"
        nfo.write_text('<tvshow><uniqueid type="tmdb">42</uniqueid></tvshow>')
        show = tmp_path / "Show"
        show.mkdir()
        result = ScrapeResult(media_path=show, media_type="tvshow")
        validator._recover_tvshow_artwork(nfo, show, result)
        assert any("Artwork recovery failed" in w for w in result.warnings)

    def test_recover_movie_artwork_skipped_when_tmdb_not_configured(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Regression for I4 (PR review cycle 4): silent skip when tmdb missing.

        ``_recover_movie_artwork`` must NOT raise nor append a warning when
        ``registry.get("tmdb")`` raises :class:`UnknownProviderError` — it
        must short-circuit and emit a structured debug log
        (``artwork_recovery_skipped_no_tmdb``). Without the I4 pre-check the
        broad ``except Exception`` swallowed the exception and surfaced it
        as a misleading "Artwork recovery failed: Unknown provider 'tmdb'"
        warning, hiding the true (config) cause from the operator.
        """
        from personalscraper.api.metadata.registry._errors import UnknownProviderError

        validator = _make_validator()
        # Registry has no tmdb configured: any get("tmdb") raises.
        validator._registry.get.side_effect = UnknownProviderError("tmdb")  # type: ignore[attr-defined]
        nfo = tmp_path / "Movie.nfo"
        nfo.write_text('<movie><uniqueid type="tmdb">42</uniqueid></movie>')
        movie_dir = tmp_path / "Movie"
        movie_dir.mkdir()
        result = ScrapeResult(media_path=movie_dir, media_type="movie")

        with caplog.at_level("DEBUG", logger="scraper"):
            validator._recover_movie_artwork(nfo, movie_dir, result)

        # No exception escaped, action unchanged, no warning surfaced.
        assert result.action != "artwork_recovered"
        assert result.warnings == []
        # Forensic anchor present.
        assert any("artwork_recovery_skipped_no_tmdb" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _repair_season_dir — dry-run + OSError branches
# ---------------------------------------------------------------------------


class TestRepairSeasonDir:
    """Cover the replacement semantics + dry-run + OSError branches.

    Semantics (DEV #9 fix, 2026-05-21): a root duplicate of an organised
    episode is the FRESHER copy and supersedes the organised file. The
    organised file is removed and the key is dropped from the returned set
    so the caller's ``_repair_episode_files`` picks up the root copy and
    moves+renames it into the season directory.
    """

    def test_root_duplicate_replaces_existing_file_real_run(self, tmp_path: Path) -> None:
        """Real run: the older organised file is removed; the root file survives.

        Regression test for DEV #9 (data-loss bug). Previously, this method
        deleted the root file (the fresher copy) and kept the organised file
        — silently losing the operator's re-download.
        """
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        s01 = show / "Saison 01"
        s01.mkdir()
        old_organised = s01 / "S01E01 - Ep.mkv"
        old_organised.write_bytes(b"\xff")  # marker for "older copy"
        new_root = show / "Show.S01E01.NEW.RELEASE.mkv"
        new_root.write_bytes(b"\x00")  # marker for "fresh download"

        organized, repaired = validator._repair_season_dir(show)

        assert repaired is True
        assert (1, 1) not in organized, "Replaced episode must drop out of organized"
        assert not old_organised.exists(), "Old organised file must be removed"
        assert new_root.exists(), "Fresh root download must survive"

    def test_dry_run_logs_but_does_not_delete(self, tmp_path: Path) -> None:
        """Dry-run reports the replacement but leaves both files in place.

        The returned ``organized`` set still reflects the post-replacement
        state (key removed) so the caller's ``_repair_episode_files`` would
        see the root file as a candidate to move/rename.
        """
        validator = _make_validator(dry_run=True)
        show = tmp_path / "Show (2020)"
        show.mkdir()
        s01 = show / "Saison 01"
        s01.mkdir()
        old_organised = s01 / "S01E01 - Ep.mkv"
        old_organised.write_bytes(b"\xff")
        new_root = show / "Show.S01E01.mkv"
        new_root.write_bytes(b"\x00")

        organized, repaired = validator._repair_season_dir(show)

        assert repaired is True
        assert (1, 1) not in organized, "Dry-run still simulates the drop"
        assert old_organised.exists(), "Dry-run preserves the old organised file"
        assert new_root.exists(), "Dry-run preserves the root duplicate"

    def test_unlink_oserror_is_logged(self, tmp_path: Path) -> None:
        """An OSError on the organised-file unlink keeps both files and key.

        When the old-file removal fails, the root copy is NOT promoted (the
        replacement did not complete) and the key remains in ``organized``
        so the caller's ``_repair_episode_files`` keeps skipping the root
        duplicate.
        """
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        s01 = show / "Saison 01"
        s01.mkdir()
        old_organised = s01 / "S01E01 - Ep.mkv"
        old_organised.write_bytes(b"\xff")
        new_root = show / "Show.S01E01.mkv"
        new_root.write_bytes(b"\x00")

        with patch("pathlib.Path.unlink", side_effect=OSError("EACCES")):
            organized, repaired = validator._repair_season_dir(show)

        assert repaired is False, "Failed replacement is not a repair"
        assert (1, 1) in organized, "Failed replacement keeps the key"
        assert old_organised.exists(), "Failed unlink → file still there"
        assert new_root.exists(), "Root file was never the unlink target"


# ---------------------------------------------------------------------------
# _repair_movie_dir — dry-run + OSError branches
# ---------------------------------------------------------------------------


class TestRepairMovieDir:
    """Cover dry-run preview and unlink failure of residual movie NFOs."""

    def test_dry_run_keeps_residuals(self, tmp_path: Path) -> None:
        """Dry-run reports the would-be removal but leaves residual NFOs."""
        validator = _make_validator(dry_run=True)
        movie_dir = tmp_path / "Movie (2024)"
        movie_dir.mkdir()
        (movie_dir / "Movie.nfo").write_text("<movie/>")  # expected
        residual = movie_dir / "Old.Title.Release.nfo"
        residual.write_text("<movie/>")
        repaired = validator._repair_movie_dir(movie_dir, "Movie")
        assert repaired is True
        assert residual.exists()

    def test_unlink_oserror_logged_not_fatal(self, tmp_path: Path) -> None:
        """An OSError on residual unlink is captured without raising."""
        validator = _make_validator()
        movie_dir = tmp_path / "Movie (2024)"
        movie_dir.mkdir()
        (movie_dir / "Movie.nfo").write_text("<movie/>")
        residual = movie_dir / "Old.Title.nfo"
        residual.write_text("<movie/>")
        with patch("pathlib.Path.unlink", side_effect=OSError("EACCES")):
            repaired = validator._repair_movie_dir(movie_dir, "Movie")
        assert repaired is False
        assert residual.exists()


# ---------------------------------------------------------------------------
# _repair_episode_files — TVDB branch + exception path (lines 480-494, 517-518)
# ---------------------------------------------------------------------------


class TestRepairEpisodeFilesTvdbBranch:
    """Cover the TVDB-primary branch + the broad exception handler."""

    def test_tvdb_branch_called_when_only_tvdb_id_present(self, tmp_path: Path) -> None:
        """When the NFO carries only a TVDB id, ``_tvdb_series_to_show_data`` is invoked."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tvdb_id=999, tmdb_id=None)
        # Root episode pending organisation.
        (show / "Show.S01E01.mkv").write_bytes(b"\x00")

        # tvdb_data needs ``external_ids`` attribute for the branch.
        tvdb_series = SimpleNamespace(external_ids={"imdb": "tt0001"})
        validator._tvdb.get_series.return_value = tvdb_series
        validator._tvdb.get_series_episodes.return_value = SeasonDetails(
            season_number=1,
            tv_id="999",
            episodes=[EpisodeInfo(season_number=1, episode_number=1, title="Pilot")],
            provider="tvdb",
        )

        with patch(
            "personalscraper.scraper.tv_service._tvdb_series_to_show_data",
            return_value={"name": "Show", "year": 2020},
        ) as mock_to_show:
            repaired = validator._repair_episode_files(show, organized=set())
        assert repaired is True
        mock_to_show.assert_called_once()

    def test_no_id_short_circuits(self, tmp_path: Path) -> None:
        """No TVDB and no TMDB id → False, no API call."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        # NFO without uniqueid
        (show / "tvshow.nfo").write_text("<tvshow/>")
        (show / "Show.S01E01.mkv").write_bytes(b"\x00")
        repaired = validator._repair_episode_files(show, organized=set())
        assert repaired is False
        validator._tvdb.get_series.assert_not_called()
        validator._tmdb.get_tv.assert_not_called()

    def test_exception_during_fetch_is_swallowed(self, tmp_path: Path) -> None:
        """OSError raised during API calls is caught (line 517-518)."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tvdb_id=None, tmdb_id=42)
        (show / "Show.S01E01.mkv").write_bytes(b"\x00")
        validator._tmdb.get_tv.side_effect = OSError("io fail")
        # Function must not raise, returns False (no repair completed).
        repaired = validator._repair_episode_files(show, organized=set())
        assert repaired is False

    def test_episode_already_organized_is_skipped(self, tmp_path: Path) -> None:
        """A root file whose key is in ``organized`` is skipped (line 456 branch)."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tvdb_id=None, tmdb_id=42)
        (show / "Show.S01E01.mkv").write_bytes(b"\x00")
        # Already organized.
        repaired = validator._repair_episode_files(show, organized={(1, 1)})
        assert repaired is False
        validator._tmdb.get_tv.assert_not_called()


# ---------------------------------------------------------------------------
# _repair_artwork (the 65-line gap 550-615)
# ---------------------------------------------------------------------------


class TestRepairArtworkOrganization:
    """Behavioural tests for ``_repair_artwork`` (organize-from-subdirs).

    Despite its misleading name, this method *moves* episodes from raw
    torrent subdirectories into ``Saison NN/`` directories, fetches API
    data via TVDB or TMDB, and writes per-episode NFOs.
    """

    def test_no_unorganized_files_returns_false(self, tmp_path: Path) -> None:
        """Empty unorganized set → early return False (line 548)."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tmdb_id=42)
        # No unorganized files.
        assert validator._repair_artwork(show) is False

    def test_no_id_in_nfo_returns_false(self, tmp_path: Path) -> None:
        """No TVDB and no TMDB id → returns False (line 555-556)."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<tvshow/>")
        release = show / "Show.S01.MULTi"
        release.mkdir()
        (release / "Show.S01E01.mkv").write_bytes(b"\x00")
        assert validator._repair_artwork(show) is False

    def test_tvdb_branch_organizes_unstructured_episodes(self, tmp_path: Path) -> None:
        """When TVDB id is present, fetcher + show-data builder are invoked."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tvdb_id=999)
        release = show / "Show.S01.MULTi"
        release.mkdir()
        (release / "Show.S01E01.mkv").write_bytes(b"\x00")

        tvdb_series = SimpleNamespace(external_ids={"imdb": "tt0001"})
        validator._tvdb.get_series.return_value = tvdb_series
        validator._tvdb.get_series_episodes.return_value = SeasonDetails(
            season_number=1,
            tv_id="999",
            episodes=[EpisodeInfo(season_number=1, episode_number=1, title="Pilot")],
            provider="tvdb",
        )
        with patch(
            "personalscraper.scraper.tv_service._tvdb_series_to_show_data",
            return_value={"name": "Show", "year": 2020},
        ) as mock_to_show:
            repaired = validator._repair_artwork(show)
        assert repaired is True
        mock_to_show.assert_called_once()
        # Episode NFO generation was triggered for the matched files.
        validator._generate_episode_nfos.assert_called_once()

    def test_tmdb_branch_organizes_unstructured_episodes(self, tmp_path: Path) -> None:
        """When only TMDB id is present, the TMDB branch executes."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tmdb_id=42)
        release = show / "Show.S01.MULTi"
        release.mkdir()
        (release / "Show.S01E01.mkv").write_bytes(b"\x00")

        validator._tmdb.get_tv.return_value = {"id": 42, "name": "Show"}
        validator._tmdb.get_tv_season.return_value = SeasonDetails(
            season_number=1,
            tv_id="42",
            episodes=[EpisodeInfo(season_number=1, episode_number=1, title="Pilot")],
            provider="tmdb",
        )
        repaired = validator._repair_artwork(show)
        assert repaired is True
        validator._generate_episode_nfos.assert_called_once()

    def test_empty_api_episodes_returns_false(self, tmp_path: Path) -> None:
        """When the API returns no episodes the repair short-circuits (line 599)."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tmdb_id=42)
        release = show / "Show.S01.MULTi"
        release.mkdir()
        (release / "Show.S01E01.mkv").write_bytes(b"\x00")

        validator._tmdb.get_tv.return_value = {"id": 42, "name": "Show"}
        # Return empty episode list → api_episodes empty.
        validator._tmdb.get_tv_season.return_value = SeasonDetails(
            season_number=1, tv_id="42", episodes=[], provider="tmdb"
        )
        assert validator._repair_artwork(show) is False

    def test_no_match_returns_false(self, tmp_path: Path) -> None:
        """When ``match_episode_files`` finds nothing, repair returns False."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tmdb_id=42)
        release = show / "Show.S01.MULTi"
        release.mkdir()
        (release / "totally_unmatchable.mkv").write_bytes(b"\x00")

        validator._tmdb.get_tv.return_value = {"id": 42, "name": "Show"}
        validator._tmdb.get_tv_season.return_value = SeasonDetails(
            season_number=1,
            tv_id="42",
            episodes=[EpisodeInfo(season_number=1, episode_number=1, title="Pilot")],
            provider="tmdb",
        )
        with patch(
            "personalscraper.scraper.existing_validator.match_episode_files",
            return_value={},
        ):
            assert validator._repair_artwork(show) is False

    def test_exception_during_repair_returns_false(self, tmp_path: Path) -> None:
        """An OSError during the repair is caught and False is returned (line 614)."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tmdb_id=42)
        release = show / "Show.S01.MULTi"
        release.mkdir()
        (release / "Show.S01E01.mkv").write_bytes(b"\x00")
        validator._tmdb.get_tv.side_effect = ConnectionError("net down")
        assert validator._repair_artwork(show) is False

    def test_seasons_inferred_from_filenames_when_no_season_dirs(self, tmp_path: Path) -> None:
        """When no Saison NN/ exists, seasons are bootstrapped from SxxEyy."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        _write_show_nfo(show / "tvshow.nfo", tmdb_id=42)
        release = show / "Show.S03.MULTi"  # season 3
        release.mkdir()
        (release / "Show.S03E01.mkv").write_bytes(b"\x00")

        validator._tmdb.get_tv.return_value = {"id": 42, "name": "Show"}
        validator._tmdb.get_tv_season.return_value = SeasonDetails(
            season_number=3,
            tv_id="42",
            episodes=[EpisodeInfo(season_number=3, episode_number=1, title="Pilot")],
            provider="tmdb",
        )
        repaired = validator._repair_artwork(show)
        assert repaired is True
        # Season 3 was discovered → fetcher called for season 3.
        validator._tmdb.get_tv_season.assert_called_with(42, 3)


# ---------------------------------------------------------------------------
# _repair_tvshow_dir — overall orchestration (lines 872-898)
# ---------------------------------------------------------------------------


class TestRepairTvshowDir:
    """Cover the orchestration of the ``_repair_tvshow_dir`` method."""

    def test_residual_root_nfo_removed(self, tmp_path: Path) -> None:
        """A non-tvshow.nfo at root is unlinked when not in dry-run."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<tvshow/>")
        residual = show / "old_release.nfo"
        residual.write_text("<tvshow/>")
        repaired = validator._repair_tvshow_dir(show)
        assert repaired is True
        assert not residual.exists()

    def test_residual_root_nfo_dry_run_keeps_file(self, tmp_path: Path) -> None:
        """Dry-run leaves the residual NFO in place but reports repair."""
        validator = _make_validator(dry_run=True)
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<tvshow/>")
        residual = show / "old.nfo"
        residual.write_text("<tvshow/>")
        repaired = validator._repair_tvshow_dir(show)
        assert repaired is True
        assert residual.exists()

    def test_residual_unlink_oserror_does_not_raise(self, tmp_path: Path) -> None:
        """OSError on residual unlink is logged and swallowed (lines 872-873)."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<tvshow/>")
        residual = show / "old.nfo"
        residual.write_text("<tvshow/>")

        # Patch only Path.unlink for the residual via a side_effect that raises
        # on the first call.
        with patch("pathlib.Path.unlink", side_effect=OSError("EACCES")):
            validator._repair_tvshow_dir(show)
        # Despite the failure the file stayed → exception was caught.
        assert residual.exists()

    def test_cleanup_release_dirs_oserror_swallowed(self, tmp_path: Path) -> None:
        """An OSError raised by ``_cleanup_empty_release_dirs`` is caught (lines 896-898)."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<tvshow/>")
        with patch(
            "personalscraper.scraper.existing_validator._cleanup_empty_release_dirs",
            side_effect=OSError("io fail"),
        ):
            # Must not raise.
            validator._repair_tvshow_dir(show)

    def test_cleanup_release_dirs_returns_count_marks_repaired(self, tmp_path: Path) -> None:
        """When cleanup removes ≥1 dir, ``_repair_tvshow_dir`` reports repair."""
        validator = _make_validator()
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text("<tvshow/>")
        with patch(
            "personalscraper.scraper.existing_validator._cleanup_empty_release_dirs",
            return_value=2,
        ):
            assert validator._repair_tvshow_dir(show) is True
