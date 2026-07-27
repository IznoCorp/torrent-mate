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

from personalscraper.api._contracts import CircuitOpenError, MediaType
from personalscraper.indexer.db import open_db as _open_indexer_db
from personalscraper.indexer.outbox._disk import disk_id_for_path
from personalscraper.indexer.outbox._publish import publish_event
from personalscraper.indexer.repos import item_repo as _indexer_item_repo
from personalscraper.logger import get_logger
from personalscraper.trailers._run_support import (
    RunContext,
    TrailerOutcome,
    _clear_state_for_item,
    _set_state_for_item,
    build_retry_state,
    youtube_search_fallback,
)
from personalscraper.trailers.discovery.ytdlp_downloader import (
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
    TrailerStateStore,
    TrailerStatus,
    make_state_key,
)

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.core.event_bus import EventBus
    from personalscraper.trailers.discovery.trailer_finder import TrailerFinder

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
        _registry: The process-scoped :class:`ProviderRegistry` from
            :class:`AppContext` (required, threaded by the boundary).
    """

    def __init__(
        self,
        config: Any,
        staging_dir: Path | None,
        *,
        event_bus: "EventBus",
        registry: "ProviderRegistry",
    ) -> None:
        """Wire up Scanner, TrailerFinder, YtdlpDownloader, TrailerStateStore.

        Args:
            config: Loaded pipeline Config.
            staging_dir: Path to the staging area (for pipeline step) or None.
            event_bus: Required :class:`~personalscraper.core.event_bus.EventBus`
                threaded from the trailers CLI command boundary or from the
                pipeline ``trailers`` step. The orchestrator emits
                ``TrailerDownloaded`` events on it and forwards it to the
                transports + YouTube ``CircuitBreaker``. Tests that don't care
                about emit can pass a fresh ``EventBus()`` with no subscribers.
            registry: Required :class:`ProviderRegistry` used by
                :class:`TrailerFinder` to resolve the ``VideoProvider``
                capability. Threaded from
                :class:`~personalscraper.core.app_context.AppContext` —
                feat/registry §5.2 (sub-phase 3.1 made this required and
                removed the transitional inline-construction fallback).
        """
        self._config = config
        self._staging_dir = staging_dir
        self._event_bus = event_bus
        self._registry = registry
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

        Runs ``auto_gc`` once, snapshots the run config, scans staging (unless
        ``items`` is supplied), then dispatches each ScanItem to
        :meth:`_process_item` (select -> resolve -> download+record), breaking
        when the step budget is exhausted.

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
            ytdlp_error, skipped_by_state, skipped_by_filter, circuit_open,
            error.
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
        ctx = self._build_run_context()
        self._library_index = None

        if items is None:
            staging_dir = self._staging_dir if self._staging_dir is not None else Path(".")
            # Pass config so the scanner restricts to FileType.MOVIE/TVSHOW
            # staging entries — without this it walks every staging subdir and
            # classifies audio/ebook/scripts items as "movie" (2026-04-25
            # incident).
            items = self._scanner.scan_staging(staging_dir, self._config)

        for item in items:
            if self._process_item(item, ctx, counts):
                break

        return counts

    def _build_run_context(self) -> RunContext:
        """Snapshot the config-derived knobs this run will use.

        Captures the step-budget start clock at call time, so callers must
        invoke this after ``auto_gc`` (matching the pre-decomposition order).

        Returns:
            An immutable :class:`RunContext` for the per-item stage helpers.
        """
        cfg = self._config.trailers
        # Pydantic strict guarantees these attributes exist; access them directly.
        max_filesize_mb = int(cfg.filters.max_filesize_mb)
        return RunContext(
            min_size=int(cfg.filters.min_file_size_bytes),
            required_free=max_filesize_mb * 1024 * 1024 * 1.5,
            retry_policy=list(cfg.retry_after_days),
            movies_check=bool(cfg.library_check.movies),
            tvshows_check=bool(cfg.library_check.tv_shows),
            fallback_yt_search=bool(cfg.fallback_youtube_search),
            max_duration_sec=int(cfg.step.max_duration_sec),
            step_start=time.monotonic(),
        )

    def _process_item(self, item: Any, ctx: RunContext, counts: dict[str, int]) -> bool:
        """Process one ScanItem through select -> resolve -> download+record.

        Args:
            item: The ScanItem to process.
            ctx: The per-run configuration snapshot.
            counts: Running counters dict, mutated in place.

        Returns:
            ``True`` when the step budget is exhausted and the run loop must
            break; ``False`` to continue with the next item.
        """
        key = self._compute_state_key(item, counts)
        if key is None:
            return False

        expected_path = self._select(item, key, ctx, counts)
        if expected_path is None:
            return False

        # Step-budget check: only items that pass every pre-flight short-circuit
        # (i.e. would otherwise reach the finder) count against the budget.
        elapsed = time.monotonic() - ctx.step_start
        if elapsed >= ctx.max_duration_sec:
            log.warning(
                "trailers_step_budget_exceeded",
                elapsed_sec=elapsed,
                max_duration_sec=ctx.max_duration_sec,
            )
            return True

        url = self._resolve(item, key, ctx, counts)
        if url is not None:
            self._download_and_record(item, key, expected_path, url, ctx, counts)
        return False

    def _compute_state_key(self, item: Any, counts: dict[str, int]) -> str | None:
        """Build the composite state key, recording a key-error outcome on failure.

        Args:
            item: The ScanItem to key.
            counts: Running counters dict (``error`` incremented on failure).

        Returns:
            The composite state key, or ``None`` when ``make_state_key`` rejected
            the item (already logged, counted, and appended to ``failed_items``).
        """
        ids: dict[str, str | int | None] = {"tmdb": item.tmdb_id, "tvdb": None}
        try:
            return make_state_key(
                media_type=MediaType.from_legacy(item.media_type),
                ids=ids,
                title=item.title,
                year=item.year,
                season_number=item.season_number,
            )
        except ValueError as exc:
            log.warning("trailers_orchestrator_key_error", title=item.title, error=str(exc))
            counts["error"] += 1
            self._failed_items.append((str(item.path), "error", str(exc)))
            return None

    def _select(self, item: Any, key: str, ctx: RunContext, counts: dict[str, int]) -> Path | None:
        """Run every pre-flight short-circuit; decide whether to attempt a download.

        Applies, in order, the state-skip, library-aware on-disk SOT recheck,
        staging SOT recheck, and disk-space pre-check — each recording its own
        terminal outcome when it fires.

        Args:
            item: The ScanItem under consideration.
            key: Composite state key for the item.
            ctx: The per-run configuration snapshot.
            counts: Running counters dict, mutated in place.

        Returns:
            The expected trailer :class:`Path` when the item should proceed to
            resolve+download, or ``None`` when a short-circuit already recorded a
            terminal outcome and the loop should advance to the next item.
        """
        if self._state_store.should_skip(key):
            log.debug("trailers_skipped_by_state", key=key, title=item.title)
            self._record_outcome(
                item, key, TrailerOutcome("skipped_by_state", item_result=("skipped", "skipped_by_state")), counts
            )
            return None

        # Library-aware SOT recheck (DESIGN SS8): a dispatched copy on a storage
        # disk may already hold its Plex-conformant trailer.
        apply_library_check = ctx.tvshows_check if item.media_type == "tvshow" else ctx.movies_check
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
                if trailer_exists(lib_trailer, ctx.min_size):
                    log.info(
                        "trailers_already_present_on_disk",
                        key=key,
                        title=item.title,
                        trailer_path=str(lib_trailer),
                    )
                    # Single-truth (P6.4): the filesystem carries presence via the
                    # derived ``trailer_found`` index — never a presence-claim
                    # state; clear any stale ledger entry instead.
                    self._record_outcome(
                        item,
                        key,
                        TrailerOutcome(
                            "already_present_on_disk",
                            item_result=("already_present", "already_present_on_disk"),
                            clear_state=True,
                        ),
                        counts,
                    )
                    return None

        # Season-level ScanItems use item.path = show_dir (verified in scanner.py);
        # use the seasonal placement path so the SOT check and downloader target the
        # correct per-season file (movies flat, TV shows in Trailers/ subfolder).
        if item.season_number is not None:
            expected_path = trailer_path_for_season(item.path, item.season_number, _DEFAULT_EXT)
        else:
            expected_path = trailer_path_for(item.path, item.path.name, media_type=item.media_type, ext=_DEFAULT_EXT)
        if trailer_exists(expected_path, ctx.min_size):
            log.debug("trailers_already_present", key=key, title=item.title)
            self._record_outcome(
                item, key, TrailerOutcome("already_present", item_result=("already_present", "already_present")), counts
            )
            return None

        # Advisory free-space pre-check on the trailer's parent directory. A
        # missing parent (unscraped staging) or a mount error is treated as
        # "enough space" — the precheck never blocks on an inconclusive probe.
        disk_ok = True
        try:
            free_bytes = shutil.disk_usage(expected_path.parent).free
            if free_bytes < ctx.required_free:
                log.warning(
                    "trailers_disk_space_low",
                    key=key,
                    title=item.title,
                    free_bytes=free_bytes,
                    required_bytes=ctx.required_free,
                )
                disk_ok = False
        except FileNotFoundError:
            # Downloader will create the parent; debug-log so an unmounted disk
            # masquerading as a missing parent stays distinguishable.
            log.debug("trailers_disk_usage_parent_missing", path=str(expected_path.parent))
        except OSError as exc:
            # Permission denied, broken NTFS/macFUSE mount, stale handle, etc.
            log.warning(
                "trailers_disk_usage_unavailable",
                path=str(expected_path.parent),
                error=str(exc),
                error_type=type(exc).__name__,
            )
        if not disk_ok:
            self._record_outcome(
                item, key, TrailerOutcome("skipped_by_filter", item_result=("skipped", "skipped_by_filter")), counts
            )
            return None

        return expected_path

    def _resolve(self, item: Any, key: str, ctx: RunContext, counts: dict[str, int]) -> str | None:
        """Resolve the trailer URL, recording a terminal outcome on failure/miss.

        Args:
            item: The ScanItem to resolve a trailer for.
            key: Composite state key for the item.
            ctx: The per-run configuration snapshot.
            counts: Running counters dict, mutated in place.

        Returns:
            The resolved video URL to download, or ``None`` when the item was
            already fully handled (finder error, circuit-open, or no trailer
            found) and the loop should advance to the next item.
        """
        assert self._finder is not None  # run() raises before the loop when None
        try:
            tmdb_id_int: int | None = int(item.tmdb_id) if item.tmdb_id else None
            url = self._finder.find(
                tmdb_id_int,  # type: ignore[arg-type]
                MediaType.from_legacy(item.media_type),
                title=item.title,
                year=item.year,
                season_number=item.season_number,
            )
        except Exception as exc:  # noqa: BLE001
            # I2: circuit-breaker open is a distinct failure mode from a generic
            # finder error — its own counter lets operators distinguish a tripped
            # TMDB/YouTube circuit from a real error. Both persist an HTTP_ERROR
            # state with a retry cooldown; only circuit-open appends an
            # item_results entry (the generic-error branch appends none).
            is_circuit_open = isinstance(exc, CircuitOpenError)
            if is_circuit_open:
                log.warning(
                    "trailers_finder_circuit_open",
                    key=key,
                    title=item.title,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            else:
                log.error(
                    "trailers_finder_error",
                    key=key,
                    title=item.title,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )
            self._record_outcome(
                item,
                key,
                TrailerOutcome(
                    counts_key="circuit_open" if is_circuit_open else "error",
                    item_result=("error", "circuit_open") if is_circuit_open else None,
                    failed_item=(key, "circuit_open" if is_circuit_open else "error", str(exc)),
                    state=build_retry_state(
                        TrailerStatus.HTTP_ERROR,
                        media_path=str(item.path),
                        season_number=item.season_number,
                        retry_policy=ctx.retry_policy,
                        notes=str(exc),
                    ),
                ),
                counts,
            )
            return None

        if url is not None:
            return url

        log.info("trailers_no_trailer_found", key=key, title=item.title)
        self._record_outcome(
            item,
            key,
            TrailerOutcome(
                counts_key="no_trailer",
                item_result=("no_trailer", "no_trailer"),
                failed_item=(key, "no_trailer", ""),
                state=build_retry_state(
                    TrailerStatus.NO_TRAILER_AVAILABLE,
                    media_path=str(item.path),
                    season_number=item.season_number,
                    retry_policy=ctx.retry_policy,
                ),
            ),
            counts,
        )
        return None

    def _download_and_record(
        self, item: Any, key: str, expected_path: Path, url: str, ctx: RunContext, counts: dict[str, int]
    ) -> None:
        """Race-recheck, download (with same-run fallback), then record the result.

        Args:
            item: The ScanItem being downloaded.
            key: Composite state key for the item.
            expected_path: The Plex-conformant trailer placement path.
            url: The resolved video URL to download.
            ctx: The per-run configuration snapshot.
            counts: Running counters dict, mutated in place.
        """
        # SOT recheck immediately before download (race guard): the trailer may
        # have appeared between _select and now (e.g. another process placed it
        # while find() was running).
        if trailer_exists(expected_path, ctx.min_size):
            log.debug("trailers_already_present", key=key, title=item.title)
            self._record_outcome(
                item, key, TrailerOutcome("already_present", item_result=("already_present", "already_present")), counts
            )
            return

        tried: set[str] = {url}
        result = self._downloader.download(url, expected_path)

        # Same-run YouTube-search fallback (feat/trailer-fallback). Fires when the
        # first download fails AND the fallback is enabled. Re-downloads at most
        # once. A tripped YouTube breaker degrades to no-fallback inside the helper
        # (it returns None). BOT_DETECTED is excluded: re-downloading immediately
        # would reset bot_detected_consecutive_attempts incorrectly.
        if result.status not in (DownloadStatus.SUCCESS, DownloadStatus.BOT_DETECTED) and ctx.fallback_yt_search:
            alt = youtube_search_fallback(self._finder, item)
            if alt and alt not in tried:
                tried.add(alt)
                url = alt  # state/NFO/events record the URL actually used
                result = self._downloader.download(url, expected_path)

        if result.status == DownloadStatus.SUCCESS:
            self._record_success(item, key, url, result, counts)
        elif result.status == DownloadStatus.BOT_DETECTED:
            log.warning("trailers_bot_detected", key=key, title=item.title, url=url)
            self._record_outcome(
                item,
                key,
                TrailerOutcome(
                    counts_key="bot_detected",
                    item_result=("bot_detected", "bot_detected"),
                    failed_item=(key, "bot_detected", result.error_message or ""),
                    # BOT_DETECTED writes no next_retry_at cooldown (always retried)
                    # but carries the consecutive-attempt counter, so it is built
                    # inline rather than via build_retry_state.
                    state=TrailerState(
                        last_attempt=datetime.now(timezone.utc).isoformat(),
                        attempts=1,
                        status=TrailerStatus.BOT_DETECTED,
                        media_path=str(item.path),
                        youtube_url=url,
                        notes=result.error_message,
                        bot_detected_consecutive_attempts=1,
                        season_number=item.season_number,
                    ),
                ),
                counts,
            )
        elif result.status == DownloadStatus.HTTP_ERROR:
            log.warning("trailers_http_error", key=key, title=item.title, url=url)
            self._record_outcome(
                item,
                key,
                TrailerOutcome(
                    counts_key="http_error",
                    item_result=("error", "http_error"),
                    failed_item=(key, "http_error", result.error_message or ""),
                    state=build_retry_state(
                        TrailerStatus.HTTP_ERROR,
                        media_path=str(item.path),
                        season_number=item.season_number,
                        retry_policy=ctx.retry_policy,
                        youtube_url=url,
                        notes=result.error_message,
                    ),
                ),
                counts,
            )
        else:
            log.warning("trailers_ytdlp_error", key=key, title=item.title, url=url)
            self._record_outcome(
                item,
                key,
                TrailerOutcome(
                    counts_key="ytdlp_error",
                    item_result=("error", "ytdlp_error"),
                    failed_item=(key, "ytdlp_error", result.error_message or ""),
                    state=build_retry_state(
                        TrailerStatus.YTDLP_ERROR,
                        media_path=str(item.path),
                        season_number=item.season_number,
                        retry_policy=ctx.retry_policy,
                        youtube_url=url,
                        notes=result.error_message,
                    ),
                ),
                counts,
            )

    def _record_success(self, item: Any, key: str, url: str, result: Any, counts: dict[str, int]) -> None:
        """Record a successful download: counts, ledger clear, outbox, NFO, bus emit.

        Args:
            item: The ScanItem that was downloaded.
            key: Composite state key for the item.
            url: The resolved video URL actually used for the download.
            result: The successful ``DownloadResult`` (its ``output_path`` gates
                the outbox publish and the bus emit).
            counts: Running counters dict, mutated in place.
        """
        log.info(
            "trailers_downloaded",
            key=key,
            title=item.title,
            url=url,
            output_path=str(result.output_path),
        )
        # Single-truth (P6.4): success records NO presence claim; it clears any
        # prior ledger entry. Presence is the filesystem's truth (constitution
        # P26), surfaced through the derived ``trailer_found`` index below.
        self._record_outcome(
            item, key, TrailerOutcome("downloaded", item_result=("downloaded", "downloaded"), clear_state=True), counts
        )

        # Best-effort outbox publish for the indexer (DESIGN §9.1).
        if result.output_path is not None:
            _db_path = self._config.indexer.db_path
            resolved = disk_id_for_path(result.output_path, _db_path)
            if resolved is not None:
                disk_id, rel_path = resolved
                publish_event(
                    disk_id,
                    op="trailer_download",
                    payload={"rel_path": rel_path, "trailer_path": str(result.output_path)},
                    db_path=_db_path,
                    source="trailers",
                )

        # Propagate the trailer URL into the NFO <trailer> tag so Plex / Kodi can
        # display the remote trailer as a fallback. Silently skip when no NFO.
        if item.nfo_path is not None:
            nfo_ok = write_trailer_url_to_nfo(item.nfo_path, url)
            if not nfo_ok:
                log.warning(
                    "placement.nfo_update_failed",
                    key=key,
                    title=item.title,
                    nfo_path=str(item.nfo_path),
                )

        # Bus emit (Sub-phase 4.4) — fires only on a real output path. ``source_url``
        # is the resolved YouTube video URL passed to YtdlpDownloader.download.
        if result.output_path is not None:
            self._event_bus.emit(
                TrailerDownloaded(
                    source="trailers.orchestrator",
                    media_path=item.path,
                    trailer_path=result.output_path,
                    source_url=url,
                ),
            )

    def _record_outcome(self, item: Any, key: str, outcome: TrailerOutcome, counts: dict[str, int]) -> None:
        """Apply a :class:`TrailerOutcome`'s bookkeeping effects for one item.

        The single collapse of the per-branch repetition the outcome ladder
        previously inlined: increments the outcome's counter, appends the
        ``(status, reason)`` to ``item_results`` (path-prefixed) when present,
        appends the ``failed_items`` tuple when present, and either clears the
        ledger entry or writes the terminal state.

        Args:
            item: The ScanItem being recorded (supplies path + title).
            key: Composite state key for the item.
            outcome: The declarative outcome to apply.
            counts: Running counters dict, mutated in place.
        """
        counts[outcome.counts_key] += 1
        if outcome.item_result is not None:
            status, reason = outcome.item_result
            self._item_results.append((str(item.path), status, reason))
        if outcome.failed_item is not None:
            self._failed_items.append(outcome.failed_item)
        if outcome.clear_state:
            _clear_state_for_item(self._state_store, key, item.title)
        elif outcome.state is not None:
            _set_state_for_item(self._state_store, key, outcome.state, counts, item.title)

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

        Uses ``self._registry`` (threaded from :class:`AppContext` —
        feat/registry §5.2) to resolve the ``VideoProvider`` capability.
        Wires the YouTube circuit breaker from
        ``config.trailers.circuit_breakers``, the YouTube quota cache
        (sidecar ``JsonTTLCache``), and the YouTube API key from
        ``YOUTUBE_API_KEY`` env. Returns None only on import-time failure
        (developer error); other misconfigurations log loudly with
        exc_info so users see them.

        Returns:
            A TrailerFinder instance, or None when import fails.
        """
        try:
            from personalscraper.config import get_settings  # noqa: PLC0415
            from personalscraper.core.circuit import CircuitBreaker  # noqa: PLC0415
            from personalscraper.core.json_ttl_cache import JsonTTLCache  # noqa: PLC0415
            from personalscraper.trailers.discovery.trailer_finder import TrailerFinder  # noqa: PLC0415
            from personalscraper.trailers.discovery.trailers_cache import TrailersCache  # noqa: PLC0415
            from personalscraper.trailers.discovery.youtube_search import (  # noqa: PLC0415
                YoutubeSearch,
                youtube_api_key_from_env,
            )
        except ImportError as exc:
            log.error("trailers_finder_import_failed", error=str(exc), exc_info=True)
            return None

        try:
            settings = get_settings()
            cache_dir = Path(str(self._config.trailers.state_file)).parent
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache = TrailersCache(cache_dir / "trailers_cache.json")

            # Registry comes from AppContext via the constructor (sub-phase
            # 3.1 made it required and removed the transitional inline
            # construction).
            registry = self._registry

            cb_cfg = self._config.trailers.circuit_breakers
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
                registry=registry,
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
        import json as _json  # noqa: PLC0415

        for db_item, _disk, dispatch_path in rows:
            if not dispatch_path:
                continue
            entry = _LibraryEntry(path=dispatch_path)
            # Migration 005 : IDs now live in ``external_ids_json``.
            try:
                external_ids = _json.loads(db_item.external_ids_json or "{}")
            except _json.JSONDecodeError:
                external_ids = {}
            tmdb_series_id = external_ids.get("tmdb", {}).get("series_id")
            imdb_series_id = external_ids.get("imdb", {}).get("series_id")
            if tmdb_series_id:
                index[(db_item.category_id, str(tmdb_series_id))] = entry
            if imdb_series_id:
                index[(db_item.category_id, imdb_series_id)] = entry
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
