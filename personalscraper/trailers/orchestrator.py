"""Trailers orchestrator, full pipeline glue.

Connects Scanner, TrailerFinder, YtdlpDownloader, and TrailerStateStore.
Implements DESIGN SS3 (orchestrator), SS7 (state tracking), SS8 (library-aware
SOT recheck), and SS12 (step budget + disk-space pre-check).
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from personalscraper.api._contracts import MediaType
from personalscraper.indexer.db import open_db as _open_indexer_db
from personalscraper.indexer.outbox._disk import disk_id_for_path
from personalscraper.indexer.outbox._publish import publish_event
from personalscraper.indexer.repos import item_repo as _indexer_item_repo
from personalscraper.logger import get_logger
from personalscraper.scraper.ytdlp_downloader import (
    CookieConfig,
    CookieError,
    DownloadStatus,
    YtdlpDownloader,
)
from personalscraper.trailers.events import TrailerDownloaded
from personalscraper.trailers.placement import (
    trailer_exists,
    trailer_path_for,
    trailer_path_for_season,
    write_trailer_url_to_nfo,
)
from personalscraper.trailers.scanner import Scanner
from personalscraper.trailers.state import (
    TrailerState,
    TrailerStateLocked,
    TrailerStateStore,
    TrailerStatus,
    compute_next_retry_at,
    make_state_key,
)

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus
    from personalscraper.scraper.trailer_finder import TrailerFinder

log = get_logger(__name__)

_DEFAULT_EXT: str = "mp4"


@dataclass(frozen=True)
class _LibraryEntry:
    """Minimal record stored in the library index.

    Holds only the on-disk path needed by the library-aware SOT recheck
    (DESIGN SS8).  Built from ``item_attribute.dispatch_path`` rows written by
    the dispatch layer when media is first moved to permanent storage.

    Attributes:
        path: Absolute filesystem path of the media directory on the storage
            disk (e.g. ``/Volumes/Disk1/TV/Breaking Bad (2008)``).
    """

    path: str


def _set_state_for_item(
    state_store: TrailerStateStore,
    key: str,
    state: TrailerState,
    counts: dict[str, int],
    title: str,
) -> bool:
    """Write a per-item state entry, absorbing ``TrailerStateLocked`` gracefully.

    A lock contention on a single item must not abort the entire orchestrator
    loop — it should log, increment the error counter, and let the loop
    continue to the next item.  The orchestrator-wide ``auto_gc()`` call that
    precedes the loop is deliberately *not* wrapped here (a contended GC is a
    real failure that propagates to ``step.py``).

    Args:
        state_store: The persistent state store to write to.
        key: Composite state key for this media item.
        state: The ``TrailerState`` to persist.
        counts: Running counters dict; ``counts["error"]`` is incremented on
            lock contention.
        title: Human-readable title used in the log event.

    Returns:
        ``True`` if the write succeeded, ``False`` if it was skipped due to
        lock contention (so the caller can skip any post-write work such as
        NFO updates that depend on a successful state write).
    """
    try:
        state_store.set(key, state)
        return True
    except TrailerStateLocked:
        log.warning(
            "trailers_state_locked_for_item",
            key=key,
            title=title,
        )
        counts["error"] += 1
        return False


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
        _library_index: Lazily built index mapping (category_id, id_value) to
            :class:`_LibraryEntry`.  Populated on first need during run().
    """

    def __init__(
        self,
        config: Any,
        staging_dir: Path | None,
        *,
        event_bus: "EventBus",
    ) -> None:
        """Wire up Scanner, TrailerFinder, YtdlpDownloader, TrailerStateStore.

        Args:
            config: Loaded pipeline Config.
            staging_dir: Path to the staging area (for pipeline step) or None.
            event_bus: Required :class:`~personalscraper.core.event_bus.EventBus`
                threaded from the trailers CLI command boundary or from the
                pipeline ``trailers`` step. The orchestrator emits
                ``TrailerDownloaded`` events on it and forwards it to the
                TMDB/YouTube transports + YouTube ``CircuitBreaker``.
                Sub-phase 5.2 tightened the Phase 4 ``| None`` contract;
                tests that don't care about emit can pass a fresh
                ``EventBus()`` with no subscribers.
        """
        self._config = config
        self._staging_dir = staging_dir
        self._event_bus = event_bus
        self._failed_items: list[tuple[str, str, str]] = []
        self._item_results: list[tuple[str, str, str | None]] = []

        min_size = int(config.trailers.filters.min_file_size_bytes)
        self._scanner = Scanner(
            min_file_size_bytes=min_size,
            seasons_enabled=bool(config.trailers.seasons.enabled),
        )

        self._finder: TrailerFinder | None = self._build_finder()

        # Resolve cookie configuration from env. CookieError surfaces a misconfigured
        # YOUTUBE_COOKIES_FILE (path missing or on a non-APFS volume) loudly so the user
        # learns about it rather than silently downloading without auth.
        cookie_config: CookieConfig | None
        try:
            cookie_config = CookieConfig.from_env()
        except CookieError as exc:
            log.warning("trailers_cookie_config_invalid", error=str(exc))
            cookie_config = None

        output_dir = staging_dir if staging_dir is not None else Path(".")
        self._downloader = YtdlpDownloader(
            output_dir=output_dir,
            ytdlp_format=str(config.trailers.ytdlp.format),
            socket_timeout_sec=int(config.trailers.ytdlp.socket_timeout_sec),
            retries=int(config.trailers.ytdlp.retries),
            cookie_config=cookie_config,
            max_filesize_bytes=int(config.trailers.filters.max_filesize_mb) * 1024 * 1024,
        )

        state_file = Path(str(config.trailers.state_file))
        self._state_store = TrailerStateStore(state_file=state_file)

        self._library_index: dict[tuple[str, str], _LibraryEntry] | None = None

    def run(self, items: "list[Any] | None" = None) -> dict[str, int]:
        """Execute the full trailer acquisition loop.

        1. state_store.auto_gc() once.
        2. Record step-budget start time.
        3. Resolve library_check toggles; library index built lazily on first need.
        4. For each ScanItem:
           a. Build composite state key.
           b. state_store.should_skip() -> skipped_by_state.
           c. Library-aware SOT recheck (per-type toggle).
           d. SOT recheck (staging).
           e. Disk-space pre-check.
           f. Step-budget check.
           g. finder.find() -> no_trailer.
           h. downloader.download() -> handle DownloadStatus.
           i. Update state.
        5. Return counts dict.

        Args:
            items: Pre-filtered list of ScanItems to process. When None
                (legacy callers, e.g. the pipeline step), the orchestrator
                scans staging itself. The CLI passes a list that has been
                filtered by --disk/--category/--since/--limit/--level/--season
                upstream — without this hook the real download path would
                ignore every CLI filter (see commit 28d9f75).

        Returns:
            Counts dict with keys: downloaded, already_present,
            already_present_on_disk, no_trailer, bot_detected, http_error,
            ytdlp_error, skipped_by_state, skipped_by_filter, error.
        """
        self._failed_items = []
        self._item_results = []

        # Guard: if the finder could not be constructed (import failure or
        # misconfiguration), raise immediately rather than processing items and
        # persisting NO_TRAILER_AVAILABLE for every entry the orchestrator never
        # actually inspected.  step.py catches this as a generic Exception and
        # returns status="error", which the pipeline treats appropriately.
        if self._finder is None:
            raise RuntimeError("trailers finder unavailable — check earlier trailers_finder_init_failed log entries")

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
            "circuit_open": 0,
            "error": 0,
        }

        self._state_store.auto_gc()

        step_start = time.monotonic()
        # Pydantic strict guarantees these attributes exist; access them directly.
        max_duration_sec = int(self._config.trailers.step.max_duration_sec)
        min_size = int(self._config.trailers.filters.min_file_size_bytes)
        max_filesize_mb = int(self._config.trailers.filters.max_filesize_mb)
        required_free: float = max_filesize_mb * 1024 * 1024 * 1.5
        retry_policy: list[int] = list(self._config.trailers.retry_after_days)
        movies_check = bool(self._config.trailers.library_check.movies)
        tvshows_check = bool(self._config.trailers.library_check.tv_shows)

        self._library_index = None

        if items is None:
            staging_dir = self._staging_dir if self._staging_dir is not None else Path(".")
            # Pass config so the scanner restricts to FileType.MOVIE/TVSHOW
            # staging entries — without this it walks every staging subdir and
            # classifies audio/ebook/scripts items as "movie" (2026-04-25
            # incident).
            items = self._scanner.scan_staging(staging_dir, self._config)

        for item in items:
            ids: dict[str, str | int | None] = {"tmdb": item.tmdb_id, "tvdb": None}
            key_media_type = MediaType.from_legacy(item.media_type)
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
                self._item_results.append((str(item.path), "skipped", "skipped_by_state"))
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
                        lib_trailer = trailer_path_for(
                            lib_path, lib_path.name, media_type=item.media_type, ext=_DEFAULT_EXT
                        )
                    if trailer_exists(lib_trailer, min_size):
                        log.info(
                            "trailers_already_present_on_disk",
                            key=key,
                            title=item.title,
                            trailer_path=str(lib_trailer),
                        )
                        _set_state_for_item(
                            self._state_store,
                            key,
                            TrailerState(
                                last_attempt=datetime.now(timezone.utc).isoformat(),
                                attempts=1,
                                status=TrailerStatus.ALREADY_PRESENT_ON_DISK,
                                media_path=str(item.path),
                                trailer_path=str(lib_trailer),
                                season_number=item.season_number,
                            ),
                            counts,
                            item.title,
                        )
                        counts["already_present_on_disk"] += 1
                        self._item_results.append((str(item.path), "already_present", "already_present_on_disk"))
                        continue

            media_name = item.path.name
            # Season-level ScanItems use item.path = show_dir (verified in scanner.py).
            # Use the seasonal placement path so the SOT check and downloader target
            # match the correct per-season file; show-level items use the per-type
            # convention (movies flat, TV shows in Trailers/ subfolder).
            if item.season_number is not None:
                expected_path = trailer_path_for_season(item.path, item.season_number, _DEFAULT_EXT)
            else:
                expected_path = trailer_path_for(item.path, media_name, media_type=item.media_type, ext=_DEFAULT_EXT)
            if trailer_exists(expected_path, min_size):
                log.debug("trailers_already_present", key=key, title=item.title)
                counts["already_present"] += 1
                self._item_results.append((str(item.path), "already_present", "already_present"))
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
            except FileNotFoundError:
                # Parent directory does not exist yet (typical for unscraped staging).
                # Downloader will create it; treat as sufficient space and proceed.
                # Debug-log so an unmounted disk masquerading as missing parent is
                # distinguishable from a legitimate first-run miss.
                log.debug(
                    "trailers_disk_usage_parent_missing",
                    path=str(expected_path.parent),
                )
            except OSError as exc:
                # Permission denied, broken NTFS/macFUSE mount, stale handle, etc.
                # Log loudly; the precheck is advisory only — let the download try.
                log.warning(
                    "trailers_disk_usage_unavailable",
                    path=str(expected_path.parent),
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            if not _disk_ok:
                counts["skipped_by_filter"] += 1
                self._item_results.append((str(item.path), "skipped", "skipped_by_filter"))
                continue

            elapsed = time.monotonic() - step_start
            if elapsed >= max_duration_sec:
                log.warning(
                    "trailers_step_budget_exceeded",
                    elapsed_sec=elapsed,
                    max_duration_sec=max_duration_sec,
                )
                break

            # self._finder is guaranteed non-None here: run() raises RuntimeError
            # before the loop when _finder is None (C10 guard at run() entry).
            url: str | None = None
            try:
                tmdb_id_int: int | None = int(item.tmdb_id) if item.tmdb_id else None
                find_media_type = MediaType.from_legacy(item.media_type)
                url = self._finder.find(
                    tmdb_id_int,  # type: ignore[arg-type]
                    find_media_type,
                    title=item.title,
                    year=item.year,
                    season_number=item.season_number,
                )
            except Exception as exc:  # noqa: BLE001
                # I2: circuit-breaker open is a distinct failure mode from a
                # generic finder error.  Track it separately so operators can
                # distinguish "TMDB/YouTube circuit tripped" from real errors.
                from personalscraper.api._contracts import CircuitOpenError

                is_circuit_open = isinstance(exc, CircuitOpenError)
                if is_circuit_open:
                    log.warning(
                        "trailers_finder_circuit_open",
                        key=key,
                        title=item.title,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                    counts["circuit_open"] += 1
                    self._item_results.append((str(item.path), "error", "circuit_open"))
                else:
                    log.error(
                        "trailers_finder_error",
                        key=key,
                        title=item.title,
                        error=str(exc),
                        error_type=type(exc).__name__,
                        exc_info=True,
                    )
                    counts["error"] += 1
                self._failed_items.append((key, "circuit_open" if is_circuit_open else "error", str(exc)))
                # Persist HTTP_ERROR (not SKIPPED_BY_FILTER) so the state taxonomy
                # correctly reflects a transient network/API failure rather than an
                # intentional filter exclusion.  next_retry_at gives the item a
                # backoff window before the next attempt.
                _set_state_for_item(
                    self._state_store,
                    key,
                    TrailerState(
                        last_attempt=datetime.now(timezone.utc).isoformat(),
                        attempts=1,
                        status=TrailerStatus.HTTP_ERROR,
                        media_path=str(item.path),
                        next_retry_at=compute_next_retry_at(
                            1, retry_policy, last_attempt=datetime.now(timezone.utc)
                        ).isoformat(),
                        notes=str(exc),
                        season_number=item.season_number,
                    ),
                    counts,
                    item.title,
                )
                continue

            if url is None:
                log.info("trailers_no_trailer_found", key=key, title=item.title)
                counts["no_trailer"] += 1
                self._item_results.append((str(item.path), "no_trailer", "no_trailer"))
                self._failed_items.append((key, "no_trailer", ""))
                _set_state_for_item(
                    self._state_store,
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
                    counts,
                    item.title,
                )
                continue

            # SOT recheck immediately before download (race guard):
            # the trailer may have appeared between the initial SOT check (step c)
            # and now (e.g. another process placed it while find() was running).
            if trailer_exists(expected_path, min_size):
                log.debug("trailers_already_present", key=key, title=item.title)
                counts["already_present"] += 1
                self._item_results.append((str(item.path), "already_present", "already_present"))
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
                self._item_results.append((str(item.path), "downloaded", "downloaded"))

                # Best-effort outbox publish for the indexer (DESIGN §9.1).
                if result.output_path is not None:
                    _db_path = self._config.indexer.db_path
                    resolved = disk_id_for_path(result.output_path, _db_path)
                    if resolved is not None:
                        disk_id, rel_path = resolved
                        publish_event(
                            disk_id,
                            op="trailer_download",
                            payload={
                                "rel_path": rel_path,
                                "trailer_path": str(result.output_path),
                            },
                            db_path=_db_path,
                            source="trailers",
                        )

                state_written = _set_state_for_item(
                    self._state_store,
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
                    counts,
                    item.title,
                )
                # Propagate the trailer URL into the NFO <trailer> tag so that
                # Plex / Kodi can display the remote trailer as a fallback.
                # Silently skip when there is no NFO or state write was blocked.
                if state_written and item.nfo_path is not None:
                    nfo_ok = write_trailer_url_to_nfo(item.nfo_path, url)
                    if not nfo_ok:
                        log.warning(
                            "placement.nfo_update_failed",
                            key=key,
                            title=item.title,
                            nfo_path=str(item.nfo_path),
                        )

                # Bus emit (Sub-phase 4.4) — fires only on successful
                # downloads with a real output path. ``source_url`` is the
                # ``url`` already in scope (the resolved YouTube video URL
                # passed to YtdlpDownloader.download); ``trailer_url_callsite_count: 4``
                # per the locked pre-flight grep.
                if result.output_path is not None:
                    self._event_bus.emit(
                        TrailerDownloaded(
                            source="trailers.orchestrator",
                            media_path=item.path,
                            trailer_path=result.output_path,
                            source_url=url,
                        ),
                    )

            elif result.status == DownloadStatus.BOT_DETECTED:
                log.warning("trailers_bot_detected", key=key, title=item.title, url=url)
                counts["bot_detected"] += 1
                self._item_results.append((str(item.path), "bot_detected", "bot_detected"))
                self._failed_items.append((key, "bot_detected", result.error_message or ""))
                _set_state_for_item(
                    self._state_store,
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
                    counts,
                    item.title,
                )

            elif result.status == DownloadStatus.HTTP_ERROR:
                log.warning("trailers_http_error", key=key, title=item.title, url=url)
                counts["http_error"] += 1
                self._item_results.append((str(item.path), "error", "http_error"))
                self._failed_items.append((key, "http_error", result.error_message or ""))
                _set_state_for_item(
                    self._state_store,
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
                    counts,
                    item.title,
                )

            else:
                log.warning("trailers_ytdlp_error", key=key, title=item.title, url=url)
                counts["ytdlp_error"] += 1
                self._item_results.append((str(item.path), "error", "ytdlp_error"))
                self._failed_items.append((key, "ytdlp_error", result.error_message or ""))
                _set_state_for_item(
                    self._state_store,
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
                    counts,
                    item.title,
                )

        return counts

    @property
    def item_results(self) -> list[tuple[str, str, str | None]]:
        """Per-item results: (item_path, status, reason) for every item processed."""
        return list(self._item_results)

    @property
    def failed_items(self) -> list[tuple[str, str, str]]:
        """List of (key, status, reason) for items that did not get a trailer.

        Returns:
            Per-item failure tuples: (composite_key, status_string, notes).
        """
        return list(self._failed_items)

    def _build_finder(self) -> "TrailerFinder | None":
        """Construct a fully wired TrailerFinder from config values.

        Wires the TMDB and YouTube circuit breakers from
        ``config.trailers.circuit_breakers``, the YouTube quota cache (sidecar
        ``JsonTTLCache``), and the YouTube API key from ``YOUTUBE_API_KEY`` env.
        Returns None only on import-time failure (developer error); other
        misconfigurations log loudly with exc_info so users see them.

        Returns:
            A TrailerFinder instance, or None when import fails.
        """
        try:
            from personalscraper.api.metadata.tmdb import TMDBClient  # noqa: PLC0415
            from personalscraper.api.transport._http import HttpTransport  # noqa: PLC0415
            from personalscraper.api.transport._policy import CircuitPolicy  # noqa: PLC0415
            from personalscraper.config import get_settings  # noqa: PLC0415
            from personalscraper.core.circuit import CircuitBreaker  # noqa: PLC0415
            from personalscraper.scraper.json_ttl_cache import JsonTTLCache  # noqa: PLC0415
            from personalscraper.scraper.trailer_finder import TrailerFinder  # noqa: PLC0415
            from personalscraper.scraper.trailers_cache import TrailersCache  # noqa: PLC0415
            from personalscraper.scraper.youtube_search import (  # noqa: PLC0415
                YoutubeSearch,
                youtube_api_key_from_env,
            )
        except ImportError as exc:
            log.error("trailers_finder_import_failed", error=str(exc), exc_info=True)
            return None

        try:
            settings = get_settings()
            tmdb_key = settings.tmdb_api_key
            cache_dir = Path(str(self._config.trailers.state_file)).parent
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache = TrailersCache(cache_dir / "trailers_cache.json")

            cb_cfg = self._config.trailers.circuit_breakers
            # TMDBClient builds its own breaker internally; pass the trailers-specific
            # threshold/cooldown so a YouTube outage does not trip the main TMDB breaker
            # used elsewhere in the scraper.
            tmdb_policy = TMDBClient.policy(
                tmdb_key,
                circuit=CircuitPolicy(
                    failure_threshold=int(cb_cfg.tmdb_videos.errors_threshold),
                    cooldown_seconds=int(cb_cfg.tmdb_videos.cooldown_sec),
                ),
            )
            tmdb_client = TMDBClient(transport=HttpTransport(tmdb_policy, event_bus=self._event_bus))
            youtube_breaker = CircuitBreaker(name="trailers_youtube", failure_threshold=int(cb_cfg.youtube.errors_threshold), cooldown_seconds=float(cb_cfg.youtube.cooldown_sec), event_bus=self._event_bus)  # noqa: E501  # fmt: skip

            quota_cache = JsonTTLCache(cache_dir / "youtube_quota.json")
            yt_api_cfg = self._config.trailers.youtube_api
            # Settings auto-loads .env via pydantic-settings; fall back to bare env var
            # for callers who export YOUTUBE_API_KEY explicitly (CI, monkeypatched tests).
            yt_api_key = settings.youtube_api_key or youtube_api_key_from_env()
            if not yt_api_key:
                log.warning(
                    "trailers_youtube_api_key_missing",
                    hint="set YOUTUBE_API_KEY in .env to enable the primary tier",
                )

            youtube_search = YoutubeSearch(
                query_format=str(self._config.trailers.search_query_format),
                api_key=yt_api_key,
                quota_cache=quota_cache,
                breaker=youtube_breaker,
                daily_quota_units=int(yt_api_cfg.daily_quota_units),
                search_list_cost_units=int(yt_api_cfg.search_list_cost_units),
            )
            languages: list[str] = list(self._config.trailers.languages)
            return TrailerFinder(
                tmdb_client=tmdb_client,
                youtube_search=youtube_search,
                cache=cache,
                languages=languages,
            )
        except Exception as exc:  # noqa: BLE001 — surface any misconfig loudly
            log.error(
                "trailers_finder_init_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            return None

    def _build_library_index(self) -> dict[tuple[str, str], _LibraryEntry]:
        """Query the indexer DB and index library items by ID for SOT recheck.

        Opens a read-only connection to the indexer database and retrieves all
        media items that have ``dispatch_path`` attributes (set by the dispatch
        layer when media is first moved to permanent storage).  Builds a flat
        dict keyed by ``(category_id, id_value)`` tuples using both ``tmdb_id``
        and ``imdb_id`` of each row.  Used for the library-aware SOT recheck
        (DESIGN SS8).

        Items inserted by the library scanner but not yet through dispatch
        (no ``dispatch_path`` attribute) are silently skipped — they have no
        known on-disk path and cannot be checked for an existing trailer.

        Returns:
            Dict mapping ``(category_id, id_value)`` to :class:`_LibraryEntry`.
            ``id_value`` is always a string (``str(tmdb_id)`` for integer TMDB
            IDs, ``imdb_id`` verbatim for IMDB IDs).  Returns an empty dict
            when the indexer DB is unavailable or contains no dispatched items.
        """
        index: dict[tuple[str, str], _LibraryEntry] = {}
        db_path = self._config.indexer.db_path
        if not db_path.exists():
            log.debug("trailers_library_index_db_missing", db_path=str(db_path))
            return index
        conn: sqlite3.Connection | None = None
        try:
            conn = _open_indexer_db(db_path, event_bus=self._event_bus)
            rows = _indexer_item_repo.list_all_dispatch_items(conn)
        except Exception as exc:  # noqa: BLE001 — degraded, but loudly logged
            log.error(
                "trailers_library_index_build_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            return index
        finally:
            if conn is not None:
                conn.close()
        for db_item, _disk, dispatch_path in rows:
            if not dispatch_path:
                continue
            entry = _LibraryEntry(path=dispatch_path)
            if db_item.tmdb_id is not None:
                index[(db_item.category_id, str(db_item.tmdb_id))] = entry
            if db_item.imdb_id:
                index[(db_item.category_id, db_item.imdb_id)] = entry
        log.debug("trailers_library_index_built", entries=len(index))
        return index

    def _lookup_library_item(self, item: Any) -> _LibraryEntry | None:
        """Look up a ScanItem in the library index by tmdb_id.

        Searches across all categories (the category dimension is ignored so
        that a show filed under tv_shows is found even when the ScanItem came
        from a differently named staging directory).

        Args:
            item: A ScanItem whose ``tmdb_id`` to use for lookup.

        Returns:
            Matching :class:`_LibraryEntry` from the library index, or None.
        """
        if self._library_index is None:
            return None
        if item.tmdb_id:
            for (_, idx_id), entry in self._library_index.items():
                if idx_id == item.tmdb_id:
                    return entry
        return None
