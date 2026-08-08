"""CLI command group: ``personalscraper follow`` — followed-series management (Follow D1).

Sub-commands:
- ``follow add --tvdb/--tmdb/--imdb/--title`` — follow a series (idempotent).
- ``follow list [--all]`` — list followed series.
- ``follow remove --tvdb/--id`` — soft-unfollow a series.
- ``follow detect [--dry-run] [--series]`` — poll aired episodes for active
  series and enqueue them as wanted items.

Registered as a Typer sub-group (``follow_app = typer.Typer(...)`` mounted via
``_root_app.add_typer``). Sub-commands use ``@follow_app.command("name")``
(NOT ``@command_with_telemetry`` which is root-app-only).
Uses ``@handle_cli_errors``, ``per_step_boundary``,
``build_torrent_client=False`` (follow management needs no torrent daemon).

Events emitted on ``app_context.event_bus``:
- :class:`~personalscraper.acquire.events.SeriesFollowed` on add (new or reactivated).
- :class:`~personalscraper.acquire.events.SeriesUnfollowed` on remove.

Import direction: commands/ imports acquire/, api/, core/, conf/, events/ only.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from personalscraper import cli_helpers
from personalscraper.acquire.detect import DetectAction, DetectOutcome, DetectService, DetectStatus
from personalscraper.acquire.events import SeriesFollowed, SeriesUnfollowed
from personalscraper.acquire.title_resolver import resolve_series_title
from personalscraper.cli_app import app as _root_app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.cli_state import state
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.core.identity import MediaRef
from personalscraper.logger import get_logger
from personalscraper.subscribers import build_redis_publisher

log = get_logger("cli.follow")

# Typer sub-group for the ``follow`` command.
follow_app = typer.Typer(help="Manage the followed-series list.")


@follow_app.command("add")
@handle_cli_errors
def follow_add(
    ctx: typer.Context,
    tvdb_id: Optional[int] = typer.Option(None, "--tvdb", help="TVDB series ID (primary)."),
    tmdb_id: Optional[int] = typer.Option(None, "--tmdb", help="TMDB series ID."),
    imdb_id: Optional[str] = typer.Option(None, "--imdb", help="IMDB series ID (e.g. tt0903747)."),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        help="Human-readable title (fallback when metadata unavailable).",
    ),
) -> None:
    """Follow a TV series by provider ID (idempotent).

    At least one of --tvdb, --tmdb, or --imdb is required. --tvdb is preferred
    (primary identifier). The canonical title is resolved via the metadata
    provider registry; --title is used as a fallback when resolution fails.
    """
    if tvdb_id is None and tmdb_id is None and imdb_id is None:
        typer.echo("Error: at least one of --tvdb, --tmdb, or --imdb is required.", err=True)
        raise typer.Exit(code=2)

    config = ctx.obj.config
    assert config is not None
    console: Console = state["console"]
    settings = cli_helpers.get_settings()

    with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
        redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
        try:
            acquire = app_context.acquire
            if acquire is None or acquire.store is None:
                console.print("[red]AcquireContext/store not available.[/red]")
                raise typer.Exit(1)

            store = acquire.store
            media_ref = MediaRef(tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id)

            # Resolve title fail-soft — never block a follow.
            resolved_title = resolve_series_title(
                media_ref,
                app_context.provider_registry,
                fallback_title=title,
            )

            existing = store.follow.find_by_ref(media_ref)
            if existing is not None and existing.active:
                console.print(f"[yellow]Already following:[/yellow] {existing.title} (id={existing.id})")
                return

            if existing is not None and not existing.active:
                # Reactivate (refollow after remove).
                assert existing.id is not None
                store.follow.set_active(existing.id, True)
                app_context.event_bus.emit(SeriesFollowed(media_ref=media_ref, title=existing.title))
                console.print(f"[green]Refollowing:[/green] {existing.title} (id={existing.id})")
                log.info("cli.follow.refollowed", tvdb_id=tvdb_id, title=existing.title)
                return

            # New follow.
            from personalscraper.acquire.domain import FollowedSeries  # noqa: PLC0415

            new_series = FollowedSeries(
                media_ref=media_ref,
                title=resolved_title,
                added_at=int(time.time()),
                active=True,
            )
            row_id = store.follow.add(new_series)
            app_context.event_bus.emit(SeriesFollowed(media_ref=media_ref, title=resolved_title))
            console.print(f"[green]Now following:[/green] {resolved_title} (id={row_id})")
            log.info("cli.follow.added", tvdb_id=tvdb_id, title=resolved_title, row_id=row_id)
        finally:
            if redis_publisher is not None:
                redis_publisher.close()


@follow_app.command("list")
@handle_cli_errors
def follow_list(
    ctx: typer.Context,
    all_series: bool = typer.Option(False, "--all", help="Include inactive (unfollowed) series."),
) -> None:
    """List followed series.

    By default shows only active series. Use --all to include unfollowed ones.
    """
    config = ctx.obj.config
    assert config is not None
    console: Console = state["console"]
    settings = cli_helpers.get_settings()

    with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
        acquire = app_context.acquire
        if acquire is None or acquire.store is None:
            console.print("[red]AcquireContext/store not available.[/red]")
            raise typer.Exit(1)

        store = acquire.store
        rows = store.follow.list_all() if all_series else store.follow.list_active()

        if not rows:
            console.print("[yellow]No followed series.[/yellow]")
            return

        table = Table(title="Followed Series", show_header=True)
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Title")
        table.add_column("TVDB", justify="right")
        table.add_column("TMDB", justify="right")
        table.add_column("IMDB")
        table.add_column("Active")

        for s in rows:
            table.add_row(
                str(s.id) if s.id is not None else "-",
                s.title,
                str(s.media_ref.tvdb_id) if s.media_ref.tvdb_id else "-",
                str(s.media_ref.tmdb_id) if s.media_ref.tmdb_id else "-",
                s.media_ref.imdb_id or "-",
                "[green]yes[/green]" if s.active else "[red]no[/red]",
            )
        console.print(table)


@follow_app.command("remove")
@handle_cli_errors
def follow_remove(
    ctx: typer.Context,
    tvdb_id: Optional[int] = typer.Option(None, "--tvdb", help="TVDB series ID."),
    followed_id: Optional[int] = typer.Option(None, "--id", help="followed_series row ID."),
) -> None:
    """Soft-unfollow a series (sets active=False, preserves history).

    Provide --tvdb <id> or --id <followed_id>.
    """
    if tvdb_id is None and followed_id is None:
        typer.echo("Error: provide --tvdb or --id.", err=True)
        raise typer.Exit(code=2)

    config = ctx.obj.config
    assert config is not None
    console: Console = state["console"]
    settings = cli_helpers.get_settings()

    with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
        redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
        try:
            acquire = app_context.acquire
            if acquire is None or acquire.store is None:
                console.print("[red]AcquireContext/store not available.[/red]")
                raise typer.Exit(1)

            store = acquire.store

            if tvdb_id is not None:
                series = store.follow.find_by_ref(MediaRef(tvdb_id=tvdb_id))
            else:
                series = store.follow.get(followed_id)  # type: ignore[arg-type]

            if series is None:
                console.print("[yellow]Series not found — nothing to remove.[/yellow]")
                return

            if not series.active:
                console.print(f"[yellow]Already inactive:[/yellow] {series.title} (id={series.id})")
                return

            assert series.id is not None
            store.follow.set_active(series.id, False)
            app_context.event_bus.emit(SeriesUnfollowed(media_ref=series.media_ref))
            console.print(f"[green]Unfollowed:[/green] {series.title} (id={series.id})")
            log.info("cli.follow.removed", series_id=series.id, title=series.title)
        finally:
            if redis_publisher is not None:
                redis_publisher.close()


@follow_app.command("detect")
@handle_cli_errors
def follow_detect(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview detected episodes without writing or emitting.",
    ),
    series: Optional[str] = typer.Option(
        None,
        "--series",
        help="Filter active set by integer followed_id or title substring.",
    ),
) -> None:
    """Detect aired episodes for followed series and enqueue them as wanted items.

    Stage A of the DETECT flow: polls the active followed set for every episode
    with a known air date (one ``poll_known`` call per series — futures included,
    cached but never enqueued), maps each back to its followed series via
    ``media_ref``, keeps only the aired ones (``air_date <= today``), skips owned
    episodes (RP6) and rows already present in the wanted queue, then enqueues the
    remainder as ``WantedItem(kind='episode', status='pending')`` and emits
    ``WantedEnqueued`` per enqueue.

    Both ``poll_known`` and ``ownership.owns`` are fail-soft: a failure is logged
    and treated as "no episodes" / "not owned" so one bad series or a missing
    library never aborts the run.

    Use ``--dry-run`` to preview without any writes or events.
    Use ``--series`` to restrict detection to a single series (integer
    ``followed_id`` or a case-insensitive title substring).
    """
    config = ctx.obj.config
    assert config is not None
    console: Console = state["console"]
    settings = cli_helpers.get_settings()

    with (
        cli_run_row(config, "follow-detect") as run_rec,
        per_step_boundary(config, settings, build_torrent_client=False) as app_context,
    ):
        redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
        try:
            acquire = app_context.acquire
            if acquire is None or acquire.store is None:
                console.print("[red]AcquireContext/store not available.[/red]")
                raise typer.Exit(1)

            # ACQUIRE-03: all DETECT business logic lives in the acquire service
            # layer (grab parity). The CLI keeps only rendering + run-row counts.
            service = DetectService(
                store=acquire.store,
                ownership=acquire.ownership,
                registry=app_context.provider_registry,
                event_bus=app_context.event_bus,
                config=config,
            )
            result = service.run(
                series=series,
                dry_run=dry_run,
                today=date.today(),
                now=int(time.time()),
            )

            if result.status is DetectStatus.NO_ACTIVE:
                console.print("[yellow]No active followed series.[/yellow]")
                return
            if result.status is DetectStatus.NO_MATCH:
                console.print("[yellow]No matching series.[/yellow]")
                return

            table = Table(title="Follow Detect", show_header=True)
            table.add_column("Series")
            table.add_column("Season", justify="right")
            table.add_column("Episode", justify="right")
            table.add_column("AirDate")
            table.add_column("Title")
            table.add_column("Action")
            for action in result.actions:
                table.add_row(*_detect_row(action, dry_run=dry_run))
            console.print(table)

            s = result.summary
            console.print(
                f"{s.enqueued} enqueued, {s.skipped_owned} skipped-owned, {s.skipped_dup} skipped-dup, "
                f"{s.resurrected} resurrected, {s.closed_owned} closed-owned"
                + (" [dim](dry-run)[/dim]" if dry_run else "")
            )
            # §5 « résultat chiffré »: persist the run's numbers on its
            # pipeline_run row so the web surface shows a real result, never
            # a bare success badge.
            run_rec.record_counts(
                {
                    "detected": s.detected,
                    "enqueued": s.enqueued,
                    "skipped_owned": s.skipped_owned,
                    "skipped_dup": s.skipped_dup,
                    "resurrected": s.resurrected,
                    "closed_owned": s.closed_owned,
                }
            )
        finally:
            if redis_publisher is not None:
                redis_publisher.close()


def _detect_action_cell(action: DetectAction, *, dry_run: bool) -> str:
    """Map a detect outcome (+ dry-run) to its exact table-cell markup label.

    Args:
        action: The detect action whose outcome selects the label.
        dry_run: Whether the run is a preview (changes the enqueue/resurrect
            labels to the dimmed dry-run form).

    Returns:
        The rich-markup string used in the "Action" column, byte-identical to
        the pre-extraction inline labels.
    """
    outcome = action.outcome
    if outcome is DetectOutcome.FILM_ACQUIRED:
        return "[green]acquis — retiré des suivis[/green]"
    if outcome is DetectOutcome.SKIPPED_OWNED:
        return "[yellow]skipped-owned[/yellow]"
    if outcome is DetectOutcome.SKIPPED_DUP:
        return "[dim]skipped-dup[/dim]"
    if outcome is DetectOutcome.RESURRECTED:
        return "[dim]resurrect (dry-run)[/dim]" if dry_run else "[green]resurrected[/green]"
    return "[dim]dry-run[/dim]" if dry_run else "[green]enqueued[/green]"


def _detect_row(action: DetectAction, *, dry_run: bool) -> tuple[str | None, ...]:
    """Render one :class:`DetectAction` into its 6 table columns.

    Movie rows carry em-dashes in the season/episode/air-date columns and an
    empty title cell; season rows (R1) carry the season number, an em-dash in
    the episode column and the last air date; episode rows carry the real
    values — the movie/episode forms are identical to the pre-extraction
    ``table.add_row`` calls.

    Args:
        action: The detect action to render.
        dry_run: Whether the run is a preview (forwarded to the label mapper).

    Returns:
        A 6-tuple ``(series, season, episode, air_date, title, action_cell)``.
    """
    cell = _detect_action_cell(action, dry_run=dry_run)
    if action.kind == "movie":
        return (action.title, "—", "—", "—", "", cell)
    if action.kind == "season":
        # A whole-season action has no single episode — render the em-dash,
        # not the literal "None" (review F9).
        return (action.title, str(action.season), "—", action.air_date or "", "", cell)
    return (action.title, str(action.season), str(action.episode), action.air_date or "", action.episode_title, cell)


def _media_ref_from_json(media_ref_json: str | None) -> MediaRef | None:
    """Parse a ``followed_series.media_ref_json`` column into a :class:`MediaRef`.

    Args:
        media_ref_json: The raw JSON column value, or ``None``.

    Returns:
        The parsed ref, or ``None`` when the column is empty, malformed, or
        carries no provider id at all (a legacy row nothing can be looked up by).
    """
    import json as _json

    if not media_ref_json:
        return None
    try:
        ref = _json.loads(media_ref_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(ref, dict):
        return None
    try:
        return MediaRef(tvdb_id=ref.get("tvdb_id"), tmdb_id=ref.get("tmdb_id"), imdb_id=ref.get("imdb_id"))
    except ValueError:
        return None


@follow_app.command("backfill-metadata")
@handle_cli_errors
def follow_backfill_metadata(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing."),
) -> None:
    """Backfill ``poster_url`` + ``overview`` + ``year`` for follows added before this fix.

    Repairs the rows the server could not enrich at creation time (acq-states
    §7.3). Shares the SINGLE enrichment authority with the create-follow route
    (``acquire.metadata_enrich``): each missing field is fetched from the
    provider BY ID — never by a title search — so a wrong poster is impossible
    by construction, and the strict TVDB/TMDB separation is honoured for free.
    Idempotent (a complete row is untouched) and additive (``COALESCE`` never
    overwrites an existing value). Read-only under ``--dry-run``.

    Transaction shape (PR #320 review, m10): the scan connection is READ-ONLY
    and every write goes through ``store.follow.merge_metadata`` — one short
    ``BEGIN IMMEDIATE`` per row, taken AFTER that row's provider calls have
    returned. The previous form issued raw ``UPDATE``s on the scan connection
    and committed once at the end, so Python's implicit transaction opened on
    the first update and held the single-writer lock across every remaining
    HTTP round-trip: on a large library that blocked the watcher, the web app
    and the crons for minutes, and one slow provider could stall them all. It
    also bypassed the store seam that owns acquire-DB writes (ACQUIRE-09).
    """
    import sqlite3

    from personalscraper.acquire.metadata_enrich import FollowMetadata, enrich_follow_metadata
    from personalscraper.acquire.store import build_acquire_store
    from personalscraper.core.sqlite._pragmas import apply_pragmas

    config = ctx.obj.config
    assert config is not None  # noqa: S101 — set by the CLI root callback
    console: Console = state["console"]
    settings = cli_helpers.get_settings()
    db_path = config.acquire.db_path
    if db_path is None:
        console.print("[red]No acquire DB configured.[/red]")
        raise typer.Exit(1)

    with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
        registry = app_context.provider_registry
        tmdb_client = registry.get("tmdb")
        tvdb_client = registry.get("tvdb")

        # Reads are lock-free (WAL); writes go through the store below.
        conn = sqlite3.connect(str(db_path))
        apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
        store = build_acquire_store(config.acquire)
        try:
            # The poster_url/overview/year columns land together with acquire
            # migration 005; on a DB still at an earlier version (e.g. prod before
            # this feature merges) this command is a clean no-op rather than an
            # OperationalError. ``kind`` arrives later (006) — its absence just
            # means every row is treated as a show, which is what it was then.
            columns = {r[1] for r in conn.execute("PRAGMA table_info(followed_series)").fetchall()}
            if not {"poster_url", "overview", "year"} <= columns:
                console.print(
                    "[yellow]followed_series has no poster_url/overview/year columns yet "
                    "(acquire migration 005 not applied) — nothing to backfill.[/yellow]"
                )
                return
            has_kind = "kind" in columns
            rows = conn.execute("SELECT * FROM followed_series").fetchall()
            updated = 0
            skipped = 0
            for row in rows:
                existing = FollowMetadata(
                    poster_url=row["poster_url"] or None,
                    overview=row["overview"] or None,
                    year=row["year"],
                    # The row already carries its name — seed it, or the
                    # backfill would call a provider for a title it holds.
                    title=row["title"] or None,
                )
                if existing.is_complete:
                    continue
                media_ref = _media_ref_from_json(row["media_ref_json"])
                if media_ref is None:
                    skipped += 1
                    log.info("cli.follow.backfill.no_provider_id", followed_id=row["id"], title=row["title"])
                    continue
                kind = (row["kind"] if has_kind else None) or "show"
                resolved = enrich_follow_metadata(
                    media_ref,
                    kind,
                    tmdb_client=tmdb_client,
                    tvdb_client=tvdb_client,
                    existing=existing,
                )
                if resolved == existing:
                    skipped += 1
                    log.info("cli.follow.backfill.no_provider_data", followed_id=row["id"], title=row["title"])
                    continue
                # A nameless row has nothing to print as a name — show the id
                # and the resolved title, or the line reads as an empty repair.
                shown = row["title"] or f"#{row['id']} (sans nom)"
                console.print(
                    f"[green]{shown}[/green] ← "
                    + " ".join(
                        f"{label}={'yes' if before is None and after is not None else '—'}"
                        for label, before, after in (
                            ("titre", existing.title, resolved.title),
                            ("poster", existing.poster_url, resolved.poster_url),
                            ("overview", existing.overview, resolved.overview),
                            ("year", existing.year, resolved.year),
                        )
                    )
                    + (f" → « {resolved.title} »" if existing.title is None and resolved.title else "")
                )
                if not dry_run:
                    # One short write transaction for THIS row, taken after its
                    # provider calls returned — never a lock held across I/O.
                    store.follow.merge_metadata(
                        row["id"],
                        poster_url=resolved.poster_url,
                        overview=resolved.overview,
                        year=resolved.year,
                        # Repairs a follow created nameless (the add-by-ID
                        # form, before the title was resolved at create).
                        title=resolved.title,
                    )
                    updated += 1
            console.print(f"[bold]{'(dry-run) ' if dry_run else ''}Backfilled {updated}, skipped {skipped}.[/bold]")
        finally:
            store.close()
            conn.close()


# Register the follow sub-group on the root Typer app (import side-effect, called by cli.py).
_root_app.add_typer(follow_app, name="follow")

__all__ = [
    "follow_add",
    "follow_app",
    "follow_backfill_metadata",
    "follow_detect",
    "follow_list",
    "follow_remove",
]
