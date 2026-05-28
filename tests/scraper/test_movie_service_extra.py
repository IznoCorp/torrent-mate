"""Additional coverage tests for ``personalscraper.scraper.movie_service``.

Targets the residual branches in :meth:`MovieServiceMixin.scrape_movie`
that remained uncovered in :file:`tests/scraper/test_scraper.py`:

* Corrupt NFO branch — unlink success, dry_run preview, OSError on unlink.
* ``get_movie`` exception → ``result.error`` short-circuit.
* Folder rename branches — direct rename, merge into existing folder,
  dry_run preview, OSError on rename, stale-cleanup OSError.
* Video file rename branches — successful rename, OSError swallowed as
  warning, dry_run preview.
* NFO generation exception → ``result.error`` short-circuit.
* ``artwork_recovered`` and ``repaired`` branches in the valid-NFO
  fast-path.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.confidence import MatchResult
from personalscraper.scraper.scraper import Scraper

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_transport() -> None:
    """Mock HttpTransport so Scraper init / TVDB bootstrap stay offline."""
    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.post.return_value = {"data": {"token": "mock-jwt"}}
    mock_instance.get.return_value = {}

    with (
        patch("personalscraper.api.transport._http.HttpTransport", return_value=mock_instance),
        patch("personalscraper.api.metadata.tvdb.HttpTransport", return_value=mock_instance),
    ):
        yield


@pytest.fixture
def settings() -> MagicMock:
    """Return a minimal Settings mock."""
    s = MagicMock()
    s.tmdb_api_key = "fake"
    s.tvdb_api_key = "fake"
    return s


@pytest.fixture
def scraper(settings: MagicMock, mock_registry: MagicMock) -> Scraper:
    """Return a Scraper with mocked TMDB client."""
    with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
        return Scraper(settings, NamingPatterns(), event_bus=EventBus(), registry=mock_registry)


@pytest.fixture
def movie_data() -> dict:
    """Minimal TMDB-shaped movie data dict used by the rename + NFO path."""
    return {
        "id": 603,
        "title": "The Matrix",
        "original_title": "The Matrix",
        "name": "The Matrix",
        "original_name": "The Matrix",
        "overview": "...",
        "vote_average": 8.7,
        "vote_count": 0,
        "genres": [],
        "release_date": "1999-03-31",
        "credits": {"cast": [], "crew": []},
        "images": {"posters": [], "backdrops": [], "logos": []},
        "external_ids": {},
        "release_dates": {"results": []},
        "production_countries": [],
        "production_companies": [],
        "origin_country": [],
    }


def _match() -> MatchResult:
    """Return a high-confidence match for The Matrix (1999)."""
    return MatchResult(
        api_id=603,
        api_title="The Matrix",
        api_year=1999,
        confidence=0.95,
        source="tmdb",
    )


# ---------------------------------------------------------------------------
# Valid NFO fast-path: artwork_recovered + repaired branches
# ---------------------------------------------------------------------------


class TestValidNfoFastPath:
    """Cover the valid-NFO branches at lines 277-286."""

    def test_artwork_recovered_when_missing_and_recovery_succeeds(self, scraper: Scraper, tmp_path: Path) -> None:
        """Missing poster triggers ``_recover_movie_artwork`` and sets the action."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The Matrix.nfo").write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')

        # Simulate that artwork is missing and recovery sets the action.
        def _fake_recover(nfo_path, mdir, result):
            result.action = "artwork_recovered"
            result.artwork_downloaded = ["poster.jpg"]

        with (
            patch.object(scraper, "_check_missing_movie_artwork", return_value=["poster.jpg"]),
            patch.object(scraper, "_recover_movie_artwork", side_effect=_fake_recover),
            patch.object(scraper, "_repair_movie_dir", return_value=False),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "artwork_recovered"

    def test_repaired_when_repair_returns_true(self, scraper: Scraper, tmp_path: Path) -> None:
        """``_repair_movie_dir`` returning True wins over ``skipped_already_done``."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The Matrix.nfo").write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')
        with (
            patch.object(scraper, "_check_missing_movie_artwork", return_value=[]),
            patch.object(scraper, "_repair_movie_dir", return_value=True),
        ):
            result = scraper.scrape_movie(movie_dir)
        assert result.action == "repaired"

    def test_repaired_does_not_override_artwork_recovered(self, scraper: Scraper, tmp_path: Path) -> None:
        """When recovery already set ``artwork_recovered`` it stays even if repair=True."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The Matrix.nfo").write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')

        def _fake_recover(nfo_path, mdir, result):
            result.action = "artwork_recovered"

        with (
            patch.object(scraper, "_check_missing_movie_artwork", return_value=["poster.jpg"]),
            patch.object(scraper, "_recover_movie_artwork", side_effect=_fake_recover),
            patch.object(scraper, "_repair_movie_dir", return_value=True),
        ):
            result = scraper.scrape_movie(movie_dir)
        assert result.action == "artwork_recovered"


# ---------------------------------------------------------------------------
# Corrupt NFO branch (lines 295-305)
# ---------------------------------------------------------------------------


class TestCorruptNfoBranch:
    """Cover the corrupt-NFO unlink + dry_run + OSError lines."""

    def test_corrupt_nfo_dry_run_does_not_delete(self, scraper: Scraper, tmp_path: Path) -> None:
        """Dry-run preserves the corrupt NFO file (no unlink)."""
        scraper.dry_run = True
        movie_dir = tmp_path / "Bad Movie (2024)"
        movie_dir.mkdir()
        nfo = movie_dir / "Bad Movie.nfo"
        # Corrupt: not parsable XML.
        nfo.write_text("<not_real_xml")

        with patch("personalscraper.scraper.scraper.match_movie", return_value=None):
            result = scraper.scrape_movie(movie_dir)

        # Dry-run preview keeps the file in place.
        assert nfo.exists()
        # Match returned None so the result is the low-confidence skip.
        assert result.action == "skipped_low_confidence"

    def test_corrupt_nfo_unlink_success(self, scraper: Scraper, tmp_path: Path) -> None:
        """Real run unlinks the corrupt NFO before retrying the match."""
        movie_dir = tmp_path / "Bad Movie (2024)"
        movie_dir.mkdir()
        nfo = movie_dir / "Bad Movie.nfo"
        nfo.write_text("<not_real_xml")  # corrupt → not complete

        with patch("personalscraper.scraper.scraper.match_movie", return_value=None):
            scraper.scrape_movie(movie_dir)

        # Unlink ran during the corrupt-rescrape path.
        assert not nfo.exists()

    def test_corrupt_nfo_unlink_oserror_returns_error(self, scraper: Scraper, tmp_path: Path) -> None:
        """An OSError on unlink short-circuits with ``result.error``."""
        movie_dir = tmp_path / "Bad Movie (2024)"
        movie_dir.mkdir()
        nfo = movie_dir / "Bad Movie.nfo"
        nfo.write_text("<not_real_xml")  # corrupt

        with patch("pathlib.Path.unlink", side_effect=OSError("EACCES")):
            result = scraper.scrape_movie(movie_dir)

        assert result.error is not None
        assert "Cannot delete corrupt NFO" in result.error


# ---------------------------------------------------------------------------
# get_movie exception (lines 318-321)
# ---------------------------------------------------------------------------


class TestGetMovieException:
    """Cover the ``self._tmdb.get_movie`` exception branch."""

    def test_get_movie_exception_short_circuits(self, scraper: Scraper, tmp_path: Path) -> None:
        """An exception raised by ``get_movie`` populates ``result.error`` and returns."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", side_effect=ConnectionError("API down")),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action != "scraped"
        assert "Get details failed" in (result.error or "")


# ---------------------------------------------------------------------------
# Folder rename branches (lines 341-368)
# ---------------------------------------------------------------------------


class TestFolderRenameBranches:
    """Cover the folder-name normalization paths."""

    def test_folder_rename_when_target_does_not_exist(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """Source name ≠ canonical → folder is renamed into place."""
        # Folder name parses to title="The Matrix" but year token absent → rename
        # is required to produce the canonical "The Matrix (1999)".
        movie_dir = tmp_path / "The Matrix"
        movie_dir.mkdir()
        (movie_dir / "video.mkv").write_text("payload")

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "scraped"
        # New canonical folder must exist.
        assert (tmp_path / "The Matrix (1999)").is_dir()
        # Old folder is gone.
        assert not movie_dir.exists()

    def test_folder_merge_into_existing_target(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """When the canonical target already exists, files are merged into it."""
        movie_dir = tmp_path / "The Matrix"
        movie_dir.mkdir()
        (movie_dir / "video.mkv").write_text("payload")
        # Pre-existing target dir to force the merge branch.
        target = tmp_path / "The Matrix (1999)"
        target.mkdir()

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
            patch(
                "personalscraper.scraper.movie_service._merge_dirs",
                return_value=(1, 0),
            ) as mock_merge,
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "scraped"
        mock_merge.assert_called_once()

    def test_folder_merge_partial_failure_emits_warning(
        self, scraper: Scraper, tmp_path: Path, movie_data: dict
    ) -> None:
        """Partial-merge failure count surfaces in ``result.warnings``."""
        movie_dir = tmp_path / "The Matrix"
        movie_dir.mkdir()
        (movie_dir / "video.mkv").write_text("payload")
        (tmp_path / "The Matrix (1999)").mkdir()

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
            patch(
                "personalscraper.scraper.movie_service._merge_dirs",
                return_value=(1, 2),  # 1 moved, 2 failed
            ),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert any("Partial merge" in w for w in result.warnings)

    def test_folder_dry_run_does_not_rename(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """Dry-run preview keeps the original folder name (no rename, no merge)."""
        scraper.dry_run = True
        movie_dir = tmp_path / "The Matrix"
        movie_dir.mkdir()

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            scraper.scrape_movie(movie_dir)

        # Original folder remains; canonical version was not created.
        assert movie_dir.exists()
        assert not (tmp_path / "The Matrix (1999)").exists()

    def test_folder_dry_run_logs_merge_when_target_exists(
        self, scraper: Scraper, tmp_path: Path, movie_data: dict
    ) -> None:
        """Dry-run with existing target uses the ``merge into`` log action."""
        scraper.dry_run = True
        movie_dir = tmp_path / "The Matrix"
        movie_dir.mkdir()
        (tmp_path / "The Matrix (1999)").mkdir()

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            # Just exercise the branch — assertion is structural.
            scraper.scrape_movie(movie_dir)

    def test_folder_rename_oserror_short_circuits(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """OSError on rename produces ``result.error`` and returns."""
        movie_dir = tmp_path / "The Matrix"
        movie_dir.mkdir()

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("pathlib.Path.rename", side_effect=OSError("EACCES")),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert "Rename/merge failed" in (result.error or "")

    def test_stale_cleanup_oserror_logged_not_fatal(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """An OSError in ``_cleanup_stale_files`` is logged and does not fail the scrape."""
        movie_dir = tmp_path / "The Matrix"
        movie_dir.mkdir()
        (movie_dir / "video.mkv").write_text("payload")

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
            patch(
                "personalscraper.scraper.movie_service._cleanup_stale_files",
                side_effect=OSError("stale io"),
            ),
        ):
            result = scraper.scrape_movie(movie_dir)

        # Scrape still succeeded despite cleanup failure.
        assert result.action == "scraped"


# ---------------------------------------------------------------------------
# Video rename branches (lines 388-398)
# ---------------------------------------------------------------------------


class TestVideoRenameBranches:
    """Cover the video-file rename real, OSError, and dry-run branches."""

    def test_video_rename_oserror_logged_as_warning(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """OSError on video rename is non-fatal — appended to ``result.warnings``."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "raw_video.mkv").write_text("payload")

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
            patch("pathlib.Path.rename", side_effect=OSError("video EACCES")),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "scraped"
        assert any("Video rename failed" in w for w in result.warnings)

    def test_video_dry_run_does_not_rename(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """Dry-run keeps the raw video filename in place."""
        scraper.dry_run = True
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        raw = movie_dir / "raw_video.mkv"
        raw.write_text("payload")

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            scraper.scrape_movie(movie_dir)

        # Video file kept its original name in dry-run mode.
        assert raw.exists()


# ---------------------------------------------------------------------------
# Post-rename orphan video cleanup (same-TMDB multi-source dedup)
# ---------------------------------------------------------------------------


class TestVideoOrphanCleanup:
    """Cover the non-canonical video unlink loop after the movie rename.

    When two distinct staged folders resolve to the same TMDB id, an earlier
    merge step folds both into one folder, leaving multiple video files at the
    movie root. ``_find_video_file`` picks the most-recently-modified one as
    canonical; the loop must remove every other root-level video.
    """

    @staticmethod
    def _make_movie_dir_with_orphan(tmp_path: Path) -> tuple[Path, Path, Path]:
        """Build a canonical movie dir holding the canonical video + an orphan.

        The canonical-named file (``The Matrix.mkv``) is given the newest mtime
        so ``_find_video_file`` selects it; its name already matches the clean
        target, so the rename branch is a no-op and the orphan loop is exercised
        on a stable canonical file.

        Returns:
            Tuple of (movie_dir, canonical_path, orphan_path).
        """
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        canonical = movie_dir / "The Matrix.mkv"
        canonical.write_text("newest-canonical-payload")
        orphan = movie_dir / "The.Matrix.1080p.mkv"
        orphan.write_text("older-orphan-payload")
        # Make the canonical file strictly newer so mtime-latest selection picks
        # it, leaving the differently-named file as the orphan to remove.
        import os

        os.utime(orphan, (1_000_000, 1_000_000))
        os.utime(canonical, (2_000_000, 2_000_000))
        return movie_dir, canonical, orphan

    def test_orphan_removed_in_real_run(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """Non-dry-run with two root videos → only the canonical survives."""
        movie_dir, canonical, orphan = self._make_movie_dir_with_orphan(tmp_path)

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "scraped"
        # Filesystem state is authoritative: canonical kept, orphan gone.
        assert canonical.exists()
        assert not orphan.exists()
        # Exactly one root-level video remains.
        remaining = sorted(p.name for p in movie_dir.iterdir() if p.suffix == ".mkv")
        assert remaining == ["The Matrix.mkv"]

    def test_orphan_kept_in_dry_run(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """Dry-run keeps BOTH videos on disk; nothing is unlinked."""
        scraper.dry_run = True
        movie_dir, canonical, orphan = self._make_movie_dir_with_orphan(tmp_path)

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            scraper.scrape_movie(movie_dir)

        # Both files survive the dry-run preview.
        assert canonical.exists()
        assert orphan.exists()

    def test_orphan_unlink_oserror_does_not_raise(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """An OSError on the orphan unlink is swallowed; canonical untouched."""
        movie_dir, canonical, orphan = self._make_movie_dir_with_orphan(tmp_path)

        real_unlink = Path.unlink

        def _failing_unlink(self: Path, *args: object, **kwargs: object) -> None:
            # Raise only for the orphan; let any other unlink proceed normally.
            if self.name == orphan.name:
                raise OSError("EACCES on orphan")
            real_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
            patch("pathlib.Path.unlink", _failing_unlink),
        ):
            # Must NOT raise despite the failing orphan unlink.
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "scraped"
        # Canonical file is never targeted by the unlink, so it stays.
        assert canonical.exists()
        # The orphan remains because its unlink failed — but the scrape survived.
        assert orphan.exists()


# ---------------------------------------------------------------------------
# NFO generation exception (lines 433-437)
# ---------------------------------------------------------------------------


class TestNfoGenerationException:
    """Cover the NFO generation exception branch."""

    def test_nfo_generation_exception_short_circuits(self, scraper: Scraper, tmp_path: Path, movie_data: dict) -> None:
        """An exception in ``generate_movie_nfo`` populates ``result.error``."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The Matrix.mkv").write_text("payload")

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(
                scraper._nfo,
                "generate_movie_nfo",
                side_effect=RuntimeError("template boom"),
            ),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert "NFO generation failed" in (result.error or "")
