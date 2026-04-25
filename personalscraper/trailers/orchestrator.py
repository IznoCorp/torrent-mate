"""Trailers orchestrator, full pipeline glue.

Connects Scanner, TrailerFinder, YtdlpDownloader, and TrailerStateStore.
Implements DESIGN SS3 (orchestrator), SS7 (state tracking), SS8 (library-aware
SOT recheck), and SS12 (step budget + disk-space pre-check).
"""

from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from personalscraper.library import scanner as library_scanner
from personalscraper.scraper.ytdlp_downloader import DownloadStatus, YtdlpDownloader
from personalscraper.trailers.placement import (
    trailer_exists,
    trailer_path_for,
    trailer_path_for_season,
    write_trailer_url_to_nfo,
)
from personalscraper.trailers.scanner import Scanner
from personalscraper.trailers.state import (
    TrailerState,
    TrailerStateStore,
    TrailerStatus,
    compute_next_retry_at,
    make_state_key,
)

if TYPE_CHECKING:
    from personalscraper.scraper.trailer_finder import TrailerFinder

log = structlog.get_logger(__name__)

_DEFAULT_MAX_DURATION_SEC: int = 1800
_DEFAULT_EXT: str = "mp4"


class TrailersOrchestrator:
    """Full trailer acquisition pipeline: scan -> find -> download -> state.

    Wires together Scanner, TrailerFinder, YtdlpDownloader, and TrailerStateStore.
    Stateless between runs - each run() call rebuilds transient caches from scratch.

    Attributes:
        _config: Loaded pipeline Config.
        _staging_dir: Staging area path.
        _scanner: Media-without-trailer detector.
        _finder: TMDB-first / YouTube-fallback URL finder (or None).
        _downloader: yt-dlp wrapper.
        _state_store: Persistent JSON state store.
        _failed_items: Per-item failure list populated by run().
        _library_index: Lazily built index of library items by (category, id).
    """

    def __init__(self, config: Any, staging_dir: Path | None) -> None:
        """Wire up Scanner, TrailerFinder, YtdlpDownloader, TrailerStateStore.

        Args:
            config: Loaded pipeline Config.
            staging_dir: Path to the staging area (for pipeline step) or None.
        """
        self._config = config
        self._staging_dir = staging_dir
        self._failed_items: list[tuple[str, str, str]] = []

        min_size = int(config.trailers.filters.min_file_size_bytes)
        seasons_enabled: bool = False
        try:
            seasons_enabled = bool(config.trailers.seasons.enabled)
        except AttributeError:
            pass

        self._scanner = Scanner(
            min_file_size_bytes=min_size,
            seasons_enabled=seasons_enabled,
        )

        self._finder: TrailerFinder | None = self._build_finder()

        output_dir = staging_dir if staging_dir is not None else Path(".")
        self._downloader = YtdlpDownloader(
            output_dir=output_dir,
            ytdlp_format=str(config.trailers.ytdlp.format),
            socket_timeout_sec=int(config.trailers.ytdlp.socket_timeout_sec),
            retries=int(config.trailers.ytdlp.retries),
            cookie_config=None,
        )

        state_file = Path(str(config.trailers.state_file))
        self._state_store = TrailerStateStore(state_file=state_file)

        self._library_index: dict[tuple[str, str], Any] | None = None

    def run(self) -> dict[str, int]:
        """Execute the full trailer acquisition loop.

        1. state_store.auto_gc() once.
        2. Record step-budget start time.
        2bis. Resolve library_check toggles; library index built lazily on first need.
        3. For each ScanItem:
           a. Build composite state key.
           b. state_store.should_skip() -> skipped_by_state.
           b-new. Library-aware SOT recheck (per-type toggle).
           c. SOT recheck (staging).
           d. Disk-space pre-check.
           e. Step-budget check.
           f. finder.find() -> no_trailer.
           g. downloader.download() -> handle DownloadStatus.
           h. Update state.
        4. Return counts dict.

        Returns:
            Counts dict with keys: downloaded, already_present,
            already_present_on_disk, no_trailer, bot_detected, http_error,
            ytdlp_error, skipped_by_state, skipped_by_filter, error.
        """
        self._failed_items = []

        counts: dict[str, int] = {
            "downloaded": 0,
            "already_present": 0,
            "already_present_on_disk": 0,
            "no_trailer": 0,
            "bot_detected": 0,
            "http_error": 0,
            "ytdlp_error": 0,
            "skipped_by_state": 0,
            "skipped_by_filter": 0,
            "error": 0,
        }

        self._state_store.auto_gc()

        step_start = time.monotonic()
        max_duration_sec: int = _DEFAULT_MAX_DURATION_SEC
        try:
            max_duration_sec = int(self._config.trailers.step.max_duration_sec)
        except AttributeError:
            pass

        min_size = int(self._config.trailers.filters.min_file_size_bytes)
        max_filesize_mb: int = 500
        try:
            max_filesize_mb = int(self._config.trailers.filters.max_filesize_mb)
        except AttributeError:
            pass
        required_free: float = max_filesize_mb * 1024 * 1024 * 1.5

        retry_policy: list[int] = [1, 7, 30]
        try:
            retry_policy = list(self._config.trailers.retry_after_days)
        except AttributeError:
            pass

        movies_check: bool = False
        tvshows_check: bool = False
        try:
            movies_check = bool(self._config.trailers.library_check.movies)
            tvshows_check = bool(self._config.trailers.library_check.tv_shows)
        except AttributeError:
            pass

        self._library_index = None

        staging_dir = self._staging_dir if self._staging_dir is not None else Path(".")
        items = self._scanner.scan_staging(staging_dir)

        for item in items:
            ids: dict[str, str | int | None] = {"tmdb": item.tmdb_id, "tvdb": None}
            key_media_type = "tv" if item.media_type == "tvshow" else item.media_type
            try:
                key = make_state_key(
                    media_type=key_media_type,
                    ids=ids,
                    title=item.title,
                    year=item.year,
                    season_number=item.season_number,
                )
            except ValueError as exc:
                log.warning("trailers_orchestrator_key_error", title=item.title, error=str(exc))
                counts["error"] += 1
                self._failed_items.append((str(item.path), "error", str(exc)))
                continue

            if self._state_store.should_skip(key):
                log.debug("trailers_skipped_by_state", key=key, title=item.title)
                counts["skipped_by_state"] += 1
                continue

            apply_library_check = tvshows_check if item.media_type == "tvshow" else movies_check
            if apply_library_check:
                if self._library_index is None:
                    self._library_index = self._build_library_index()
                lib_item = self._lookup_library_item(item)
                if lib_item is not None:
                    lib_path = Path(lib_item.path)
                    if item.season_number is not None:
                        lib_trailer = trailer_path_for_season(lib_path, item.season_number, _DEFAULT_EXT)
                    else:
                        lib_trailer = trailer_path_for(lib_path, lib_path.name, ext=_DEFAULT_EXT)
                    if trailer_exists(lib_trailer, min_size):
                        log.info(
                            "trailers_already_present_on_disk",
                            key=key,
                            title=item.title,
                            trailer_path=str(lib_trailer),
                        )
                        self._state_store.set(
                            key,
                            TrailerState(
                                last_attempt=datetime.now(timezone.utc).isoformat(),
                                attempts=1,
                                status=TrailerStatus.ALREADY_PRESENT_ON_DISK,
                                media_path=str(item.path),
                                trailer_path=str(lib_trailer),
                                season_number=item.season_number,
                            ),
                        )
                        counts["already_present_on_disk"] += 1
                        continue

            media_name = item.path.name
            # Season-level ScanItems use item.path = show_dir (verified in scanner.py).
            # Use the seasonal placement path so the SOT check and downloader target
            # match the correct per-season file; show-level items use the flat convention.
            if item.season_number is not None:
                expected_path = trailer_path_for_season(item.path, item.season_number, _DEFAULT_EXT)
            else:
                expected_path = trailer_path_for(item.path, media_name, ext=_DEFAULT_EXT)
            if trailer_exists(expected_path, min_size):
                log.debug("trailers_already_present", key=key, title=item.title)
                counts["already_present"] += 1
                continue

            _disk_ok = True
            try:
                free_bytes = shutil.disk_usage(expected_path.parent).free
                if free_bytes < required_free:
                    log.warning(
                        "trailers_disk_space_low",
                        key=key,
                        title=item.title,
                        free_bytes=free_bytes,
                        required_bytes=required_free,
                    )
                    _disk_ok = False
            except OSError:
                # Parent directory does not exist yet; downloader will create it.
                # Treat as sufficient space and proceed.
                pass
            if not _disk_ok:
                counts["skipped_by_filter"] += 1
                continue

            elapsed = time.monotonic() - step_start
            if elapsed >= max_duration_sec:
                log.warning(
                    "trailers_step_budget_exceeded",
                    elapsed_sec=elapsed,
                    max_duration_sec=max_duration_sec,
                )
                break

            url: str | None = None
            if self._finder is not None:
                try:
                    tmdb_id_int: int | None = int(item.tmdb_id) if item.tmdb_id else None
                    find_media_type = "tv" if item.media_type == "tvshow" else item.media_type
                    url = self._finder.find(
                        tmdb_id_int,  # type: ignore[arg-type]
                        find_media_type,
                        title=item.title,
                        year=item.year,
                        season_number=item.season_number,
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("trailers_finder_error", key=key, title=item.title, error=str(exc))
                    counts["error"] += 1
                    self._failed_items.append((key, "error", str(exc)))
                    self._state_store.set(
                        key,
                        TrailerState(
                            last_attempt=datetime.now(timezone.utc).isoformat(),
                            attempts=1,
                            status=TrailerStatus.SKIPPED_BY_FILTER,
                            media_path=str(item.path),
                            next_retry_at=compute_next_retry_at(
                                1, retry_policy, last_attempt=datetime.now(timezone.utc)
                            ).isoformat(),
                            notes=str(exc),
                            season_number=item.season_number,
                        ),
                    )
                    continue

            if url is None:
                log.info("trailers_no_trailer_found", key=key, title=item.title)
                counts["no_trailer"] += 1
                self._failed_items.append((key, "no_trailer", ""))
                self._state_store.set(
                    key,
                    TrailerState(
                        last_attempt=datetime.now(timezone.utc).isoformat(),
                        attempts=1,
                        status=TrailerStatus.NO_TRAILER_AVAILABLE,
                        media_path=str(item.path),
                        next_retry_at=compute_next_retry_at(
                            1, retry_policy, last_attempt=datetime.now(timezone.utc)
                        ).isoformat(),
                        season_number=item.season_number,
                    ),
                )
                continue

            # SOT recheck immediately before download (race guard):
            # the trailer may have appeared between the initial SOT check (step c)
            # and now (e.g. another process placed it while find() was running).
            if trailer_exists(expected_path, min_size):
                log.debug("trailers_already_present", key=key, title=item.title)
                counts["already_present"] += 1
                continue

            result = self._downloader.download(url, expected_path)
            now_iso = datetime.now(timezone.utc).isoformat()

            if result.status == DownloadStatus.SUCCESS:
                log.info(
                    "trailers_downloaded",
                    key=key,
                    title=item.title,
                    url=url,
                    output_path=str(result.output_path),
                )
                counts["downloaded"] += 1
                self._state_store.set(
                    key,
                    TrailerState(
                        last_attempt=now_iso,
                        attempts=1,
                        status=TrailerStatus.DOWNLOADED,
                        media_path=str(item.path),
                        trailer_path=str(result.output_path) if result.output_path else None,
                        youtube_url=url,
                        source="youtube",
                        season_number=item.season_number,
                    ),
                )
                # Propagate the trailer URL into the NFO <trailer> tag so that
                # Plex / Kodi can display the remote trailer as a fallback.
                # Silently skip when there is no NFO (movies without scrape, etc.).
                if item.nfo_path is not None:
                    write_trailer_url_to_nfo(item.nfo_path, url)

            elif result.status == DownloadStatus.BOT_DETECTED:
                log.warning("trailers_bot_detected", key=key, title=item.title, url=url)
                counts["bot_detected"] += 1
                self._failed_items.append((key, "bot_detected", result.error_message or ""))
                self._state_store.set(
                    key,
                    TrailerState(
                        last_attempt=now_iso,
                        attempts=1,
                        status=TrailerStatus.BOT_DETECTED,
                        media_path=str(item.path),
                        youtube_url=url,
                        notes=result.error_message,
                        bot_detected_consecutive_attempts=1,
                        season_number=item.season_number,
                    ),
                )

            elif result.status == DownloadStatus.HTTP_ERROR:
                log.warning("trailers_http_error", key=key, title=item.title, url=url)
                counts["http_error"] += 1
                self._failed_items.append((key, "http_error", result.error_message or ""))
                self._state_store.set(
                    key,
                    TrailerState(
                        last_attempt=now_iso,
                        attempts=1,
                        status=TrailerStatus.HTTP_ERROR,
                        media_path=str(item.path),
                        next_retry_at=compute_next_retry_at(
                            1, retry_policy, last_attempt=datetime.now(timezone.utc)
                        ).isoformat(),
                        youtube_url=url,
                        notes=result.error_message,
                        season_number=item.season_number,
                    ),
                )

            else:
                log.warning("trailers_ytdlp_error", key=key, title=item.title, url=url)
                counts["ytdlp_error"] += 1
                self._failed_items.append((key, "ytdlp_error", result.error_message or ""))
                self._state_store.set(
                    key,
                    TrailerState(
                        last_attempt=now_iso,
                        attempts=1,
                        status=TrailerStatus.YTDLP_ERROR,
                        media_path=str(item.path),
                        next_retry_at=compute_next_retry_at(
                            1, retry_policy, last_attempt=datetime.now(timezone.utc)
                        ).isoformat(),
                        youtube_url=url,
                        notes=result.error_message,
                        season_number=item.season_number,
                    ),
                )

        return counts

    @property
    def failed_items(self) -> list[tuple[str, str, str]]:
        """List of (key, status, reason) for items that did not get a trailer.

        Returns:
            Per-item failure tuples: (composite_key, status_string, notes).
        """
        return list(self._failed_items)

    def _build_finder(self) -> "TrailerFinder | None":
        """Attempt to construct a TrailerFinder from config values.

        Returns None when the TMDB/YouTube clients are not yet wired (pre-Phase-7).
        Tests replace self._finder via patch.object.

        Returns:
            A TrailerFinder instance, or None when clients are unavailable.
        """
        try:
            from personalscraper.scraper.tmdb_client import TMDBClient  # noqa: PLC0415
            from personalscraper.scraper.trailer_finder import TrailerFinder  # noqa: PLC0415
            from personalscraper.scraper.trailers_cache import TrailersCache  # noqa: PLC0415
            from personalscraper.scraper.youtube_search import YoutubeSearch  # noqa: PLC0415

            tmdb_key = str(self._config.tmdb.api_key)
            cache_dir = Path(str(self._config.trailers.state_file)).parent
            cache = TrailersCache(cache_dir / "trailers_cache.json")
            tmdb_client = TMDBClient(api_key=tmdb_key)
            youtube_search = YoutubeSearch(
                query_format=str(self._config.trailers.search_query_format),
                api_key=None,  # type: ignore[arg-type]
                quota_cache=None,  # type: ignore[arg-type]
                breaker=None,  # type: ignore[arg-type]
            )
            languages: list[str] = list(self._config.trailers.languages)
            return TrailerFinder(
                tmdb_client=tmdb_client,
                youtube_search=youtube_search,
                cache=cache,
                languages=languages,
            )
        except Exception:  # noqa: BLE001
            return None

    def _build_library_index(self) -> dict[tuple[str, str], Any]:
        """Scan all configured disks and index LibraryScanItems by ID.

        Builds a flat dict keyed by (category, id_value) tuples for both
        tmdb_id and imdb_id of each LibraryScanItem.
        Used for the library-aware SOT recheck (DESIGN SS8).

        Returns:
            Dict mapping (category, id_value) to LibraryScanItem instances.
            Empty when the library scan fails or returns nothing.
        """
        index: dict[tuple[str, str], Any] = {}
        try:
            result = library_scanner.scan_library(self._config.disks, self._config)
        except Exception as exc:  # noqa: BLE001
            log.warning("trailers_library_index_build_failed", error=str(exc))
            return index
        for lib_item in result.items:
            if lib_item.nfo.tmdb_id:
                index[(lib_item.category, lib_item.nfo.tmdb_id)] = lib_item
            if lib_item.nfo.imdb_id:
                index[(lib_item.category, lib_item.nfo.imdb_id)] = lib_item
        log.debug("trailers_library_index_built", entries=len(index))
        return index

    def _lookup_library_item(self, item: Any) -> Any | None:
        """Look up a ScanItem in the library index by tmdb_id.

        Searches across all categories (the category dimension is ignored so
        that a show filed under tv_shows is found even when the ScanItem came
        from a differently named staging directory).

        Args:
            item: A ScanItem whose tmdb_id to use for lookup.

        Returns:
            Matching LibraryScanItem from the library index, or None.
        """
        if self._library_index is None:
            return None
        if item.tmdb_id:
            for (_, idx_id), lib_item in self._library_index.items():
                if idx_id == item.tmdb_id:
                    return lib_item
        return None
