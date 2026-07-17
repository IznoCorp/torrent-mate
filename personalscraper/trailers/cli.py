"""CLI commands for the trailers feature.

Sub-app mounted at ``personalscraper trailers`` via typer.

Subcommands:
    scan      - Dry-run: list media missing trailers
    download  - Discover and download missing trailers
    audit     - Audit existing trailers (size, extension)
    purge     - Remove orphan trailers (media parent absent)

Common filters (scan, download, verify, purge)::
    --disk DISK_ID
    --category CATEGORY_ID
    --since YYYY-MM-DD
    --limit N
    --no-refresh   (skip library cache refresh)
    --level {show|season|both}
    --season N

Flags specific to ``download`` and ``purge`` only::
    --dry-run
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import typer
from rich.console import Console
from rich.table import Table

from personalscraper import cli_helpers
from personalscraper.cli_helpers import _build_app_context
from personalscraper.core.event_bus import current_correlation_id
from personalscraper.logger import get_logger
from personalscraper.trailers.orchestrator import TrailersOrchestrator
from personalscraper.trailers.scanner import ScanItem, Scanner
from personalscraper.trailers.state import TrailerStateLocked, TrailerStateStore


@contextmanager
def _trailers_boundary(config: Any):  # type: ignore[no-untyped-def]
    """Build :class:`AppContext` + bind ``current_correlation_id`` for a trailers command.

    Yields the :class:`AppContext` so the command body can pass
    ``event_bus=app_context.event_bus`` to downstream orchestrators
    (Sub-phase 2.5 boundary-only rule). The ``current_correlation_id``
    ContextVar is bound to a fresh ``uuid4()`` for the duration of the
    body and reset in the ``finally`` clause even on exception, mirroring
    the lifecycle locked in :meth:`Pipeline.run` (Sub-phase 2.3).

    Args:
        config: The typed JSON5 ``Config`` loaded by ``cli.main``.

    Yields:
        The freshly-built :class:`AppContext` carrying ``config``,
        ``settings``, and a fresh :class:`EventBus`.
    """
    settings = cli_helpers.get_settings()
    app_context = _build_app_context(config, settings)
    token = current_correlation_id.set(str(uuid4()))
    try:
        yield app_context
    finally:
        current_correlation_id.reset(token)


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


def _resolve_category_token(config: Any, category: str) -> str:
    """Resolve a --category token to the staging folder name to match against.

    The CLI accepts any of: the staging entry ``name`` (e.g. ``tvshows``),
    its ``file_type`` (``tvshow``), or the on-disk folder name
    (``002-TVSHOWS``). All resolve to the canonical folder name. When nothing
    matches we return the raw token so the legacy substring behaviour still
    works for ad-hoc paths.

    Args:
        config: Loaded pipeline Config (may have ``staging_dirs``).
        category: Raw ``--category`` value from the CLI.

    Returns:
        A path-substring guaranteed to live inside the canonical folder when
        the token resolves; otherwise the raw token.
    """
    from personalscraper.conf.staging import folder_name

    try:
        entries = list(config.staging_dirs)
    except (AttributeError, TypeError):
        return category
    token = category.strip()
    token_lower = token.lower()
    for entry in entries:
        candidates = {
            getattr(entry, "name", "").lower(),
            (getattr(entry, "file_type", "") or "").lower(),
            folder_name(entry).lower(),
        }
        if token_lower in candidates:
            return folder_name(entry)
    return category


def _apply_filters(
    items: list[ScanItem],
    config: Any,
    *,
    disk: str | None,
    category: str | None,
    since_dt: datetime | None,
    level: str,
    season: int | None,
    limit: int | None,
) -> list[ScanItem]:
    """Apply the full filter chain to a ScanItem list.

    Centralises the filtering so the dry-run path AND the real download path
    apply EXACTLY the same predicates. Without this helper, the real download
    path historically silently ignored every CLI filter (see commit 28d9f75).

    Args:
        items: ScanItems produced by ``Scanner.scan_staging``.
        config: Loaded pipeline Config (used by --disk and --category).
        disk: Optional disk ID; when set, drop items not under the disk path.
        category: Optional category token; resolved via
            ``_resolve_category_token``, then applied as a path substring.
        since_dt: Optional UTC cutoff for item age (NFO/dir mtime).
        level: Resolved level (``show``/``season``/``both``).
        season: Optional explicit season filter.
        limit: Optional max item count.

    Returns:
        The filtered list, in the same order as the input.
    """
    items = _filter_since(items, since_dt)
    items = _apply_level_filter(items, level, season)
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
        token = _resolve_category_token(config, category)
        items = [item for item in items if token in str(item.path)]
    if limit is not None:
        items = items[:limit]
    return items


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

    with _trailers_boundary(config):
        seasons_enabled = _seasons_enabled_from_config(config)
        resolved_level, resolved_season = _resolve_level_and_season(level, season, seasons_enabled)
        since_dt = _parse_since(since)

        scanner = Scanner(
            min_file_size_bytes=_min_file_size(config),
            seasons_enabled=seasons_enabled,
        )

        staging_dir: Path = Path(str(config.paths.staging_dir))
        items = scanner.scan_staging(staging_dir, config)
        items = _apply_filters(
            items,
            config,
            disk=disk,
            category=category,
            since_dt=since_dt,
            level=resolved_level,
            season=resolved_season,
            limit=limit,
        )

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

    with _trailers_boundary(config) as app_context:
        seasons_enabled = _seasons_enabled_from_config(config)
        resolved_level, resolved_season = _resolve_level_and_season(level, season, seasons_enabled)
        since_dt = _parse_since(since)

        # Build the filtered candidate list ONCE, then either show it (dry-run)
        # or hand it to the orchestrator (real). Sharing the same _apply_filters
        # path is the load-bearing invariant: it makes the dry-run faithfully
        # represent the real run, and prevents the real run from silently
        # ignoring CLI filters (see commit 28d9f75).
        scanner = Scanner(
            min_file_size_bytes=_min_file_size(config),
            seasons_enabled=seasons_enabled,
        )
        staging_dir = Path(str(config.paths.staging_dir))
        items = scanner.scan_staging(staging_dir, config)
        items = _apply_filters(
            items,
            config,
            disk=disk,
            category=category,
            since_dt=since_dt,
            level=resolved_level,
            season=resolved_season,
            limit=limit,
        )

        if dry_run:
            console.print(f"[yellow]DRY-RUN:[/yellow] Would attempt to download trailers for {len(items)} items.")
            for item in items:
                season_col = f" (season {item.season_number})" if item.season_number is not None else ""
                console.print(f"  - {item.title}{season_col}  [dim]{item.path}[/dim]")
            return

        orchestrator = TrailersOrchestrator(
            config=config,
            staging_dir=staging_dir,
            event_bus=app_context.event_bus,
            registry=app_context.provider_registry,
        )
        counts = orchestrator.run(items=items)

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
# audit
# ---------------------------------------------------------------------------


def _audit_impl(
    ctx: typer.Context,
    *,
    disk: str | None,
    category: str | None,
    since: str | None,
    deep: bool,
    level: str,
    season: int | None,
) -> None:
    """Shared body for the ``trailers audit`` command.

    Extracted from the typer entrypoint so the implementation can be reused
    by direct callers (tests, future scripted access) without going through
    the typer wrapper.

    Args:
        ctx: Typer context carrying AppCtx (config available via ``ctx.obj.config``).
        disk: Optional disk ID filter.
        category: Optional category ID filter.
        since: Optional ISO date lower bound for item age.
        deep: When True, run ffprobe playability check (expensive).
        level: Trailer level filter (``show`` / ``season`` / ``both``).
        season: Specific season number; implies ``--level=season``.
    """
    import sqlite3  # noqa: PLC0415 — deferred to avoid top-level import cost

    from personalscraper.indexer.db import open_db  # noqa: PLC0415
    from personalscraper.trailers.placement import (  # noqa: PLC0415
        find_existing_trailer,
        trailer_path_for,
        trailer_path_for_season,
    )

    config = ctx.obj.config
    console = Console()

    with _trailers_boundary(config) as app_context:
        seasons_enabled = _seasons_enabled_from_config(config)
        resolved_level, resolved_season = _resolve_level_and_season(level, season, seasons_enabled)
        since_dt = _parse_since(since)

        min_size = _min_file_size(config)
        allowed_exts = _allowed_extensions(config)

        scanner = Scanner(min_file_size_bytes=min_size, seasons_enabled=seasons_enabled)

        # Audit is a filesystem probe over the WHOLE library (constitution P26:
        # the filesystem is the single truth for trailer existence). We enumerate
        # ALL dispatched items (scan_library_all — no trailer_found predicate) and
        # probe the disk ourselves so the audit can SHOW what exists, not only
        # what is missing (F6 / §8).
        db_path = config.indexer.db_path
        conn: sqlite3.Connection = open_db(db_path, event_bus=app_context.event_bus)
        try:
            items = scanner.scan_library_all(
                conn=conn,
                disk_filter=disk,
                category_filter=category,
            )
        finally:
            conn.close()

        items = _filter_since(items, since_dt)
        items = _apply_level_filter(items, resolved_level, resolved_season)

        existing: list[tuple[str, str]] = []  # (title, trailer_path_str)
        issues: list[tuple[str, str, str]] = []  # (title, trailer_path_str, issue_category)
        ffprobe_error = False

        for item in items:
            media_name = item.path.name
            # Locate the trailer on disk (the FS truth). Show/movie-level items
            # scan every known extension; season-level items probe the single
            # seasonal placement slot.
            if item.season_number is not None:
                seasonal_p = trailer_path_for_season(item.path, item.season_number, "mp4")
                found: Path | None = seasonal_p if seasonal_p.exists() else None
                trailer_p = seasonal_p
            else:
                found = find_existing_trailer(item.path, media_name, media_type=item.media_type)
                trailer_p = (
                    found if found is not None else trailer_path_for(item.path, media_name, media_type=item.media_type)
                )

            if found is None:
                issues.append((item.title, str(trailer_p), "missing"))
                continue

            actual_size = found.stat().st_size
            if actual_size < min_size:
                issues.append((item.title, str(found), "undersized"))
                continue

            ext = found.suffix.lstrip(".").lower()
            if ext not in allowed_exts:
                issues.append((item.title, str(found), "wrong_extension"))
                continue

            if deep:
                # Minimal duration probe via ffprobe. A more thorough playability
                # check (codec, bitrate, audio track presence) would require parsing
                # the full ffprobe JSON output and is intentionally out of scope.
                log.debug(
                    "trailers_verify_deep_probe",
                    trailer_path=str(found),
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
                            str(found),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    # Flag corrupt files (non-zero returncode or empty output) and
                    # zero-duration files (ffprobe parsed a 0.0 or negative value).
                    duration_str = result.stdout.strip()
                    try:
                        duration_val = float(duration_str) if duration_str else 0.0
                    except ValueError:
                        duration_val = 0.0
                    if result.returncode != 0 or duration_val <= 0.0:
                        issues.append((item.title, str(found), "unplayable"))
                        continue
                except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
                    log.error("trailers_verify_ffprobe_error", trailer_path=str(found), error=str(exc))
                    ffprobe_error = True
                    continue

            # Passed every applicable check — a healthy, present trailer (F6).
            existing.append((item.title, str(found)))

        if ffprobe_error:
            console.print("[red]ffprobe error: one or more probes failed (exit 4).[/red]")
            raise typer.Exit(code=4)

        # F6 / §8: always SHOW what exists on disk, not only what is missing.
        if existing:
            existing_table = Table(title=f"Existing trailers ({len(existing)})", show_header=True)
            existing_table.add_column("Title")
            existing_table.add_column("Path")
            for title, path in existing:
                existing_table.add_row(title, path)
            console.print(existing_table)
        else:
            console.print("[dim]No existing trailers found.[/dim]")

        if issues:
            table = Table(title=f"Trailer issues ({len(issues)} found)", show_header=True)
            table.add_column("Title")
            table.add_column("Issue")
            table.add_column("Path")
            for title, path, issue in issues:
                table.add_row(title, issue, path)
            console.print(table)
            raise typer.Exit(code=2)

        console.print(f"[green]All {len(existing)} trailers verified OK.[/green]")


@app.command("audit")
def audit(
    ctx: typer.Context,
    disk: str | None = typer.Option(None, "--disk", help="Restrict to one disk by ID (e.g. Disk1)."),
    category: str | None = typer.Option(None, "--category", help="Restrict to one category ID."),
    since: str | None = typer.Option(None, "--since", help="Only items added/modified after YYYY-MM-DD."),
    deep: bool = typer.Option(False, "--deep", help="Run ffprobe playability probe (expensive)."),
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
    """Audit existing trailers (canonical command).

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
        level: Trailer level filter (show / season / both).
        season: Specific season number; implies --level=season.
    """
    _audit_impl(
        ctx,
        disk=disk,
        category=category,
        since=since,
        deep=deep,
        level=level,
        season=season,
    )


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

    with _trailers_boundary(config):
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
            try:
                purged_state = state_store.purge_orphans()
            except TrailerStateLocked:
                console.print("[red]Another trailers process is running; try again later.[/red]")
                raise typer.Exit(1)
            console.print(f"[green]Purged {purged_state} orphan state entries.[/green]")
            log.info("trailers_purge_state_entries", count=purged_state)
