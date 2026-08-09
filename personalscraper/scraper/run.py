"""Scrape step runner: entry point for the scrape pipeline step.

Instantiates API clients, creates the Scraper orchestrator, and
processes movies and TV shows. Converts ScrapeResult list to StepReport
for the pipeline framework.

Lock is acquired at the CLI level, not here.
"""

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus, current_run_uid
from personalscraper.core.media_types import VIDEO_EXTENSIONS, FileType
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.naming_patterns import PATTERNS, SEASON_DIR_RE
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.reports.scrape import ScrapeDetails
from personalscraper.scraper.scraper import Scraper, ScrapeResult, verify_tvshow_scrape_drift

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.acquire.store import ConcreteAcquireStore
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.core.identity import MediaRef

log = get_logger("run")


def lookup_ref_for_folder(prov_index: "dict[str, MediaRef]", folder: Path) -> "MediaRef | None":
    """Resolve the provenance seed for a media folder, tolerating a deeper path.

    The index is keyed on ``current_path``, which the sorter now records as the
    media folder — but rows written before that, or by any producer that tracked
    the file rather than its folder, sit one level deeper. An exact lookup alone
    silently misses those and the scrape free-matches by title, which is how a
    single-file movie whose TMDB id was known since the grab ended up ambiguous
    across 27 candidates (« The Odyssey », 2026-08-06).

    So: exact match first, then any indexed path that lives UNDER ``folder``. The
    fallback is deliberately not a prefix-string test — it compares path parts,
    so ``…/The Odyssey (2026)`` never swallows ``…/The Odyssey (2026) Remastered``.
    Unicode forms are normalised (macFUSE yields NFD, the DB stores NFC).

    Args:
        prov_index: The ``{current_path: MediaRef}`` snapshot.
        folder: The media folder the scrape is about to identify.

    Returns:
        The seed :class:`MediaRef`, or ``None`` on a genuine miss.
    """
    import unicodedata  # noqa: PLC0415 — stdlib, only needed on this path

    def _norm(text: str) -> str:
        return unicodedata.normalize("NFC", text)

    target = _norm(str(folder))
    exact = prov_index.get(str(folder)) or prov_index.get(target)
    if exact is not None:
        return exact
    target_parts = Path(target).parts
    for raw_path, ref in prov_index.items():
        candidate_parts = Path(_norm(raw_path)).parts
        if len(candidate_parts) > len(target_parts) and candidate_parts[: len(target_parts)] == target_parts:
            return ref
    return None


def _has_unscraped_items(settings: Settings, config: Config) -> bool:
    """Check if any media folder needs scraping or artwork recovery.

    Returns True if at least one folder has:
    - No valid NFO (needs full scrape), OR
    - Valid NFO but missing essential artwork — poster or landscape
      (needs artwork recovery)

    Uses _parse_folder_name for consistent title extraction,
    matching the same parsing logic as Scraper.scrape_movie/scrape_tvshow.

    Args:
        settings: Pipeline configuration (API keys and thresholds).
        config: Application config for staging path and dir name resolution.

    Returns:
        True if at least one folder needs work.
    """
    from personalscraper.scraper.scraper import _parse_folder_name

    movies_dir_name = folder_name(find_by_file_type(config, FileType.MOVIE))
    tvshows_dir_name = folder_name(find_by_file_type(config, FileType.TVSHOW))
    staging = config.paths.staging_dir
    for dir_name in (movies_dir_name, tvshows_dir_name):
        cat_dir = staging / dir_name
        if not cat_dir.exists():
            continue
        for folder in cat_dir.iterdir():
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            if dir_name == movies_dir_name:
                title, _ = _parse_folder_name(folder.name)
                nfo_name = PATTERNS.format("movie_nfo", Title=title)
                nfo_path = folder / nfo_name
                if not _is_nfo_complete(nfo_path):
                    return True
                # Check essential artwork (poster + landscape)
                poster = PATTERNS.format("movie_poster", Title=title)
                if not (folder / poster).exists():
                    return True
                landscape = PATTERNS.format("movie_landscape", Title=title)
                if not (folder / landscape).exists():
                    return True
            else:
                nfo_path = folder / PATTERNS.tvshow_nfo
                if not _is_nfo_complete(nfo_path):
                    return True
                # Drift check: even with a complete NFO + both artworks,
                # re-scraping is required when the folder or episodes no
                # longer match what the current scraper would produce
                # (folder rename policy, legacy title-less episodes,
                # missing episode NFOs).
                is_valid, reason = verify_tvshow_scrape_drift(folder, nfo_path, PATTERNS)
                if not is_valid:
                    log.info("show_rescrape_drift_detected", directory=folder.name, reason=reason)
                    return True
    return False


def _needs_repair(category_dir: Path, file_type: FileType) -> bool:
    """Check if any item in category needs repair beyond NFO/artwork.

    Quick filesystem-only check (no API calls). Returns True if any
    item has unorganized episodes, residual NFOs, or root-level MKV
    duplicates.

    Args:
        category_dir: Path to the movies or TV shows staging directory.
        file_type: FileType.MOVIE or FileType.TVSHOW — determines which
            checks to apply. Passed explicitly by callers to avoid
            substring heuristics on directory names.

    Returns:
        True if at least one item needs repair.
    """
    if not category_dir.exists():
        return False

    is_movies = file_type == FileType.MOVIE

    for folder in category_dir.iterdir():
        if not folder.is_dir() or folder.name.startswith("."):
            continue

        if is_movies:
            # Detect duplicate NFOs (e.g. clean + raw release-group NFO)
            nfo_count = sum(1 for f in folder.iterdir() if f.suffix.lower() == ".nfo")
            if nfo_count > 1:
                return True
        else:
            # TV show checks
            has_season_dirs = any(d.is_dir() and SEASON_DIR_RE.match(d.name) for d in folder.iterdir())

            for item in folder.iterdir():
                # Root-level video when season dirs exist → misplaced episode
                if has_season_dirs and item.is_file() and item.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS:
                    return True

                # Any non-season, non-hidden subdir is a residual torrent dir
                # (may contain videos, NFO residuals, or be empty)
                if item.is_dir() and not item.name.startswith(".") and not SEASON_DIR_RE.match(item.name):
                    return True

            # Residual episode NFOs at root (tvshow.nfo is expected)
            root_nfos = [
                f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".nfo" and f.name != "tvshow.nfo"
            ]
            if root_nfos:
                return True

    return False


def _build_follow_tvdb_resolver(config: Config) -> "Callable[[Path], int | None] | None":
    """Build the scrape-follow-id provenance resolver from the acquire queue.

    Reads the grabbed wanted snapshot + follow titles ONCE (they stay ``grabbed``
    for the whole scrape step — the reconcile runs post-dispatch) and closes over
    them, so each show dir is resolved in-memory without re-opening the store.

    Args:
        config: The loaded config (its ``acquire`` sub-config locates the store).

    Returns:
        A ``show_dir -> tvdb_id | None`` callable, or ``None`` (free match) when
        nothing is grabbed or the store cannot be read (fail-soft, never blocks).
    """
    from personalscraper.acquire.store import build_acquire_store  # noqa: PLC0415
    from personalscraper.scraper.follow_provenance import resolve_followed_tvdb  # noqa: PLC0415

    # Only touch the acquire store when it is configured with a real path — guards
    # against a non-configured/mock acquire config (opening it would create a
    # spurious DB file). In production db_path is always a real Path.
    db_path = getattr(config.acquire, "db_path", None)
    if not isinstance(db_path, (str, Path)):
        return None

    try:
        store = build_acquire_store(config.acquire)
        try:
            grabbed = store.wanted.list_grabbed()
            follow_titles = {f.id: f.title for f in store.follow.list_all() if f.id is not None}
            follow_years = _read_follow_years(db_path)
            # Provenance (#30): {current_path: media_ref} snapshot — the DETERMINISTIC
            # identity seed recorded at grab, kept live through sort. Read once here,
            # like the #29 grabbed snapshot below it.
            prov_index = store.provenance.path_ref_index()
        finally:
            store.close()
    except Exception as exc:  # noqa: BLE001 — fail-soft: free match if store unavailable
        log.warning("scrape_follow_resolver_build_failed", error=str(exc))
        return None

    if not grabbed and not prov_index:
        return None

    def _resolver(show_dir: Path) -> int | None:
        # Provenance FIRST — a deterministic hash→folder→identity link beats the
        # title/episode inference. Only its tvdb feeds the tvshow forced path here;
        # a provenance miss (or a tmdb-only movie ref) falls through to #29.
        ref = lookup_ref_for_folder(prov_index, show_dir)
        if ref is not None and ref.tvdb_id is not None:
            return ref.tvdb_id
        return resolve_followed_tvdb(show_dir, grabbed, follow_titles, follow_years)

    return _resolver


def _build_provenance_movie_resolver(config: Config) -> "Callable[[Path], int | None] | None":
    """Build the MOVIE scrape-identity resolver from the provenance registry (#30 / ACC-05).

    Movies have no #29 episode-inference fallback (that is TV-only), so this is a
    pure provenance lookup: ``movie_dir -> tmdb_id`` recorded at grab, kept live
    through sort. ``None`` when nothing is tracked or the store cannot be read
    (fail-soft → the scrape free-matches by title+year exactly as today).
    """
    from personalscraper.acquire.store import build_acquire_store  # noqa: PLC0415

    db_path = getattr(config.acquire, "db_path", None)
    if not isinstance(db_path, (str, Path)):
        return None
    try:
        store = build_acquire_store(config.acquire)
        try:
            prov_index = store.provenance.path_ref_index()
        finally:
            store.close()
    except Exception as exc:  # noqa: BLE001 — fail-soft: free match if store unavailable
        log.warning("scrape_movie_provenance_build_failed", error=str(exc))
        return None

    if not prov_index:
        return None

    def _resolver(movie_dir: Path) -> int | None:
        ref = lookup_ref_for_folder(prov_index, movie_dir)
        return ref.tmdb_id if (ref is not None and ref.tmdb_id is not None) else None

    return _resolver


def _open_provenance_store(config: Config) -> "ConcreteAcquireStore | None":
    """Open a LIVE acquire store for provenance writes during the scrape (fail-soft).

    Unlike the resolver builders (which read a snapshot and close), the scrape needs
    a store held open so ``move_path`` can keep ``current_path`` live as each folder
    is renamed to its canonical name (review A/B). ``None`` when the store is not
    configured or cannot be opened — the scrape then simply records no rename move.
    The caller MUST ``close()`` it.
    """
    from personalscraper.acquire.store import build_acquire_store  # noqa: PLC0415

    db_path = getattr(config.acquire, "db_path", None)
    if not isinstance(db_path, (str, Path)):
        return None
    try:
        return build_acquire_store(config.acquire)
    except Exception as exc:  # noqa: BLE001 — fail-soft: no rename tracking if unavailable
        log.warning("scrape_provenance_store_open_failed", error=str(exc))
        return None


def _read_follow_years(db_path: "str | Path") -> dict[int, int | None]:
    """Read ``followed_id -> year`` from the acquire DB (year guard input).

    Fail-soft: any error (missing column on an un-migrated DB, unreadable file)
    yields an empty map, which simply disables the year guard.
    """
    import sqlite3  # noqa: PLC0415

    from personalscraper.core.sqlite._pragmas import apply_pragmas  # noqa: PLC0415

    years: dict[int, int | None] = {}
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            apply_pragmas(conn)
            for row in conn.execute("SELECT id, year FROM followed_series"):
                years[int(row[0])] = int(row[1]) if row[1] is not None else None
        finally:
            conn.close()
    except sqlite3.Error as exc:
        log.debug("scrape_follow_years_read_failed", error=str(exc))
    return years


def run_scrape(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
    interactive: bool = False,
    movies_only: bool = False,
    tvshows_only: bool = False,
    *,
    event_bus: EventBus,
    registry: "ProviderRegistry",
) -> StepReport:
    """Run the scrape pipeline step.

    Instantiates the Scraper orchestrator using the registry injected at
    pipeline boot (sub-phase 1.1) and processes movies and/or TV shows
    from the staging directory. Provider clients (TMDB / TVDB) are owned
    by the registry — this function no longer constructs them.

    Args:
        settings: Pipeline configuration with API keys and thresholds.
        config: Config for staging path, dir name resolution, and
            classifier-based categorisation. Each scraped item is
            classified and ``ScrapeResult.category_id`` is set.
            Items with no matching category are skipped.
        dry_run: If True, preview operations without writing files.
        interactive: If True, prompt user for ambiguous matches.
        movies_only: If True, process only {movies_dir}/.
        tvshows_only: If True, process only {tvshows_dir}/.
        event_bus: Required in-process EventBus. Each per-item
            lifecycle transition emits an ``ItemProgressed`` event on the bus.
        registry: Required :class:`ProviderRegistry` from the pipeline boot
            sequence. Owns provider instantiation and exposes capability-
            keyed access (DESIGN §6.1 / §6.2).

    Returns:
        StepReport with success/skip/error counts and details.
    """
    staging = config.paths.staging_dir
    movies_dir_name = folder_name(find_by_file_type(config, FileType.MOVIE))
    tvshows_dir_name = folder_name(find_by_file_type(config, FileType.TVSHOW))

    # Fast-skip: nothing to scrape and no structural repairs needed
    try:
        needs_movie_repair = _needs_repair(staging / movies_dir_name, FileType.MOVIE)
    except OSError as exc:
        log.warning("scrape_repair_check_failed", category="movies", error=str(exc))
        needs_movie_repair = True
    try:
        needs_tvshow_repair = _needs_repair(staging / tvshows_dir_name, FileType.TVSHOW)
    except OSError as exc:
        log.warning("scrape_repair_check_failed", category="tvshows", error=str(exc))
        needs_tvshow_repair = True
    if not _has_unscraped_items(settings, config) and not needs_movie_repair and not needs_tvshow_repair:
        log.info("scrape_fast_skip")
        return StepReport(name="scrape")

    # Live provenance store held open for the scrape: when a scrape renames a tracked
    # folder to its canonical name, the orchestrator calls provenance.move_path so
    # current_path stays live for the dispatch record (review A/B). Fail-soft.
    prov_store = _open_provenance_store(config)
    scraper = Scraper(
        settings=settings,
        patterns=PATTERNS,
        dry_run=dry_run,
        interactive=interactive,
        config=config,
        event_bus=event_bus,
        registry=registry,
        # scrape-follow-id: force the followed series' TVDB id (anti-split) when a
        # staging show came from the wanted queue. None ⇒ free match (unchanged).
        follow_tvdb_resolver=_build_follow_tvdb_resolver(config),
        # #30 / ACC-05: force a followed MOVIE's TMDB id from the provenance registry.
        follow_movie_resolver=_build_provenance_movie_resolver(config),
        provenance=prov_store.provenance if prov_store is not None else None,
        # F3 run-linkage: stamp the scraping run onto each item's provenance row.
        run_uid=current_run_uid(),
    )

    all_results: list[ScrapeResult] = []

    try:
        # Process movies
        if not tvshows_only:
            movies_dir = staging / movies_dir_name
            if movies_dir.exists():
                all_results.extend(scraper.process_movies(movies_dir))

        # Process TV shows
        if not movies_only:
            tvshows_dir = staging / tvshows_dir_name
            if tvshows_dir.exists():
                all_results.extend(scraper.process_tvshows(tvshows_dir))
    finally:
        if prov_store is not None:
            prov_store.close()

    # Emit per-folder progress events
    for r in all_results:
        item_name = r.media_path.name
        event_bus.emit(ItemProgressed(step="scrape", item=item_name, status="started"))
        if _is_enqueued(r):
            # Every item that lands in the scrape-arbiter decision queue emits
            # a single ``queued_for_decision`` event, whatever its action
            # (``queued_for_decision`` for mid_band/ambiguous, or the additive
            # ``skipped_low_confidence`` for below_threshold). The WS badge and
            # the DESIGN §4 "emitted per enqueued item" contract both key on
            # this status — a below_threshold item must surface it too (F16).
            event_bus.emit(
                ItemProgressed(
                    step="scrape",
                    item=item_name,
                    status="queued_for_decision",
                    details={
                        "trigger": r.decision_trigger or "",
                        "confidence": r.match.confidence if r.match else 0.0,
                        "candidates_count": len(r.decision_candidates or []),
                    },
                )
            )
        elif r.action in ("scraped", "artwork_recovered"):
            event_bus.emit(
                ItemProgressed(
                    step="scrape",
                    item=item_name,
                    status="matched",
                    details={
                        "action": r.action,
                        "provider": r.match.source if r.match else "",
                        "confidence": r.match.confidence if r.match else 0.0,
                    },
                )
            )
        elif r.action == "skipped_low_confidence":
            # Not enqueued (defensive — after F11 every below_threshold item is
            # enqueued): a genuine unmatched skip with no decision row.
            event_bus.emit(
                ItemProgressed(
                    step="scrape",
                    item=item_name,
                    status="skipped_low_confidence",
                    details={
                        "provider": r.match.source if r.match else "",
                        "confidence": r.match.confidence if r.match else 0.0,
                    },
                )
            )
        elif r.action in ("skipped_already_done", "skipped_no_category"):
            event_bus.emit(
                ItemProgressed(
                    step="scrape",
                    item=item_name,
                    status="skipped",
                    details={"action": r.action},
                )
            )
        elif r.action == "error":
            event_bus.emit(
                ItemProgressed(
                    step="scrape",
                    item=item_name,
                    status="failed",
                    details={"error": r.error or ""},
                )
            )

    # Enqueue ambiguous / mid-band / below-threshold items into the
    # scrape-arbiter decision queue so the operator can later resolve them
    # through the web UI (§5).  The DecisionWriter is fail-soft — a DB
    # failure never aborts the pipeline.
    #
    # dry-run must NOT touch the DB (F47/F51): a preview classifies items
    # identically but the standing operator rule is "always --dry-run first",
    # so persisting rows / flipping pending→superseded during a preview would
    # mutate durable state before the operator approved the real run.
    db_path = config.indexer.db_path
    if dry_run:
        log.debug("scrape_arbiter_skip_dry_run", reason="dry-run does not mutate the decision queue")
    elif not isinstance(db_path, Path):
        log.debug("scrape_arbiter_skip_no_db", reason="indexer.db_path is not a Path")
    else:
        from personalscraper.core.event_bus import current_correlation_id
        from personalscraper.scraper.decision_writer import DecisionWriter
        from personalscraper.scraper.scraper import _parse_folder_name

        # Correlate every enqueued/refreshed row with the run that produced it
        # (DESIGN §3 run_uid contract, F08/F15). The pipeline binds the
        # correlation ContextVar to str(run_id); the row stores the hex form
        # to match ``pipeline_run.run_uid``.
        run_uid: str | None = None
        _corr = current_correlation_id.get()
        if _corr:
            try:
                run_uid = UUID(str(_corr)).hex
            except (ValueError, TypeError):
                run_uid = None

        writer = DecisionWriter(db_path)
        # F2 (decisions-spine): mirror each 'awaiting' verdict onto the provenance spine
        # so the acquisition timeline shows the item needs resolution. ADVISORY — a fresh
        # store (the scrape's prov_store is already closed above), path-keyed on
        # current_path, a no-op on an untracked manual item. Best-effort: a failure here
        # never affects the authoritative DecisionWriter.upsert.
        prov_resolution = _open_provenance_store(config)
        try:
            for r in all_results:
                if _is_enqueued(r):
                    title, year = _parse_folder_name(r.media_path.name)
                    candidates_json = (
                        json.dumps([c.model_dump() for c in r.decision_candidates]) if r.decision_candidates else "[]"
                    )
                    decision_id = writer.upsert(
                        staging_path=r.media_path,
                        media_kind=r.media_type,
                        extracted_title=title,
                        extracted_year=year,
                        trigger=r.decision_trigger or "mid_band",
                        candidates_json=candidates_json,
                        run_uid=run_uid,
                    )
                    if prov_resolution is not None:
                        prov_resolution.provenance.set_resolution(
                            str(r.media_path),
                            state="awaiting",
                            resolved_at=int(time.time()),
                            decision_id=decision_id,
                            trigger=r.decision_trigger or "mid_band",
                        )
            writer.mark_superseded_orphans()
        finally:
            if prov_resolution is not None:
                prov_resolution.close()

    # Convert to StepReport
    return _build_scrape_report(all_results)


def _is_enqueued(r: ScrapeResult) -> bool:
    """Return ``True`` when *r* must be written to the scrape-arbiter queue.

    A result is enqueued iff a decision trigger was assigned (``below_threshold``
    / ``mid_band`` / ``ambiguous``) and the item was not recovered from the
    local DB.  This is the single source of truth shared by the per-item event
    emission, the ``DecisionWriter.upsert`` loop, and the ``StepReport`` count,
    so a below-threshold item with zero candidates (F11) is enqueued while a
    ``restored_from_db`` item (F10) is not.

    Args:
        r: The scrape result to classify.

    Returns:
        ``True`` when the item belongs in the decision queue.
    """
    return r.decision_trigger is not None and r.action != "restored_from_db"


def _build_scrape_report(results: list[ScrapeResult]) -> StepReport:
    """Build a StepReport from a list of ScrapeResult (scrape finalizer).

    Scrape's per-item ``ItemProgressed`` events are emitted separately in
    ``run_scrape`` (the enqueued/action partition differs from the counter
    partition below — a below-threshold item emits ``queued_for_decision`` yet
    counts as a skip+unmatched), so the report is built by direct construction
    rather than through the shared ``record`` reporter.

    Items with action ``skipped_low_confidence`` are counted separately
    in ``counts["unmatched"]`` so the caller can distinguish between
    intentional skips (already done, no category) and silent match
    failures that may indicate a scraper problem.

    Args:
        results: List of scrape results.

    Returns:
        StepReport with aggregated counts, details, and an ``unmatched``
        entry in ``counts`` when at least one item had no confident match.
    """
    success = 0
    skipped = 0
    unmatched = 0
    errors = 0
    warnings: list[str] = []
    details: list[str] = []
    unmatched_paths: list[str] = []
    # Typed-payload accumulators (STEP_REPORT_CONTRACT: ScrapeDetails).
    payload = ScrapeDetails()

    for r in results:
        name = r.media_path.name
        if r.action == "scraped":
            success += 1
            payload.scraped.append(name)
            parts = [f"[scraped] {name}"]
            if r.nfo_written:
                parts.append("NFO")
            if r.artwork_downloaded:
                parts.append(f"{len(r.artwork_downloaded)} artwork")
            if r.episodes_renamed > 0:
                parts.append(f"{r.episodes_renamed} episodes")
            details.append(" | ".join(parts))
        elif r.action == "artwork_recovered":
            success += 1
            payload.scraped.append(name)
            parts = [f"[recovered] {name}"]
            if r.artwork_downloaded:
                parts.append(f"{len(r.artwork_downloaded)} artwork")
            details.append(" | ".join(parts))
        elif r.action == "repaired":
            success += 1
            payload.scraped.append(name)
            details.append(f"[repaired] {name}")
        elif r.action == "skipped_low_confidence":
            # Counted as both skipped (for backward compat) and unmatched
            # (distinct observable counter for diagnosis).
            skipped += 1
            unmatched += 1
            payload.skipped_low_confidence.append(name)
            details.append(f"[unmatched] {name}")
            unmatched_paths.append(name)
        elif r.action == "queued_for_decision":
            details.append(f"[queued_for_decision] {name}")
            unmatched_paths.append(name)
        elif r.action == "skipped_already_done":
            skipped += 1
            payload.existing_validated.append(name)
            details.append(f"[skipped] {name} ({r.action})")
        elif r.action.startswith("skipped"):
            skipped += 1
            details.append(f"[skipped] {name} ({r.action})")
        elif r.action == "error":
            errors += 1
            payload.failed.append((name, r.error or ""))
            details.append(f"[error] {name}: {r.error}")
            warnings.append(f"{name}: {r.error}")

    payload.unmatched_paths = list(unmatched_paths)

    counts: dict[str, int] = {}
    if unmatched:
        counts["unmatched"] = unmatched
    # Count all items enqueued for operator decision — the same predicate the
    # enqueue loop uses (``_is_enqueued``): mid_band/ambiguous items plus the
    # additive below_threshold tier, excluding restored-from-DB items.
    queued = sum(1 for r in results if _is_enqueued(r))
    if queued:
        counts["queued_for_decision"] = queued

    return StepReport(
        name="scrape",
        success_count=success,
        skip_count=skipped,
        error_count=errors,
        warnings=warnings,
        details=details,
        counts=counts,
        unmatched_paths=unmatched_paths,
        details_payload=payload,  # type: ignore[arg-type]  # coerced to dict via StepReport.__post_init__
    )
