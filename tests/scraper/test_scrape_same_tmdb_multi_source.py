"""Regression test for the same-TMDB multi-source dedup bug (the "Gourou" scenario).

Reproduces the production deviation surfaced by ``/pipeline-monitor`` on
2026-05-28: two *distinct* staged movie folders that both resolve to the **same**
TMDB id. The scraper renames the source folder to the canonical name; because the
canonical folder already exists, :func:`_merge_dirs` folds both folders into one,
leaving multiple video files at the movie root. Before phase 30 the orphan
``.mkv`` stayed behind and DISPATCH copied duplicate videos to storage.

Operator spec (verbatim, 2026-05-28 17h50 run): « la dernière version (le dernier
téléchargé) doit être celui qui reste à la fin » — the canonical video must be the
most-recently-modified source, and no orphan must remain.

With sub-phases 30.1 (``_find_video_file`` prefers mtime-latest), 30.2 (post-rename
orphan unlink) and 30.3 (VERIFY ``no_duplicate_videos`` safety net) in place, the
two sources must converge to a single video equal to the newest source's content.

This test is intentionally placed under ``tests/scraper/`` (NOT ``tests/e2e/``) so
it runs in the default ``make test`` suite and in CI: ``pyproject.toml`` ``addopts``
excludes ``e2e``-marked tests, so an ``@pytest.mark.e2e`` regression test would
never actually guard against the bug regressing. The scrape is fully mocked
(no real disks, no live APIs), so it is fast and deterministic.

The harness mirrors :file:`tests/scraper/test_movie_service_extra.py`: the autouse
``_patch_transport`` fixture keeps the ``Scraper`` init offline, the ``scraper``
fixture is built with the shared ``mock_registry`` fixture, and the TMDB
``get_movie`` call is patched on ``scraper._registry.get("tmdb")``.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import structlog
from structlog.testing import capture_logs

from personalscraper.conf.models.config import Config
from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.confidence import MatchResult
from personalscraper.scraper.scraper import Scraper
from personalscraper.verify.checker import MediaChecker

# The fixed TMDB id both staged folders resolve to (the crux of the bug).
GOUROU_TMDB_ID = 123456

# Distinct byte contents so the surviving file proves WHICH source won. Size is
# not the selection driver — mtime is — so the contents only differ to identify
# the winner, not to bias selection.
OLD_CONTENT = b"OLD-2025-content" * 4096
NEW_CONTENT = b"NEW-2026-content" * 4096


# ---------------------------------------------------------------------------
# Fixtures — modelled on tests/scraper/test_movie_service_extra.py
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
def scraper(settings: MagicMock, mock_registry: MagicMock, test_config: Config) -> Scraper:
    """Return a Scraper with mocked TMDB client and a synthetic Config.

    The synthetic ``test_config`` lets ``_classify_item`` resolve a category
    without touching real disks; the scrape therefore proceeds past the merge +
    orphan-cleanup region the test asserts on.
    """
    with patch("personalscraper.api.metadata.tmdb.TMDBClient"):
        return Scraper(
            settings,
            NamingPatterns(),
            config=test_config,
            event_bus=EventBus(),
            registry=mock_registry,
        )


@pytest.fixture
def gourou_movie_data() -> dict:
    """TMDB-shaped movie data for "Gourou" (2026), id 123456.

    Mirrors the ``movie_data`` fixture in test_movie_service_extra.py but for the
    Gourou item: the ``release_date`` of 2026 makes the resolved clean folder name
    ``Gourou (2026)`` — the canonical target both staged folders converge on.
    """
    return {
        "id": GOUROU_TMDB_ID,
        "title": "Gourou",
        "original_title": "Gourou",
        "name": "Gourou",
        "original_name": "Gourou",
        "overview": "...",
        "vote_average": 7.0,
        "vote_count": 0,
        "genres": [],
        "release_date": "2026-01-01",
        "credits": {"cast": [], "crew": []},
        "images": {"posters": [], "backdrops": [], "logos": []},
        "external_ids": {},
        "release_dates": {"results": []},
        "production_countries": [],
        "production_companies": [],
        "origin_country": [],
    }


def _gourou_match() -> MatchResult:
    """Return the single high-confidence match BOTH folders resolve to.

    api_year is 2026 so the canonical clean folder name is ``Gourou (2026)``;
    scraping the 2025 folder therefore triggers the merge-into-existing branch.
    """
    return MatchResult(
        api_id=GOUROU_TMDB_ID,
        api_title="Gourou",
        api_year=2026,
        confidence=0.95,
        source="tmdb",
    )


def _build_two_sources(staging: Path) -> tuple[Path, Path, Path, Path]:
    """Create the two distinct staged Gourou folders that collide on TMDB.

    ``Gourou (2025)/A.mkv`` is given an OLDER mtime and distinct content; the
    canonical ``Gourou (2026)/B.mkv`` is given a strictly NEWER mtime and distinct
    content. mtimes are set explicitly with ``os.utime`` so B is unambiguously the
    last-downloaded source regardless of byte size.

    Args:
        staging: Temporary staging directory to populate.

    Returns:
        Tuple of (older_dir, older_video, newer_dir, newer_video).
    """
    older_dir = staging / "Gourou (2025)"
    older_dir.mkdir(parents=True)
    older_video = older_dir / "A.mkv"
    older_video.write_bytes(OLD_CONTENT)

    newer_dir = staging / "Gourou (2026)"
    newer_dir.mkdir(parents=True)
    newer_video = newer_dir / "B.mkv"
    newer_video.write_bytes(NEW_CONTENT)

    # mtime drives canonical selection (30.1): make B strictly newer than A so the
    # 2026 source wins, matching the operator spec "last downloaded survives".
    os.utime(older_video, (1_000_000, 1_000_000))
    os.utime(newer_video, (2_000_000, 2_000_000))
    return older_dir, older_video, newer_dir, newer_video


# ---------------------------------------------------------------------------
# Regression: same-TMDB multi-source dedup (the Gourou scenario)
# ---------------------------------------------------------------------------


class TestScrapeSameTmdbMultiSource:
    """Two distinct staged folders → same TMDB id → single canonical video."""

    def test_merge_dedup_keeps_newest_and_removes_orphan(
        self,
        scraper: Scraper,
        tmp_path: Path,
        gourou_movie_data: dict,
        test_config: Config,
    ) -> None:
        """Scraping the older folder merges into the newer one and dedups.

        Flow under test (movie_service.py ~936-1021):
          1. ``Gourou (2025)`` resolves to clean name ``Gourou (2026)`` which
             ALREADY exists → ``_merge_dirs`` folds A.mkv into ``Gourou (2026)``
             alongside B.mkv (event ``movie_folder_merged``).
          2. ``_find_video_file`` (30.1) picks the newest = B.mkv as canonical and
             renames it to ``Gourou.mkv`` (event ``movie_video_renamed``).
          3. The orphan-cleanup loop (30.2) unlinks A.mkv
             (event ``movie_video_orphan_removed``).

        The orphan cleanup runs BEFORE classify/NFO, so the filesystem + log
        assertions hold even if the later artwork/NFO steps are no-ops under mocks.
        """
        staging = tmp_path / "staging"
        older_dir, _older_video, newer_dir, _newer_video = _build_two_sources(staging)

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=_gourou_match()),
            patch.object(scraper._registry.get("tmdb"), "get_movie", return_value=gourou_movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
            capture_logs() as cap_logs,
        ):
            # Scrape the OLDER folder — its clean name is "Gourou (2026)" which
            # already exists, forcing the merge-into-existing dedup path.
            scraper.scrape_movie(older_dir)

        # --- Filesystem assertions (authoritative) ---------------------------
        # (1) The older source folder is merged away.
        assert not older_dir.exists(), "Gourou (2025)/ must be merged away"

        # (2) The canonical folder holds EXACTLY ONE video at its root.
        root_videos = sorted(p for p in newer_dir.iterdir() if p.is_file() and p.suffix == ".mkv")
        assert len(root_videos) == 1, f"expected exactly one root video, found {[p.name for p in root_videos]}"

        # (3) The surviving video's bytes equal B.mkv (the NEWEST source won).
        survivor = root_videos[0]
        assert survivor.read_bytes() == NEW_CONTENT, "the newest source (B.mkv / 2026) must be the survivor"

        # (4) No orphan .mkv lingers (the bug would have left A.mkv behind).
        assert all(p.read_bytes() != OLD_CONTENT for p in root_videos), "the orphan A.mkv must be removed"

        # --- Log-capture assertions ------------------------------------------
        events = {entry.get("event") for entry in cap_logs}
        assert "movie_folder_merged" in events, f"missing movie_folder_merged in {sorted(events)}"
        assert "movie_video_renamed" in events, f"missing movie_video_renamed in {sorted(events)}"
        assert "movie_video_orphan_removed" in events, f"missing movie_video_orphan_removed in {sorted(events)}"
        assert "movie_video_orphan_remove_failed" not in events, "orphan removal must not fail"

        # --- VERIFY safety net (30.3) ----------------------------------------
        # The no_duplicate_videos check must now PASS on the canonical folder:
        # only one root-level video remains after the dedup.
        checker = MediaChecker(NamingPatterns(), test_config)
        results = checker.check_movie(newer_dir)
        dup_check = next(r for r in results if r.name == "no_duplicate_videos")
        assert dup_check.passed is True, f"no_duplicate_videos must pass, got message={dup_check.message!r}"

    def test_capture_logs_records_event_dicts(self) -> None:
        """Document the capture_logs contract this regression relies on.

        ``capture_logs`` records each emitted log as a dict with an ``event`` key;
        the assertions above key off ``entry["event"]``. This guard pins that
        contract so a structlog upgrade that changes the capture shape fails here
        with a clear message rather than silently weakening the regression.
        """
        log = structlog.get_logger("scraper")
        with capture_logs() as cap_logs:
            log.info("movie_video_orphan_removed", filename="A.mkv", parent="Gourou (2026)")
        assert any(entry.get("event") == "movie_video_orphan_removed" for entry in cap_logs)
