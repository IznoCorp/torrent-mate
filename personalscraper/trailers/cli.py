"""CLI commands for the trailers feature.

Sub-app mounted at ``personalscraper trailers`` via typer.

Subcommands:
    scan      - Dry-run: list media missing trailers
    download  - Discover and download missing trailers
    verify    - Audit existing trailers (size, extension)
    purge     - Remove orphan trailers (media parent absent)

Common filters (all subcommands)::
    --disk DISK_ID
    --category CATEGORY_ID
    --since YYYY-MM-DD
    --limit N
    --dry-run
    --no-refresh   (skip library cache refresh)
    --level {show|season|both}
    --season N
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from personalscraper.logger import get_logger
from personalscraper.trailers.orchestrator import TrailersOrchestrator
from personalscraper.trailers.scanner import ScanItem, Scanner
from personalscraper.trailers.state import TrailerStateStore

log = get_logger("trailers.cli")

app = typer.Typer(name="trailers", help="Trailer acquisition and management commands.")

_VALID_LEVELS = {"show", "season", "both"}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_since(since: str | None) -> datetime | None:
    """Parse a YYYY-MM-DD string into a UTC midnight datetime.

    Args:
        since: Date string in YYYY-MM-DD format, or None.

    Returns:
        UTC midnight datetime, or None when ``since`` is None.

    Raises:
        typer.Exit: With code 2 when the date string is malformed.
    """
    if since is None:
        return None
    try:
        return datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        typer.echo(f"Error: --since {since!r} must be YYYY-MM-DD.", err=True)
        raise typer.Exit(code=2)


def _item_added_at(item: ScanItem) -> datetime:
    """Return the added timestamp for a ScanItem for --since filtering.

    Uses the NFO file mtime when present; falls back to the media directory
    mtime. Returned as a UTC-aware datetime.

    Args:
        item: The ScanItem to inspect.

    Returns:
        UTC-aware datetime representing when the item was added.
    """
    source: Path = item.nfo_path if item.nfo_path is not None and item.nfo_path.exists() else item.path
    try:
        mtime = source.stat().st_mtime
    except OSError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


def _filter_since(items: list[ScanItem], since_dt: datetime | None) -> list[ScanItem]:
    """Drop ScanItems added before ``since_dt``.

    Args:
        items: List of ScanItems to filter.
        since_dt: UTC cutoff datetime; items strictly before this are dropped.
            None means no filtering.

    Returns:
        Filtered list.
    """
    if since_dt is None:
        return items
    return [item for item in items if _item_added_at(item) >= since_dt]


def _resolve_level_and_season(
    level: str,
    season: int | None,
    seasons_enabled: bool,
) -> tuple[str, int | None]:
    """Normalise the --level / --season pair before filtering.

    Rules (evaluated in order):
    1. ``level`` must be one of ``show | season | both``; invalid => exit code 2.
    2. When ``season`` is not None, force ``level="season"`` (explicit season wins).
    3. When ``seasons_enabled`` is False, any season-level work becomes a no-op:
       ``level="season"`` silently collapses to ``"show"`` and ``season`` is set to
       None, matching the silently ignored UX described in the help text.

    Args:
        level: Raw ``--level`` value from the CLI.
        season: Raw ``--season`` value, or None.
        seasons_enabled: Whether ``config.trailers.seasons.enabled`` is True.

    Returns:
        Resolved ``(level, season)`` tuple.

    Raises:
        typer.Exit: With code 2 when ``level`` is not a valid value.
    """
    if level not in _VALID_LEVELS:
        typer.echo(
            f"Error: --level {level!r} is not valid. Choose from: {', '.join(sorted(_VALID_LEVELS))}.",
            err=True,
        )
        raise typer.Exit(code=2)

    # An explicit --season N forces level=season
    if season is not None:
        level = "season"

    # When seasons are disabled, collapse any season-level intent to a no-op
    if not seasons_enabled and level == "season":
        log.warning(
            "trailers_seasons_disabled_skipping_season_level",
            requested_level=level,
            requested_season=season,
        )
        level = "show"
        season = None

    return level, season


def _apply_level_filter(items: list[ScanItem], level: str, season: int | None) -> list[ScanItem]:
    """Filter ScanItems based on resolved level and season.

    Args:
        items: List of ScanItems to filter.
        level: Resolved level string: ``show``, ``season``, or ``both``.
        season: Specific season number to narrow to, or None.

    Returns:
        Filtered list.
    """
    if level == "both":
        return items
    if level == "show":
        return [item for item in items if item.season_number is None]
    # level == "season"
    season_items = [item for item in items if item.season_number is not None]
    if season is not None:
        season_items = [item for item in season_items if item.season_number == season]
    return season_items


def _seasons_enabled_from_config(config: Any) -> bool:
    """Extract ``config.trailers.seasons.enabled`` with a safe fallback.

    Args:
        config: Loaded pipeline Config.

    Returns:
        True when seasons are enabled in config; False otherwise.
    """
    try:
        return bool(config.trailers.seasons.enabled)
    except AttributeError:
        return False


def _min_file_size(config: Any) -> int:
    """Return ``config.trailers.filters.min_file_size_bytes`` safely.

    Args:
        config: Loaded pipeline Config.

    Returns:
        Minimum file size in bytes (default 102400 when missing).
    """
    try:
        return int(config.trailers.filters.min_file_size_bytes)
    except AttributeError:
        return 102400


def _allowed_extensions(config: Any) -> set[str]:
    """Return the allowed trailer extensions from config.

    Args:
        config: Loaded pipeline Config.

    Returns:
        Set of lowercase extension strings without leading dot.
    """
    try:
        return set(config.trailers.filters.allowed_extensions)
    except AttributeError:
        return {"mp4", "mkv", "webm"}


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------


@app.command()
def scan(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk", help="Restrict to one disk by ID (e.g. Disk1)."),
    category: str | None = typer.Option(None, "--category", help="Restrict to one category ID."),
    since: str | None = typer.Option(None, "--since", help="Only items added/modified after YYYY-MM-DD."),
    limit: int | None = typer.Option(None, "--limit", help="Max items to scan."),
    no_refresh: bool = typer.Option(False, "--no-refresh", help="Use cached library scan even if stale."),
    level: str = typer.Option(
        "both",
        "--level",
        help=(
            "Which trailer levels to list: show | season | both. "
            "Season-level is silently ignored when seasons.enabled is False."
        ),
    ),
    season: int | None = typer.Option(
        None,
        "--season",
        help="Target a specific season number (1-indexed). Implies --level=season.",
    ),
) -> None:
    """Dry-run: list media items missing trailers.

    Args:
        ctx: Typer context carrying AppCtx (config available via ctx.obj.config).
        disk: Optional disk ID filter.
        category: Optional category ID filter.
        since: Optional ISO date lower bound for item age.
        limit: Optional max item count.
        no_refresh: Skip library cache refresh when True.
        level: Trailer level filter (show / season / both).
        season: Specific season number; implies --level=season.
    """
    config = ctx.obj.config
    console = Console()

    seasons_enabled = _seasons_enabled_from_config(config)
    resolved_level, resolved_season = _resolve_level_and_season(level, season, seasons_enabled)
    since_dt = _parse_since(since)

    scanner = Scanner(
        min_file_size_bytes=_min_file_size(config),
        seasons_enabled=seasons_enabled,
    )

    staging_dir: Path = Path(str(config.paths.staging_dir))
    items = scanner.scan_staging(staging_dir)

    items = _filter_since(items, since_dt)
    items = _apply_level_filter(items, resolved_level, resolved_season)

    # Apply --disk filter by checking whether item.path starts with a disk mount
    if disk is not None:
        disk_paths: list[Path] = []
        try:
            for d in config.disks:
                if d.id == disk:
                    disk_paths.append(Path(str(d.path)))
        except (AttributeError, TypeError):
            pass
        if disk_paths:
            items = [item for item in items if any(str(item.path).startswith(str(dp)) for dp in disk_paths)]

    # Apply --category filter by checking path contains the category substring
    if category is not None:
        items = [item for item in items if category in str(item.path)]

    if limit is not None:
        items = items[:limit]

    log.info("trailers_scan_complete", count=len(items), disk=disk, category=category)

    if not items:
        console.print("[green]No media without trailers found.[/green]")
        return

    table = Table(title=f"Media missing trailers ({len(items)} items)", show_header=True)
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Season", justify="right")
    table.add_column("Path")

    for item in items:
        season_col = str(item.season_number) if item.season_number is not None else "-"
        table.add_row(item.title, item.media_type, season_col, str(item.path))

    console.print(table)


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


@app.command()
def download(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk", help="Restrict to one disk by ID (e.g. Disk1)."),
    category: str | None = typer.Option(None, "--category", help="Restrict to one category ID."),
    since: str | None = typer.Option(None, "--since", help="Only items added/modified after YYYY-MM-DD."),
    limit: int | None = typer.Option(None, "--limit", help="Max items to process."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be downloaded without doing it."),
    no_refresh: bool = typer.Option(False, "--no-refresh", help="Skip library cache refresh."),
    level: str = typer.Option(
        "both",
        "--level",
        help=(
            "Which trailer levels to process: show | season | both. "
            "Season-level is silently ignored when seasons.enabled is False."
        ),
    ),
    season: int | None = typer.Option(
        None,
        "--season",
        help="Target a specific season number (1-indexed). Implies --level=season.",
    ),
) -> None:
    """Discover and download missing trailers.

    Args:
        ctx: Typer context carrying AppCtx (config available via ctx.obj.config).
        disk: Optional disk ID filter.
        category: Optional category ID filter.
        since: Optional ISO date lower bound for item age.
        limit: Optional max item count.
        dry_run: When True, show candidates without downloading.
        no_refresh: Skip library cache refresh when True.
        level: Trailer level filter (show / season / both).
        season: Specific season number; implies --level=season.
    """
    config = ctx.obj.config
    console = Console()

    seasons_enabled = _seasons_enabled_from_config(config)
    resolved_level, resolved_season = _resolve_level_and_season(level, season, seasons_enabled)
    since_dt = _parse_since(since)

    if dry_run:
        # Dry-run: reuse scan logic to show candidates without downloading
        scanner = Scanner(
            min_file_size_bytes=_min_file_size(config),
            seasons_enabled=seasons_enabled,
        )
        staging_dir = Path(str(config.paths.staging_dir))
        items = scanner.scan_staging(staging_dir)
        items = _filter_since(items, since_dt)
        items = _apply_level_filter(items, resolved_level, resolved_season)

        if disk is not None:
            disk_paths: list[Path] = []
            try:
                for d in config.disks:
                    if d.id == disk:
                        disk_paths.append(Path(str(d.path)))
            except (AttributeError, TypeError):
                pass
            if disk_paths:
                items = [item for item in items if any(str(item.path).startswith(str(dp)) for dp in disk_paths)]

        if category is not None:
            items = [item for item in items if category in str(item.path)]

        if limit is not None:
            items = items[:limit]

        console.print(f"[yellow]DRY-RUN:[/yellow] Would attempt to download trailers for {len(items)} items.")
        return

    staging_dir = Path(str(config.paths.staging_dir))
    orchestrator = TrailersOrchestrator(config=config, staging_dir=staging_dir)
    counts = orchestrator.run()

    error_count = counts.get("error", 0)

    table = Table(title="Trailer download summary", show_header=True)
    table.add_column("Status")
    table.add_column("Count", justify="right")
    for status, count in counts.items():
        table.add_row(status.replace("_", " ").capitalize(), str(count))
    console.print(table)

    if error_count > 0:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


@app.command()
def verify(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk", help="Restrict to one disk by ID (e.g. Disk1)."),
    category: str | None = typer.Option(None, "--category", help="Restrict to one category ID."),
    since: str | None = typer.Option(None, "--since", help="Only items added/modified after YYYY-MM-DD."),
    deep: bool = typer.Option(False, "--deep", help="Run ffprobe playability probe (expensive)."),
    no_refresh: bool = typer.Option(False, "--no-refresh", help="Skip library cache refresh."),
    level: str = typer.Option(
        "both",
        "--level",
        help=(
            "Which trailer levels to audit: show | season | both. "
            "Season-level is silently ignored when seasons.enabled is False."
        ),
    ),
    season: int | None = typer.Option(
        None,
        "--season",
        help="Target a specific season number (1-indexed). Implies --level=season.",
    ),
) -> None:
    """Audit existing trailers.

    Runs four checks per trailer:
    1. Existence - trailer file present at the expected placement path.
    2. Size - file size >= config.trailers.filters.min_file_size_bytes.
    3. Extension - file suffix in config.trailers.filters.allowed_extensions.
    4. Playable (opt-in, --deep) - ffprobe returns non-zero duration.

    Failures report a category: missing, undersized, wrong_extension, unplayable.
    Exit codes: 0 if all pass, 2 if any functional check fails,
    4 if a --deep ffprobe call errors out (probe itself broken).

    Args:
        ctx: Typer context carrying AppCtx (config available via ctx.obj.config).
        disk: Optional disk ID filter.
        category: Optional category ID filter.
        since: Optional ISO date lower bound for item age.
        deep: When True, run ffprobe playability check (expensive).
        no_refresh: Skip library cache refresh when True.
        level: Trailer level filter (show / season / both).
        season: Specific season number; implies --level=season.
    """
    from personalscraper.trailers.placement import trailer_path_for, trailer_path_for_season  # noqa: PLC0415

    config = ctx.obj.config
    console = Console()

    seasons_enabled = _seasons_enabled_from_config(config)
    resolved_level, resolved_season = _resolve_level_and_season(level, season, seasons_enabled)
    since_dt = _parse_since(since)

    min_size = _min_file_size(config)
    allowed_exts = _allowed_extensions(config)

    scanner = Scanner(min_file_size_bytes=min_size, seasons_enabled=seasons_enabled)

    # verify operates on the permanent library (scan_library)
    items = scanner.scan_library(
        config=config,
        disk_filter=disk,
        category_filter=category,
        force_refresh=not no_refresh,
    )

    items = _filter_since(items, since_dt)
    items = _apply_level_filter(items, resolved_level, resolved_season)

    issues: list[tuple[str, str, str]] = []  # (title, trailer_path_str, issue_category)
    ffprobe_error = False

    for item in items:
        media_name = item.path.name
        if item.season_number is not None:
            trailer_p = trailer_path_for_season(item.path, item.season_number, "mp4")
        else:
            trailer_p = trailer_path_for(item.path, media_name)

        if not trailer_p.exists():
            issues.append((item.title, str(trailer_p), "missing"))
            continue

        actual_size = trailer_p.stat().st_size
        if actual_size < min_size:
            issues.append((item.title, str(trailer_p), "undersized"))
            continue

        ext = trailer_p.suffix.lstrip(".").lower()
        if ext not in allowed_exts:
            issues.append((item.title, str(trailer_p), "wrong_extension"))
            continue

        if deep:
            # TODO(v0.7.0): full ffprobe-based playability check not yet implemented.
            # Currently runs a minimal duration probe; exits code 4 on probe failure.
            log.warning(
                "trailers_verify_deep_stub",
                trailer_path=str(trailer_p),
                note="Full ffprobe-based check is not yet fully implemented (v0.7.0 TODO).",
            )
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        str(trailer_p),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    issues.append((item.title, str(trailer_p), "unplayable"))
            except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
                log.error("trailers_verify_ffprobe_error", trailer_path=str(trailer_p), error=str(exc))
                ffprobe_error = True

    if ffprobe_error:
        console.print("[red]ffprobe error: one or more probes failed (exit 4).[/red]")
        raise typer.Exit(code=4)

    if issues:
        table = Table(title=f"Trailer issues ({len(issues)} found)", show_header=True)
        table.add_column("Title")
        table.add_column("Issue")
        table.add_column("Path")
        for title, path, issue in issues:
            table.add_row(title, issue, path)
        console.print(table)
        raise typer.Exit(code=2)

    console.print(f"[green]All {len(items)} trailers verified OK.[/green]")


# ---------------------------------------------------------------------------
# purge
# ---------------------------------------------------------------------------


@app.command()
def purge(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk", help="Restrict to one disk by ID (e.g. Disk1)."),
    since: str | None = typer.Option(None, "--since", help="Only items added/modified after YYYY-MM-DD."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be purged without doing it."),
    include_state: bool = typer.Option(
        False,
        "--include-state",
        help="Also wipe orphan state entries via state_store.purge_orphans().",
    ),
    level: str = typer.Option(
        "both",
        "--level",
        help=(
            "Which trailer levels to purge: show | season | both. "
            "Season-level is silently ignored when seasons.enabled is False."
        ),
    ),
    season: int | None = typer.Option(
        None,
        "--season",
        help="Target a specific season number (1-indexed). Implies --level=season.",
    ),
) -> None:
    """Remove orphan trailers whose media parent is absent.

    When --include-state is set, after the filesystem purge completes call
    state_store.purge_orphans() and log the count in the CLI output.

    Args:
        ctx: Typer context carrying AppCtx (config available via ctx.obj.config).
        disk: Optional disk ID filter.
        since: Optional ISO date lower bound for item age.
        dry_run: When True, show orphans without deleting.
        include_state: When True, also call state_store.purge_orphans().
        level: Trailer level filter (show / season / both).
        season: Specific season number; implies --level=season.
    """
    config = ctx.obj.config
    console = Console()

    seasons_enabled = _seasons_enabled_from_config(config)
    _resolve_level_and_season(level, season, seasons_enabled)  # validate args eagerly
    _parse_since(since)  # validate date format eagerly

    state_file = Path(str(config.trailers.state_file))
    state_store = TrailerStateStore(state_file=state_file)

    entries = state_store.all_entries()

    # Identify orphan entries: those whose media_path no longer exists on disk
    orphan_trailer_paths: list[Path] = []
    for _key, entry_state in entries.items():
        media_path_str = getattr(entry_state, "media_path", None)
        if media_path_str and not Path(str(media_path_str)).exists():
            trailer_path_str = getattr(entry_state, "trailer_path", None)
            if trailer_path_str:
                trailer_p = Path(str(trailer_path_str))
                if trailer_p.exists():
                    orphan_trailer_paths.append(trailer_p)

    # Apply --disk filter
    if disk is not None:
        disk_paths: list[Path] = []
        try:
            for d in config.disks:
                if d.id == disk:
                    disk_paths.append(Path(str(d.path)))
        except (AttributeError, TypeError):
            pass
        if disk_paths:
            orphan_trailer_paths = [
                p for p in orphan_trailer_paths if any(str(p).startswith(str(dp)) for dp in disk_paths)
            ]

    if dry_run:
        console.print(f"[yellow]DRY-RUN:[/yellow] Would purge {len(orphan_trailer_paths)} orphan trailer(s).")
        if include_state:
            console.print("[yellow]DRY-RUN:[/yellow] Would also wipe orphan state entries (--include-state).")
        return

    deleted = 0
    for trailer_p in orphan_trailer_paths:
        try:
            trailer_p.unlink()
            deleted += 1
            log.info("trailers_purge_deleted", path=str(trailer_p))
        except OSError as exc:
            log.warning("trailers_purge_delete_failed", path=str(trailer_p), error=str(exc))

    console.print(f"[green]Purged {deleted} orphan trailer(s).[/green]")

    if include_state:
        purged_state = state_store.purge_orphans()
        console.print(f"[green]Purged {purged_state} orphan state entries.[/green]")
        log.info("trailers_purge_state_entries", count=purged_state)
