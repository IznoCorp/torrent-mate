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

from personalscraper import cli as cli_compat
from personalscraper.acquire.airing import poll_aired
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import FilmAcquired, SeriesFollowed, SeriesUnfollowed, WantedEnqueued
from personalscraper.acquire.title_resolver import resolve_series_title
from personalscraper.cli_app import app as _root_app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.cli_state import state
from personalscraper.commands._acquire_run_row import acquisition_run_row
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
    settings = cli_compat.get_settings()

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
    settings = cli_compat.get_settings()

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
    settings = cli_compat.get_settings()

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

    Stage A of the DETECT flow: polls the active followed set for aired episodes
    (one ``poll_aired`` call over the whole set), maps each aired episode back to
    its followed series via ``media_ref``, skips owned episodes (RP6) and rows
    already present in the wanted queue, then enqueues the remainder as
    ``WantedItem(kind='episode', status='pending')`` and emits ``WantedEnqueued``
    per enqueue.

    Both ``poll_aired`` and ``ownership.owns`` are fail-soft: a failure is logged
    and treated as "no episodes" / "not owned" so one bad series or a missing
    library never aborts the run.

    Use ``--dry-run`` to preview without any writes or events.
    Use ``--series`` to restrict detection to a single series (integer
    ``followed_id`` or a case-insensitive title substring).
    """
    config = ctx.obj.config
    assert config is not None
    console: Console = state["console"]
    settings = cli_compat.get_settings()

    with (
        acquisition_run_row(config, "follow-detect") as run_rec,
        per_step_boundary(config, settings, build_torrent_client=False) as app_context,
    ):
        redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
        try:
            acquire = app_context.acquire
            if acquire is None or acquire.store is None:
                console.print("[red]AcquireContext/store not available.[/red]")
                raise typer.Exit(1)

            store = acquire.store
            ownership = acquire.ownership
            bus = app_context.event_bus
            registry = app_context.provider_registry
            today = date.today()
            now = int(time.time())

            active = store.follow.list_active()
            if not active:
                console.print("[yellow]No active followed series.[/yellow]")
                return

            # Optional filter: integer followed_id, else case-insensitive title substring.
            if series is not None:
                try:
                    filter_id = int(series)
                    active = [s for s in active if s.id == filter_id]
                except ValueError:
                    active = [s for s in active if series.lower() in s.title.lower()]
                if not active:
                    console.print("[yellow]No matching series.[/yellow]")
                    return

            # §5 films: a movie follow produces ONE WantedItem(kind='movie') —
            # no airing poll (a film has no episode schedule; it is wanted as
            # soon as it is followed and not yet owned). Split the set so
            # poll_aired only sees shows (a movie follow has no tvdb series id
            # and would only be silently skipped by the poller).
            movie_follows = [s for s in active if s.kind == "movie"]
            show_follows = [s for s in active if s.kind != "movie"]

            # MediaRef is a frozen dataclass → hashable; map each aired episode back
            # to its followed series by provider-ID key.
            by_ref = {s.media_ref: s for s in show_follows}

            # ONE poll over the active shows — poll_aired is fail-soft per series
            # internally, so the broad except is purely defensive.
            aired = []
            if show_follows:
                try:
                    aired = poll_aired(show_follows, registry, today=today)
                except Exception as exc:  # noqa: BLE001 — defensive; poll_aired already fail-soft
                    log.warning("cli.follow.detect.poll_failed", error=str(exc))
                    aired = []

            table = Table(title="Follow Detect", show_header=True)
            table.add_column("Series")
            table.add_column("Season", justify="right")
            table.add_column("Episode", justify="right")
            table.add_column("AirDate")
            table.add_column("Title")
            table.add_column("Action")

            enqueued = skipped_owned = skipped_dup = 0

            for mf in movie_follows:
                if mf.id is None:
                    continue
                # Ownership check (fail-soft: error → treat as not-owned).
                try:
                    owned = ownership.owns(mf.media_ref, kind="movie")
                except Exception as exc:  # noqa: BLE001 — fail-soft → treat as not-owned
                    log.warning("cli.follow.detect.ownership_error", error=str(exc))
                    owned = False
                if owned:
                    # §5 closure: the film is IN the library — close its live
                    # wanted row (done) and auto-unfollow, with a visible trace
                    # ("Film X acquis — retiré des suivis"). Ownership by
                    # provider ID is the robust reconciliation (the info-hash
                    # dispatch correlation misses scraped/renamed movies whose
                    # staging size diverges from the torrent). Fail-soft: an
                    # error leaves the follow active for the next detect run.
                    if not dry_run:
                        try:
                            live = store.wanted.find(followed_id=mf.id, kind="movie", season=None, episode=None)
                            if live is not None and live.id is not None and live.status != "done":
                                store.wanted.set_status(live.id, "done")
                            store.follow.set_active(mf.id, False)
                            bus.emit(FilmAcquired(media_ref=mf.media_ref, title=mf.title, followed_id=mf.id))
                            log.info("cli.follow.detect.film_acquired_unfollowed", series=mf.title)
                            table.add_row(mf.title, "—", "—", "—", "", "[green]acquis — retiré des suivis[/green]")
                            skipped_owned += 1
                            continue
                        except Exception as exc:  # noqa: BLE001 — fail-soft; retried next run
                            log.warning("cli.follow.detect.film_unfollow_failed", error=str(exc))
                    table.add_row(mf.title, "—", "—", "—", "", "[yellow]skipped-owned[/yellow]")
                    skipped_owned += 1
                    continue
                # Dedup: one live wanted row per movie follow (NULL season/episode).
                if store.wanted.find(followed_id=mf.id, kind="movie", season=None, episode=None) is not None:
                    table.add_row(mf.title, "—", "—", "—", "", "[dim]skipped-dup[/dim]")
                    skipped_dup += 1
                    continue
                table.add_row(
                    mf.title, "—", "—", "—", "", "[dim]dry-run[/dim]" if dry_run else "[green]enqueued[/green]"
                )
                enqueued += 1
                if not dry_run:
                    store.wanted.add(
                        WantedItem(
                            media_ref=mf.media_ref,
                            kind="movie",
                            status="pending",
                            enqueued_at=now,
                            followed_id=mf.id,
                        )
                    )
                    bus.emit(WantedEnqueued(media_ref=mf.media_ref, kind="movie", season=None, episode=None))
                    log.info("cli.follow.detect.enqueued", series=mf.title, kind="movie")

            for ep in aired:
                fs = by_ref.get(ep.media_ref)
                if fs is None or fs.id is None:
                    continue

                # Ownership check (fail-soft: error → treat as not-owned).
                try:
                    owned = ownership.owns(
                        ep.media_ref,
                        kind="episode",
                        season=ep.season,
                        episode=ep.episode,
                    )
                except Exception as exc:  # noqa: BLE001 — fail-soft → treat as not-owned
                    log.warning("cli.follow.detect.ownership_error", error=str(exc))
                    owned = False

                if owned:
                    table.add_row(
                        fs.title,
                        str(ep.season),
                        str(ep.episode),
                        str(ep.air_date),
                        ep.title,
                        "[yellow]skipped-owned[/yellow]",
                    )
                    skipped_owned += 1
                    continue

                # Dedup against the wanted queue.
                if (
                    store.wanted.find(
                        followed_id=fs.id,
                        kind="episode",
                        season=ep.season,
                        episode=ep.episode,
                    )
                    is not None
                ):
                    table.add_row(
                        fs.title,
                        str(ep.season),
                        str(ep.episode),
                        str(ep.air_date),
                        ep.title,
                        "[dim]skipped-dup[/dim]",
                    )
                    skipped_dup += 1
                    continue

                action = "[dim]dry-run[/dim]" if dry_run else "[green]enqueued[/green]"
                table.add_row(
                    fs.title,
                    str(ep.season),
                    str(ep.episode),
                    str(ep.air_date),
                    ep.title,
                    action,
                )
                enqueued += 1

                if not dry_run:
                    # No ``criteria_json`` set: DESIGN §6's
                    # ``criteria_json = source_criteria(...) or None`` reduces to
                    # ``None`` at D2 since ``FollowedSeries`` has no per-series
                    # source-criteria field yet — the mapping wasn't dropped.
                    store.wanted.add(
                        WantedItem(
                            media_ref=ep.media_ref,
                            kind="episode",
                            status="pending",
                            enqueued_at=now,
                            followed_id=fs.id,
                            season=ep.season,
                            episode=ep.episode,
                        )
                    )
                    bus.emit(
                        WantedEnqueued(
                            media_ref=ep.media_ref,
                            kind="episode",
                            season=ep.season,
                            episode=ep.episode,
                        )
                    )
                    log.info(
                        "cli.follow.detect.enqueued",
                        series=fs.title,
                        season=ep.season,
                        episode=ep.episode,
                    )

            console.print(table)
            console.print(
                f"{enqueued} enqueued, {skipped_owned} skipped-owned, {skipped_dup} skipped-dup"
                + (" [dim](dry-run)[/dim]" if dry_run else "")
            )
            # §5 « résultat chiffré »: persist the run's numbers on its
            # pipeline_run row so the web surface shows a real result, never
            # a bare success badge.
            run_rec.record_counts(
                {
                    "detected": enqueued + skipped_owned + skipped_dup,
                    "enqueued": enqueued,
                    "skipped_owned": skipped_owned,
                    "skipped_dup": skipped_dup,
                }
            )
        finally:
            if redis_publisher is not None:
                redis_publisher.close()


def _candidate_matching_id(
    candidates: list[object],
    tvdb_id: int | None,
    tmdb_id: int | None,
) -> object | None:
    """Return the candidate whose provider id equals the follow's own id, or None.

    Matching strictly by id (never by rank/title) so a follow with no id-matched
    candidate is skipped rather than assigned a wrong poster.

    Args:
        candidates: Scored provider candidates from a detailed match.
        tvdb_id: The follow's TVDB id, or None.
        tmdb_id: The follow's TMDB id, or None.

    Returns:
        The matching candidate, or None.
    """
    for candidate in candidates:
        provider = getattr(candidate, "provider", None)
        provider_id = str(getattr(candidate, "provider_id", ""))
        if provider == "tvdb" and tvdb_id is not None and str(tvdb_id) == provider_id:
            return candidate
        if provider == "tmdb" and tmdb_id is not None and str(tmdb_id) == provider_id:
            return candidate
    return None


@follow_app.command("backfill-metadata")
@handle_cli_errors
def follow_backfill_metadata(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing."),
) -> None:
    """Backfill ``poster_url`` + ``overview`` for follows added before those columns.

    For each follow missing a poster and/or overview, searches the provider by
    title and takes ONLY the candidate whose provider id matches the follow's own
    id — a follow with no id-matched candidate is skipped, so a wrong poster is
    impossible. Idempotent (follows that already have both are untouched) and
    additive (``COALESCE`` never overwrites an existing value). Read-only under
    ``--dry-run``.
    """
    import json as _json
    import sqlite3

    from personalscraper.core.sqlite._pragmas import apply_pragmas
    from personalscraper.scraper.confidence import match_tvshow_detailed

    config = ctx.obj.config
    assert config is not None  # noqa: S101 — set by the CLI root callback
    console: Console = state["console"]
    settings = cli_compat.get_settings()
    db_path = config.acquire.db_path
    if db_path is None:
        console.print("[red]No acquire DB configured.[/red]")
        raise typer.Exit(1)

    with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
        registry = app_context.provider_registry
        tmdb_client = registry.get("tmdb")
        tvdb_client = registry.get("tvdb")

        conn = sqlite3.connect(str(db_path))
        apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
        try:
            # The poster_url/overview columns land with acquire migration 005; on a
            # DB still at an earlier version (e.g. prod before this feature merges)
            # this command is a clean no-op rather than an OperationalError.
            columns = {r[1] for r in conn.execute("PRAGMA table_info(followed_series)").fetchall()}
            if "poster_url" not in columns or "overview" not in columns:
                console.print(
                    "[yellow]followed_series has no poster_url/overview columns yet "
                    "(acquire migration 005 not applied) — nothing to backfill.[/yellow]"
                )
                return
            rows = conn.execute(
                "SELECT id, title, media_ref_json, poster_url, overview FROM followed_series"
            ).fetchall()
            updated = 0
            skipped = 0
            for row in rows:
                if row["poster_url"] and row["overview"]:
                    continue
                ref = _json.loads(row["media_ref_json"]) if row["media_ref_json"] else {}
                tvdb_id, tmdb_id = ref.get("tvdb_id"), ref.get("tmdb_id")
                # year is a migration-005 column too; search by title only (year is
                # an optional disambiguator) and match strictly by provider id.
                _, candidates = match_tvshow_detailed(tvdb_client, tmdb_client, row["title"], None)
                match = _candidate_matching_id(list(candidates), tvdb_id, tmdb_id)
                if match is None:
                    skipped += 1
                    log.info("cli.follow.backfill.no_id_match", followed_id=row["id"], title=row["title"])
                    continue
                new_poster = getattr(match, "poster_url", None) if not row["poster_url"] else None
                new_overview = getattr(match, "overview", None) if not row["overview"] else None
                if not new_poster and not new_overview:
                    skipped += 1
                    continue
                console.print(
                    f"[green]{row['title']}[/green] ← poster={'yes' if new_poster else '—'} "
                    f"overview={'yes' if new_overview else '—'}"
                )
                if not dry_run:
                    conn.execute(
                        "UPDATE followed_series SET poster_url = COALESCE(?, poster_url), "
                        "overview = COALESCE(?, overview) WHERE id = ?",
                        (new_poster, new_overview, row["id"]),
                    )
                    updated += 1
            if not dry_run:
                conn.commit()
            console.print(f"[bold]{'(dry-run) ' if dry_run else ''}Backfilled {updated}, skipped {skipped}.[/bold]")
        finally:
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
