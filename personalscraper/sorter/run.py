"""Sort step entry point — run_sort() function.

Coordinates NameCleaner and Sorter to sort all items from the ingest
directory ({ingest_dir}/) into categorized subdirectories under the staging
root. Returns a StepReport for the pipeline.
The lock is managed by the CLI caller, not by this module.

staging_dir and ingest_dir come from Config.paths. Functions accept an
explicit ``staging_dir`` parameter; when config is provided, ingest_dir is
resolved via staging_path(config, find_ingest_dir(config)).
"""

from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_ingest_dir, staging_path
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.core.tags import SEED_PURE
from personalscraper.logger import get_logger
from personalscraper.models import SortResult, StepReport
from personalscraper.pipeline_protocol import record
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.sorter import Sorter

if TYPE_CHECKING:
    from personalscraper.api.torrent._contracts import TorrentLister

log = get_logger("sorter.run")


def run_sort(
    settings: Settings,
    staging_dir: Path,
    config: Config,
    dry_run: bool = False,
    *,
    event_bus: EventBus,
    torrent_client: "TorrentLister | None" = None,
) -> StepReport:
    """Sort all items from the ingest directory into type subdirectories.

    Instantiates NameCleaner and Sorter, processes the ingest directory
    (e.g. {ingest_dir}/) and sorts items into category subdirectories
    ({movies_dir}/, {tvshows_dir}/, etc.) under the staging root.

    Fast-skip: returns immediately if the ingest dir has no items to sort.

    Args:
        settings: Pipeline settings (retained for API compatibility; thresholds).
        staging_dir: Absolute path to the staging area (from Config.paths).
        config: Loaded Config instance (required) for staging_dirs and path resolution.
        dry_run: If True, simulate moves without actually moving.
        event_bus: Required in-process EventBus. Each per-item lifecycle
            transition emits an ``ItemProgressed`` event on the bus.
        torrent_client: Optional torrent client exposing ``get_completed()``
            (a :class:`TorrentLister`). Consulted only when
            ``config.sort.verify_seed_pure`` is True to build the set of
            seed-pure-tagged completed-torrent names that the sort genuinely
            excludes. ``None`` (or the flag off) leaves the guard inert — the
            sort proceeds with an empty skip set. The query is fail-soft: any
            client error logs a warning and keeps the skip set empty. Note: the
            standalone ``personalscraper sort`` command does NOT wire a client
            (the seed-pure sort guard is pipeline-only by design — DESIGN §4.2),
            so the flag has effect only on the full-pipeline path.

    Returns:
        StepReport with counts and per-item details.
    """
    ingest_dir = staging_path(config, find_ingest_dir(config))

    # Fast-skip: nothing to sort
    if not _has_unsorted_items(ingest_dir):
        log.info("sort_fast_skip", ingest_dir=str(ingest_dir))
        return StepReport(name="sort")

    cleaner = NameCleaner()
    sorter = Sorter(config=config, cleaner=cleaner, dry_run=dry_run)

    # Seed-pure sort guard (opt-in): genuinely exclude completed torrents tagged
    # seed-pure from the sort. Guarded by config.sort.verify_seed_pure and the
    # presence of a torrent client; fail-soft so the guard never aborts the sort.
    skip_names: frozenset[str] = frozenset()
    if getattr(config, "sort", None) is not None and config.sort.verify_seed_pure and torrent_client is not None:
        try:
            completed = torrent_client.get_completed()
            skip_names = frozenset(t.name for t in completed if SEED_PURE in t.tags)
            if skip_names:
                log.info("sort.seed_pure_guard_active", skipping=sorted(skip_names))
        except Exception as exc:  # noqa: BLE001 — guard must never abort the sort
            log.warning(
                "sort.seed_pure_guard_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                consequence=(
                    "sort proceeds with empty seed-pure skip set; ingest-skip remains the authoritative guardrail"
                ),
            )

    # Sort processes ingest_dir ({ingest_dir}/) → categorized dirs at staging root.
    # ``Sorter.process`` emits the per-item ``started`` events (F8) as it works.
    results = sorter.process(ingest_dir, dest_root=staging_dir, skip_names=skip_names, bus=event_bus)

    # Terminal per-item progress + report counters via the shared reporter.
    report = StepReport(name="sort")
    for r in results:
        _record_sort_terminal(report, event_bus, r)

    # After sort consumes files from the ingest dir, prune any
    # ``dest_path`` recorded inside that dir from the ingest tracker.
    # Without this, the tracker keeps a stale path forever and the
    # state-validator agent would flag every successful sort as a
    # phantom-tracker-entry false positive.
    if not dry_run and report.success_count:
        try:
            from personalscraper.ingest.tracker import IngestTracker  # noqa: PLC0415

            tracker = IngestTracker(config.paths.data_dir / "ingested_torrents.json")
            pruned = tracker.prune_consumed_dest_paths(ingest_dir)
            if pruned:
                log.info("sort_tracker_pruned", removed=pruned)
        except Exception as exc:  # noqa: BLE001 — tracker is best-effort
            log.warning("sort_tracker_prune_failed", error=str(exc))

    log.info(
        "sort_complete",
        moved=report.success_count,
        skipped=report.skip_count,
        errors=report.error_count,
    )
    return report


def _record_sort_terminal(report: StepReport, bus: EventBus, r: SortResult) -> None:
    """Record one sort result's terminal ``ItemProgressed`` + report counter.

    Preserves the exact counter/detail/warning + event-payload semantics of the
    former inline loop:

    * ``moved`` → ``success_count``; detail ``<name> -> <dest>``; event
      ``moved`` with ``{destination}``.
    * ``dry-run`` → ``success_count``; detail ``[DRY-RUN] <name> -> <dest>``;
      event ``moved`` with ``{destination, dry_run}``.
    * ``skipped`` → ``skip_count``; warning ``<name>: <message>`` only when a
      message is present (no detail); event ``skipped`` with ``{reason}``.
    * ``error`` → ``error_count``; warning ``ERROR <name>: <message>`` (no
      detail); event ``error`` with ``{error}``.

    Args:
        report: Sort step report mutated in place.
        bus: Required in-process EventBus.
        r: One sort result.
    """
    name = r.source.name
    if r.status == "moved":
        record(
            report,
            bus,
            step="sort",
            item=name,
            status="moved",
            detail=f"{name} -> {r.destination}",
            event_details={"destination": str(r.destination)},
        )
    elif r.status == "dry-run":
        record(
            report,
            bus,
            step="sort",
            item=name,
            status="moved",
            detail=f"[DRY-RUN] {name} -> {r.destination}",
            event_details={"destination": str(r.destination), "dry_run": True},
        )
    elif r.status == "skipped":
        record(
            report,
            bus,
            step="sort",
            item=name,
            status="skipped",
            warning=f"{name}: {r.message}" if r.message else None,
            event_details={"reason": r.message or ""},
        )
    elif r.status == "error":
        record(
            report,
            bus,
            step="sort",
            item=name,
            status="error",
            warning=f"ERROR {name}: {r.message}",
            event_details={"error": r.message or ""},
        )


def _has_unsorted_items(ingest_dir: Path) -> bool:
    """Check if the ingest directory contains non-hidden items to sort.

    Used for fast-skip: if nothing to sort, skip the entire phase.

    Args:
        ingest_dir: Resolved path to the ingest directory ({ingest_dir}/).

    Returns:
        True if there are items to sort.
    """
    if not ingest_dir.exists():
        return False
    return any(not item.name.startswith(".") for item in ingest_dir.iterdir())


def assert_temp_empty(settings: Settings, staging_dir: Path, config: Config) -> list[str]:
    """Check that the ingest directory is empty after sort.

    Ignores hidden files (.gitkeep, .DS_Store, etc.) since these
    are not unsorted media.

    Args:
        settings: Pipeline settings (retained for API compatibility; no longer used for path resolution).
        staging_dir: Absolute path to the staging area (from Config.paths).
        config: Loaded Config instance (required) for ingest_dir resolution.

    Returns:
        List of remaining file/dir names. Empty list means gate passes.
    """
    ingest_dir = staging_path(config, find_ingest_dir(config))
    if not ingest_dir.exists():
        return []
    remaining = [item.name for item in ingest_dir.iterdir() if not item.name.startswith(".")]
    if remaining:
        log.warning(
            "sort_ingest_not_empty",
            remaining_count=len(remaining),
        )
    return remaining
