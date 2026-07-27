"""Characterization pins for ``TrailersOrchestrator.run`` outcome taxonomy.

These tests freeze the CURRENT (pre-refactor) behaviour of
:meth:`personalscraper.trailers.orchestrator.TrailersOrchestrator.run` so that
the P6 restructure of the trailers subsystem can be proven behaviour-preserving.
They assert nothing about what the taxonomy *should* be — only what it *is*.

Per-item processing produces a normalized outcome expressed through four
observable channels, all pinned here:

1. **Reported result** — the ``(status, reason)`` tuple appended to
   :attr:`TrailersOrchestrator.item_results` and the run-level ``counts`` dict
   key incremented, plus the ``failed_items`` kind.
2. **State mutation** — the ``TrailerState`` persisted to the JSON state store
   (its ``status``, ``attempts``, and whether a ``next_retry_at`` cooldown was
   written), or the absence of a write.
3. **Filesystem effect** — whether a trailer file lands at the Plex-conformant
   location (movies flat ``<name>-trailer.ext``; TV shows ``Trailers/<name>.ext``).
4. **Indexer + bus effect** — the best-effort outbox publish and the
   ``TrailerDownloaded`` event, both firing only on a successful download.

Volatile fields (ISO timestamps, tmp paths, durations) are normalized away:
timestamps collapse to a ``next_retry_set`` boolean and item/state paths are
stripped from the pinned tuples.

Taxonomy note (plan drift corrected in ``phase-00-safety-net.md``): the plan
named the outcomes ``found/placed/skipped/failed/cooldown/no-match``. The code's
actual ``item_results`` status vocabulary is the six values
``downloaded / already_present / no_trailer / bot_detected / error / skipped``,
refined by ten distinct ``reason`` codes plus an ``error``-with-no-``item_result``
asymmetry on finder failure. The actual taxonomy is pinned below.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api._contracts import CircuitOpenError, MediaType
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.event_bus import EventBus
from personalscraper.trailers.discovery.ytdlp_downloader import DownloadResult, DownloadStatus
from personalscraper.trailers.events import TrailerDownloaded
from personalscraper.trailers.orchestrator import TrailersOrchestrator, _LibraryEntry
from personalscraper.trailers.placement import trailer_path_for
from personalscraper.trailers.scanner import ScanItem
from personalscraper.trailers.state import TrailerState, make_state_key

# Sentinel distinguishing "finder should return None" from "finder not driven".
_UNSET: Any = object()

# Comfortably above ``min_file_size_bytes`` (100 KiB) so ``trailer_exists`` passes.
_TRAILER_BYTES = b"x" * 200_000

_MOVIE_URL = "https://youtube.com/watch?v=MOVIE"


def _make_config(
    tmp_path: Path,
    *,
    fallback: bool = False,
    library_movies: bool = False,
    library_tv: bool = False,
) -> MagicMock:
    """Build a minimal mock config for orchestrator characterization tests.

    Only the fields the orchestrator reads as concrete typed values are set;
    everything else is satisfied by ``MagicMock``'s numeric/iter dunders. The
    ``fallback`` and ``library_*`` toggles default off so the base outcome
    ladder is isolated from the same-run YouTube fallback and the library-aware
    SOT recheck (each pinned in its own dedicated test).

    Args:
        tmp_path: Pytest tmp_path fixture used for the state-file location.
        fallback: Value for ``trailers.fallback_youtube_search``.
        library_movies: Value for ``trailers.library_check.movies``.
        library_tv: Value for ``trailers.library_check.tv_shows``.

    Returns:
        A ``MagicMock`` configured with every field the orchestrator reads.
    """
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.languages = ["fr-FR", "en-US"]
    cfg.trailers.fallback_youtube_search = fallback
    cfg.trailers.search_query_format = "{title} {year} bande annonce"
    cfg.trailers.filters.min_file_size_bytes = 102400
    cfg.trailers.filters.max_filesize_mb = 500
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.trailers.retry_after_days = [1, 7, 30]
    cfg.trailers.ytdlp.format = "best[ext=mp4]/best"
    cfg.trailers.ytdlp.socket_timeout_sec = 30
    cfg.trailers.ytdlp.retries = 3
    cfg.trailers.seasons.enabled = False
    cfg.trailers.library_check.movies = library_movies
    cfg.trailers.library_check.tv_shows = library_tv
    # Large budget so the step-budget break never fires in these unit tests.
    cfg.trailers.step.max_duration_sec = 1800
    return cfg


def _make_orchestrator(config: MagicMock, tmp_path: Path) -> TrailersOrchestrator:
    """Construct a ``TrailersOrchestrator`` with a real EventBus.

    Args:
        config: The mock config from :func:`_make_config`.
        tmp_path: Staging directory root (unused by the driven tests, which
            supply items directly, but required by the constructor).

    Returns:
        A fully wired orchestrator whose ``_finder`` is non-None.
    """
    return TrailersOrchestrator(
        config=config,
        staging_dir=tmp_path,
        event_bus=EventBus(),
        registry=MagicMock(spec=ProviderRegistry),
    )


def _state_key(item: ScanItem) -> str:
    """Recompute the composite state key exactly as the orchestrator does.

    Args:
        item: The ScanItem the orchestrator processed.

    Returns:
        The composite state-store key for that item.
    """
    return make_state_key(
        media_type=MediaType.from_legacy(item.media_type),
        ids={"tmdb": item.tmdb_id, "tvdb": None},
        title=item.title,
        year=item.year,
        season_number=item.season_number,
    )


def _persisted_state(orchestrator: TrailersOrchestrator, item: ScanItem) -> TrailerState | None:
    """Read back the persisted ``TrailerState`` for ``item``, or None if absent.

    Args:
        orchestrator: The orchestrator whose state store to query.
        item: The ScanItem whose persisted state to fetch.

    Returns:
        The persisted ``TrailerState``, or ``None`` when the orchestrator wrote
        no state entry for this item.
    """
    return orchestrator._state_store.get(_state_key(item))


def _def_download(url: str, dest: Path) -> DownloadResult:  # noqa: ARG001
    """Guard downloader used when a scenario must not reach the download step.

    Raises:
        AssertionError: Always — reaching a real download in a short-circuit
            scenario is a characterization failure (and would invoke yt-dlp).
    """
    raise AssertionError("downloader.download must not be called in this scenario")


def _dl_success(url: str, dest: Path) -> DownloadResult:  # noqa: ARG001
    """Fake a successful download by materializing the trailer at ``dest``.

    Args:
        url: Resolved video URL (ignored).
        dest: Placement path the orchestrator computed and passed in.

    Returns:
        A ``SUCCESS`` result whose ``output_path`` is the created file.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_TRAILER_BYTES)
    return DownloadResult(status=DownloadStatus.SUCCESS, output_path=dest, error_message=None)


def _dl_status(status: DownloadStatus) -> Callable[[str, Path], DownloadResult]:
    """Build a fake downloader that returns a failure ``status`` and no file.

    Args:
        status: The non-success ``DownloadStatus`` to report.

    Returns:
        A callable matching the ``download(url, dest)`` signature.
    """

    def _download(url: str, dest: Path) -> DownloadResult:  # noqa: ARG001
        return DownloadResult(status=status, output_path=None, error_message="boom")

    return _download


def _drive(
    orchestrator: TrailersOrchestrator,
    item: ScanItem,
    expected_path: Path,
    *,
    skip: bool = False,
    disk_full: bool = False,
    find_return: Any = _UNSET,
    find_raise: BaseException | None = None,
    download: Callable[[str, Path], DownloadResult] = _def_download,
) -> dict[str, Any]:
    """Drive ``run()`` for a single item and return its normalized outcome.

    The scanner, finder, and downloader are always patched so no real network
    or yt-dlp call can occur. ``find`` and ``download`` default to guards that
    fail loudly if a short-circuit scenario unexpectedly reaches them.

    Args:
        orchestrator: The orchestrator under test.
        item: The single ScanItem to process.
        expected_path: The Plex-conformant trailer path for ``item`` (used to
            report the ``trailer_placed`` filesystem effect).
        skip: When True, patch ``should_skip`` to return True.
        disk_full: When True, patch ``shutil.disk_usage`` to report zero free.
        find_return: Return value for ``finder.find`` (``None`` is a valid
            value meaning "no trailer found"); ``_UNSET`` leaves the guard.
        find_raise: Exception for ``finder.find`` to raise, if any.
        download: Fake ``download(url, dest)`` implementation.

    Returns:
        A normalized outcome dict with volatile fields collapsed.
    """
    contexts: list[Any] = [
        patch.object(orchestrator._scanner, "scan_staging", return_value=[item]),
        patch.object(orchestrator._downloader, "download", side_effect=download),
    ]
    if find_raise is not None:
        contexts.append(patch.object(orchestrator._finder, "find", side_effect=find_raise))
    elif find_return is not _UNSET:
        contexts.append(patch.object(orchestrator._finder, "find", return_value=find_return))
    else:
        contexts.append(
            patch.object(
                orchestrator._finder,
                "find",
                side_effect=AssertionError("finder.find must not be called in this scenario"),
            )
        )
    if skip:
        contexts.append(patch.object(orchestrator._state_store, "should_skip", return_value=True))
    if disk_full:
        contexts.append(
            patch(
                "personalscraper.trailers.orchestrator.shutil.disk_usage",
                return_value=SimpleNamespace(total=0, used=0, free=0),
            )
        )

    with contextlib.ExitStack() as stack:
        for ctx in contexts:
            stack.enter_context(ctx)
        counts = orchestrator.run()

    state = _persisted_state(orchestrator, item)
    return {
        "item_results": [(status, reason) for (_path, status, reason) in orchestrator.item_results],
        "failed_kinds": [kind for (_key, kind, _notes) in orchestrator.failed_items],
        "counts": {key: value for key, value in counts.items() if value},
        "state_status": state.status.value if state is not None else None,
        "state_attempts": state.attempts if state is not None else None,
        "next_retry_set": (state.next_retry_at is not None) if state is not None else None,
        "trailer_placed": expected_path.exists(),
    }


def _movie_item(tmp_path: Path) -> tuple[ScanItem, Path]:
    """Create a movie ScanItem plus its expected flat trailer path.

    Args:
        tmp_path: Pytest tmp_path fixture.

    Returns:
        ``(item, expected_trailer_path)`` for a Fight Club (1999) movie dir.
    """
    media_dir = tmp_path / "Fight Club (1999)"
    media_dir.mkdir()
    item = ScanItem(
        path=media_dir,
        media_type="movie",
        title="Fight Club",
        year=1999,
        tmdb_id="550",
    )
    expected = trailer_path_for(media_dir, media_dir.name, media_type="movie", ext="mp4")
    return item, expected


# ---------------------------------------------------------------------------
# The outcome ladder: (status, reason) reported x state x filesystem, per branch
# ---------------------------------------------------------------------------

_LADDER: list[Any] = [
    pytest.param(
        {"skip": True},
        {
            "item_results": [("skipped", "skipped_by_state")],
            "failed_kinds": [],
            "counts": {"skipped_by_state": 1},
            "state_status": None,
            "state_attempts": None,
            "next_retry_set": None,
            "trailer_placed": False,
        },
        id="skipped_by_state",
    ),
    pytest.param(
        {"disk_full": True},
        {
            "item_results": [("skipped", "skipped_by_filter")],
            "failed_kinds": [],
            "counts": {"skipped_by_filter": 1},
            "state_status": None,
            "state_attempts": None,
            "next_retry_set": None,
            "trailer_placed": False,
        },
        id="skipped_by_filter",
    ),
    pytest.param(
        {"find_return": None},
        {
            "item_results": [("no_trailer", "no_trailer")],
            "failed_kinds": ["no_trailer"],
            "counts": {"no_trailer": 1},
            "state_status": "no_trailer_available",
            "state_attempts": 1,
            "next_retry_set": True,
            "trailer_placed": False,
        },
        id="no_trailer",
    ),
    pytest.param(
        {"find_raise": CircuitOpenError("trailers_youtube", 5.0)},
        {
            "item_results": [("error", "circuit_open")],
            "failed_kinds": ["circuit_open"],
            "counts": {"circuit_open": 1},
            "state_status": "http_error",
            "state_attempts": 1,
            "next_retry_set": True,
            "trailer_placed": False,
        },
        id="circuit_open",
    ),
    pytest.param(
        {"find_raise": ValueError("finder blew up")},
        {
            # ASYMMETRY: the generic finder error appends NO item_results entry
            # (only the CircuitOpenError branch does). Pinned as the empty list.
            "item_results": [],
            "failed_kinds": ["error"],
            "counts": {"error": 1},
            "state_status": "http_error",
            "state_attempts": 1,
            "next_retry_set": True,
            "trailer_placed": False,
        },
        id="finder_error_no_item_result",
    ),
    pytest.param(
        {"find_return": _MOVIE_URL, "download": _dl_success},
        {
            "item_results": [("downloaded", "downloaded")],
            "failed_kinds": [],
            "counts": {"downloaded": 1},
            # P6.4 single-truth: a successful download records NO presence claim in
            # the state JSON (the ledger tracks failures/cooldowns only) — it clears
            # any prior entry, so no state is persisted here. Presence is the
            # filesystem's truth (``trailer_placed`` True) + the derived index.
            # Previously pinned status="downloaded"/attempts=1/next_retry_set=False.
            "state_status": None,
            "state_attempts": None,
            "next_retry_set": None,
            "trailer_placed": True,
        },
        id="downloaded",
    ),
    pytest.param(
        {"find_return": _MOVIE_URL, "download": _dl_status(DownloadStatus.BOT_DETECTED)},
        {
            "item_results": [("bot_detected", "bot_detected")],
            "failed_kinds": ["bot_detected"],
            "counts": {"bot_detected": 1},
            "state_status": "bot_detected",
            "state_attempts": 1,
            # BOT_DETECTED does not write a next_retry_at cooldown (always retried).
            "next_retry_set": False,
            "trailer_placed": False,
        },
        id="bot_detected",
    ),
    pytest.param(
        {"find_return": _MOVIE_URL, "download": _dl_status(DownloadStatus.HTTP_ERROR)},
        {
            "item_results": [("error", "http_error")],
            "failed_kinds": ["http_error"],
            "counts": {"http_error": 1},
            "state_status": "http_error",
            "state_attempts": 1,
            "next_retry_set": True,
            "trailer_placed": False,
        },
        id="http_error",
    ),
    pytest.param(
        {"find_return": _MOVIE_URL, "download": _dl_status(DownloadStatus.YTDLP_ERROR)},
        {
            "item_results": [("error", "ytdlp_error")],
            "failed_kinds": ["ytdlp_error"],
            "counts": {"ytdlp_error": 1},
            "state_status": "ytdlp_error",
            "state_attempts": 1,
            "next_retry_set": True,
            "trailer_placed": False,
        },
        id="ytdlp_error",
    ),
]


class TestTrailerOutcomeTaxonomy:
    """Pin every per-item outcome of ``run()`` as a normalized status map.

    One parametrized case per distinct code branch. Each asserts the exact
    reported result, the persisted state mutation, and the filesystem effect
    for a movie item — the full ladder minus ``already_present`` (its own
    test, which needs a pre-existing file) and ``already_present_on_disk``
    (the library-aware recheck, pinned in :class:`TestTrailerLibraryOnDisk`).
    """

    @pytest.mark.parametrize(("setup", "expected"), _LADDER)
    def test_outcome_status_map(self, tmp_path: Path, setup: dict[str, Any], expected: dict[str, Any]) -> None:
        """Each branch yields its pinned normalized outcome.

        Args:
            tmp_path: Pytest tmp_path fixture.
            setup: Keyword arguments forwarded to :func:`_drive`.
            expected: The frozen normalized outcome dict.
        """
        config = _make_config(tmp_path)
        orchestrator = _make_orchestrator(config, tmp_path)
        item, expected_path = _movie_item(tmp_path)

        outcome = _drive(orchestrator, item, expected_path, **setup)

        assert outcome == expected

    def test_already_present_short_circuits_before_finder(self, tmp_path: Path) -> None:
        """A pre-existing staging trailer yields ``already_present`` with no state write.

        The trailer file exists before the run, so the SOT check short-circuits
        before the finder and downloader (both left as guards that would raise
        if reached), no ``TrailerState`` is persisted, and the counter is
        ``already_present``.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        config = _make_config(tmp_path)
        orchestrator = _make_orchestrator(config, tmp_path)
        item, expected_path = _movie_item(tmp_path)
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_bytes(_TRAILER_BYTES)

        outcome = _drive(orchestrator, item, expected_path)

        assert outcome == {
            "item_results": [("already_present", "already_present")],
            "failed_kinds": [],
            "counts": {"already_present": 1},
            "state_status": None,
            "state_attempts": None,
            "next_retry_set": None,
            "trailer_placed": True,
        }

    def test_bot_detected_records_consecutive_attempt_counter(self, tmp_path: Path) -> None:
        """The BOT_DETECTED state pins ``bot_detected_consecutive_attempts == 1``.

        This counter is unique to the bot-detected branch (all other branches
        leave it at its default 0), so it is pinned separately from the
        normalized ladder map.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        config = _make_config(tmp_path)
        orchestrator = _make_orchestrator(config, tmp_path)
        item, expected_path = _movie_item(tmp_path)

        _drive(
            orchestrator,
            item,
            expected_path,
            find_return=_MOVIE_URL,
            download=_dl_status(DownloadStatus.BOT_DETECTED),
        )

        state = _persisted_state(orchestrator, item)
        assert state is not None
        assert state.bot_detected_consecutive_attempts == 1


def _tv_item(tmp_path: Path) -> tuple[ScanItem, Path]:
    """Create a show-level TV ScanItem plus its expected subfolder trailer path.

    Args:
        tmp_path: Pytest tmp_path fixture.

    Returns:
        ``(item, expected_trailer_path)`` for a Game of Thrones (2011) show dir.
        The expected path is the Plex TV convention: ``Trailers/<name>.mp4``.
    """
    show_dir = tmp_path / "Game of Thrones (2011)"
    show_dir.mkdir()
    item = ScanItem(
        path=show_dir,
        media_type="tvshow",
        title="Game of Thrones",
        year=2011,
        tmdb_id="1399",
    )
    expected = trailer_path_for(show_dir, show_dir.name, media_type="tvshow", ext="mp4")
    return item, expected


class TestTrailerPlacementFamilies:
    """Pin the family-specific Plex-conformant placement of the PLACED outcome.

    Movies place flat (``<name>-trailer.ext`` next to the media file); TV shows
    place in a ``Trailers/`` subfolder (``Trailers/<name>.ext``). Both are pinned
    for the successful-download outcome so the P6 refactor cannot silently move
    a family's trailer to the wrong Plex location.
    """

    def test_movie_places_trailer_flat(self, tmp_path: Path) -> None:
        """A downloaded movie trailer lands flat at ``<name>-trailer.mp4``.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        config = _make_config(tmp_path)
        orchestrator = _make_orchestrator(config, tmp_path)
        item, expected_path = _movie_item(tmp_path)

        outcome = _drive(orchestrator, item, expected_path, find_return=_MOVIE_URL, download=_dl_success)

        assert expected_path == item.path / "Fight Club (1999)-trailer.mp4"
        assert outcome["trailer_placed"] is True
        assert outcome["counts"] == {"downloaded": 1}
        # P6.4 single-truth: success writes no presence claim (was "downloaded").
        assert outcome["state_status"] is None

    def test_tvshow_places_trailer_in_subfolder(self, tmp_path: Path) -> None:
        """A downloaded TV-show trailer lands in ``Trailers/<name>.mp4``.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        config = _make_config(tmp_path)
        orchestrator = _make_orchestrator(config, tmp_path)
        item, expected_path = _tv_item(tmp_path)

        outcome = _drive(
            orchestrator, item, expected_path, find_return="https://youtube.com/watch?v=TV", download=_dl_success
        )

        assert expected_path == item.path / "Trailers" / "Game of Thrones (2011).mp4"
        assert outcome["trailer_placed"] is True
        assert outcome["counts"] == {"downloaded": 1}
        # P6.4 single-truth: success writes no presence claim (was "downloaded").
        assert outcome["state_status"] is None


class TestTrailerDownloadSideEffects:
    """Pin the download-only side effects: bus emit, indexer outbox, NFO tag.

    These effects fire ONLY on a successful download; the ladder tests already
    pin that failing outcomes leave them untouched, and one negative case here
    re-confirms the bus stays silent on a bot-detected outcome.
    """

    def test_success_emits_single_trailer_downloaded_event(self, tmp_path: Path) -> None:
        """A successful download emits exactly one ``TrailerDownloaded`` on the real bus.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        config = _make_config(tmp_path)
        orchestrator = _make_orchestrator(config, tmp_path)
        item, expected_path = _movie_item(tmp_path)

        received: list[TrailerDownloaded] = []
        orchestrator._event_bus.subscribe(TrailerDownloaded, received.append)

        _drive(orchestrator, item, expected_path, find_return=_MOVIE_URL, download=_dl_success)

        assert len(received) == 1
        event = received[0]
        assert event.media_path == item.path
        assert event.trailer_path == expected_path
        assert event.source_url == _MOVIE_URL
        assert event.source == "trailers.orchestrator"

    def test_bot_detected_emits_no_event(self, tmp_path: Path) -> None:
        """A bot-detected outcome emits no ``TrailerDownloaded`` event.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        config = _make_config(tmp_path)
        orchestrator = _make_orchestrator(config, tmp_path)
        item, expected_path = _movie_item(tmp_path)

        received: list[TrailerDownloaded] = []
        orchestrator._event_bus.subscribe(TrailerDownloaded, received.append)

        _drive(
            orchestrator,
            item,
            expected_path,
            find_return=_MOVIE_URL,
            download=_dl_status(DownloadStatus.BOT_DETECTED),
        )

        assert received == []

    def test_success_publishes_indexer_outbox_event(self, tmp_path: Path) -> None:
        """A successful download publishes a best-effort ``trailer_download`` outbox event.

        The disk resolver is stubbed to a mounted disk so the publish path (not
        the None short-circuit) is exercised, pinning the op name, source, and
        payload shape the orchestrator sends to the indexer.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        config = _make_config(tmp_path)
        orchestrator = _make_orchestrator(config, tmp_path)
        item, expected_path = _movie_item(tmp_path)

        with (
            patch(
                "personalscraper.trailers.orchestrator.disk_id_for_path",
                return_value=(7, "Movies/Fight Club (1999)/Fight Club (1999)-trailer.mp4"),
            ),
            patch("personalscraper.trailers.orchestrator.publish_event") as publish_mock,
        ):
            _drive(orchestrator, item, expected_path, find_return=_MOVIE_URL, download=_dl_success)

        assert publish_mock.call_count == 1
        _args, kwargs = publish_mock.call_args
        assert publish_mock.call_args.args[0] == 7
        assert kwargs["op"] == "trailer_download"
        assert kwargs["source"] == "trailers"
        assert kwargs["payload"]["rel_path"] == "Movies/Fight Club (1999)/Fight Club (1999)-trailer.mp4"
        assert kwargs["payload"]["trailer_path"] == str(expected_path)

    def test_success_writes_trailer_url_into_nfo(self, tmp_path: Path) -> None:
        """A successful download populates the ``<trailer>`` tag in the item's NFO.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from xml.etree import ElementTree as ET

        config = _make_config(tmp_path)
        orchestrator = _make_orchestrator(config, tmp_path)
        item_base, expected_path = _movie_item(tmp_path)
        nfo_path = item_base.path / "movie.nfo"
        nfo_path.write_text("<movie><title>Fight Club</title><trailer></trailer></movie>", encoding="utf-8")
        item = ScanItem(
            path=item_base.path,
            media_type="movie",
            title="Fight Club",
            year=1999,
            tmdb_id="550",
            nfo_path=nfo_path,
        )

        _drive(orchestrator, item, expected_path, find_return=_MOVIE_URL, download=_dl_success)

        trailer_elem = ET.parse(nfo_path).getroot().find("trailer")
        assert trailer_elem is not None
        assert trailer_elem.text == _MOVIE_URL


class TestTrailerLibraryOnDisk:
    """Pin the library-aware SOT recheck outcome (``already_present_on_disk``).

    When the per-type library check is enabled and the indexer reports a
    dispatched on-disk path whose Plex-conformant trailer already exists, the
    orchestrator short-circuits before any network call, writes an
    ``ALREADY_PRESENT_ON_DISK`` state, and never reaches the finder/downloader.
    """

    def test_trailer_found_on_storage_disk_short_circuits(self, tmp_path: Path) -> None:
        """An existing on-disk trailer yields ``already_present_on_disk`` + state write.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        config = _make_config(tmp_path, library_tv=True)
        orchestrator = _make_orchestrator(config, tmp_path)
        item, _staging_expected = _tv_item(tmp_path)

        # Simulate a dispatched library copy on a storage disk that already has
        # its Plex TV-show trailer in place.
        lib_dir = tmp_path / "storage" / "Game of Thrones (2011)"
        lib_dir.mkdir(parents=True)
        lib_trailer = trailer_path_for(lib_dir, lib_dir.name, media_type="tvshow", ext="mp4")
        lib_trailer.parent.mkdir(parents=True, exist_ok=True)
        lib_trailer.write_bytes(_TRAILER_BYTES)
        index = {("tv_shows", "1399"): _LibraryEntry(path=str(lib_dir))}

        with patch.object(orchestrator, "_build_library_index", return_value=index):
            outcome = _drive(orchestrator, item, lib_trailer)

        assert outcome == {
            "item_results": [("already_present", "already_present_on_disk")],
            "failed_kinds": [],
            "counts": {"already_present_on_disk": 1},
            # P6.4 single-truth: the library-aware recheck no longer persists an
            # ALREADY_PRESENT_ON_DISK presence claim — presence is the filesystem
            # (``trailer_placed`` True) + the derived index. No state is written
            # (any stale ledger entry is cleared). Previously pinned
            # status="already_present_on_disk"/attempts=1/next_retry_set=False.
            "state_status": None,
            "state_attempts": None,
            "next_retry_set": None,
            "trailer_placed": True,
        }
