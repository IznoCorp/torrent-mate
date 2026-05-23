"""Analysis Typer commands for the library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from personalscraper import cli as cli_compat
from personalscraper.cli_app import app
from personalscraper.cli_helpers import _resolve_category, handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.logger import get_logger

log = get_logger("cli")


@app.command()
@handle_cli_errors
def library_analyze(
    ctx: typer.Context,
    disk: str = typer.Option(None, "--disk", help="Analyze only this disk"),
    category: str = typer.Option(None, "--category", help="Analyze only this category"),
    max_items: int = typer.Option(None, "--max-items", help="Limit number of items to analyze"),
    from_index: bool = typer.Option(
        False,
        "--from-index",
        help=(
            "Read codec / audio / subtitle data from the indexer DB instead of "
            "running ffprobe per file. Requires a prior `library-index --mode enrich` "
            "pass; HDR / Atmos detection is approximated (see analyze_from_index docstring)."
        ),
    ),
) -> None:
    """Deep scan video files with ffprobe (codec, audio, subtitles) and print a summary.

    Most I/O-intensive command — schedule during off-peak hours. Use
    ``--from-index`` to read enrich-populated streams from the DB instead
    (orders of magnitude faster, with the documented HDR / Atmos caveats).

    The result set is **not persisted to disk**. ``library-recommend`` runs
    this scan inline before producing recommendations, so there is no need to
    call ``library-analyze`` first as a side-effect setup step.

    Examples:
        personalscraper library-analyze
        personalscraper library-analyze --disk <disk_id> --category series
        personalscraper library-analyze --max-items 50
        personalscraper library-analyze --from-index
    """
    from personalscraper.library.analyzer import analyze_from_index, analyze_library

    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    if from_index:
        console.print("[bold]Analyzing library (from index)...[/bold]")
        import sqlite3  # noqa: PLC0415

        from personalscraper.cli_helpers import _build_app_context  # noqa: PLC0415
        from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
        from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

        db_path = config.indexer.db_path
        migrations_dir = Path(_migrations_pkg.__file__).parent
        app_context = _build_app_context(config, cli_compat.get_settings())
        conn: sqlite3.Connection = open_db(db_path, event_bus=app_context.event_bus)
        apply_migrations(conn, migrations_dir)
        try:
            result = analyze_from_index(
                conn,
                disk_filter=disk,
                category_filter=category_id,
                max_items=max_items,
            )
        finally:
            conn.close()
    else:
        console.print("[bold]Analyzing library (ffprobe)...[/bold]")
        result = analyze_library(
            config,
            disk_filter=disk,
            category_filter=category_id,
            max_items=max_items,
        )

    # Aggregate codec / audio profile distributions for the summary.
    codec_counts: dict[str, int] = {}
    audio_counts: dict[str, int] = {}
    for item in result.items:
        for media_file in item.files:
            codec = media_file.video.codec or "unknown"
            codec_counts[codec] = codec_counts.get(codec, 0) + 1
            profile = media_file.audio_profile or "unknown"
            audio_counts[profile] = audio_counts.get(profile, 0) + 1

    console.print(f"[green]Analysis complete:[/green] {result.item_count} items, {result.file_count} files")
    if codec_counts:
        codecs = ", ".join(f"{c}={n}" for c, n in sorted(codec_counts.items(), key=lambda kv: -kv[1]))
        console.print(f"  Codecs: {codecs}")
    if audio_counts:
        audio = ", ".join(f"{p}={n}" for p, n in sorted(audio_counts.items(), key=lambda kv: -kv[1]))
        console.print(f"  Audio profiles: {audio}")


@app.command()
@handle_cli_errors
def library_recommend(
    ctx: typer.Context,
    sort: str = typer.Option("priority", "--sort", help="Sort by: priority, size, codec"),
    export: str = typer.Option(None, "--export", help="Export format: csv"),
    disk: str = typer.Option(None, "--disk", help="Filter to this disk"),
    category: str = typer.Option(None, "--category", help="Filter to this category"),
    from_index: bool = typer.Option(
        False,
        "--from-index",
        help=(
            "Read codec / audio / subtitle data from the indexer DB instead of "
            "running ffprobe per file. Requires a prior `library-index --mode enrich` "
            "pass."
        ),
    ),
) -> None:
    """Generate re-download recommendations from a fresh ffprobe analysis.

    Runs the ffprobe analysis inline (no on-disk cache) and feeds the
    in-memory result to the recommender.  Preferences come from
    ``config.library``.  Output is written to ``library_recommendations.json``.
    Pass ``--from-index`` to skip ffprobe and read streams from the indexer
    DB instead (orders of magnitude faster on a populated index).

    Examples:
        personalscraper library-recommend
        personalscraper library-recommend --sort size
        personalscraper library-recommend --export csv
        personalscraper library-recommend --from-index
    """
    import csv

    from personalscraper.library.analyzer import analyze_from_index, analyze_library
    from personalscraper.library.models import write_json
    from personalscraper.library.recommender import generate_recommendations

    # Resolve alias now so unknown --category values fail fast.
    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    # Validate --sort parameter
    valid_sorts = {"priority", "size", "codec"}
    if sort not in valid_sorts:
        console.print(f"[red]Invalid --sort value '{sort}'. Valid: {', '.join(sorted(valid_sorts))}[/red]")
        raise typer.Exit(1)

    if from_index:
        console.print("[bold]Analyzing library (from index)...[/bold]")
        import sqlite3  # noqa: PLC0415

        from personalscraper.cli_helpers import _build_app_context  # noqa: PLC0415
        from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
        from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

        db_path = config.indexer.db_path
        migrations_dir = Path(_migrations_pkg.__file__).parent
        app_context = _build_app_context(config, cli_compat.get_settings())
        conn: sqlite3.Connection = open_db(db_path, event_bus=app_context.event_bus)
        apply_migrations(conn, migrations_dir)
        try:
            analysis = analyze_from_index(
                conn,
                disk_filter=disk,
                category_filter=category_id,
            )
        finally:
            conn.close()
    else:
        # Run analysis inline; the indexer DB remains the source of truth.
        console.print("[bold]Analyzing library (ffprobe)...[/bold]")
        analysis = analyze_library(
            config,
            disk_filter=disk,
            category_filter=category_id,
        )

    # Use preferences from config.library (no separate file).
    prefs = config.library

    result = generate_recommendations(analysis.items, prefs)

    # Sort
    sort_keys = {
        "priority": lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.priority, 3),
        "size": lambda r: -(r.estimated_savings_gb or 0),
        "codec": lambda r: r.current.codec,
    }
    if sort in sort_keys:
        result.items.sort(key=sort_keys[sort])

    # Write JSON
    output_path = config.paths.data_dir / "library_recommendations.json"
    write_json(result, output_path)

    # CSV export
    if export == "csv":
        csv_path = config.paths.data_dir / "library_recommendations.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "title",
                    "type",
                    "disk",
                    "codec",
                    "resolution",
                    "size_gb",
                    "audio",
                    "priority",
                    "savings_gb",
                    "reasons",
                ]
            )
            for r in result.items:
                writer.writerow(
                    [
                        r.title,
                        r.media_type,
                        r.disk,
                        r.current.codec,
                        r.current.resolution,
                        f"{r.current.size_gb:.1f}",
                        r.current.audio_profile,
                        r.priority,
                        f"{r.estimated_savings_gb or 0:.1f}",
                        "; ".join(r.reasons),
                    ]
                )
        console.print(f"[green]CSV exported:[/green] {csv_path}")

    console.print(
        f"[green]Recommendations:[/green] {result.total_recommendations} items, "
        f"~{result.estimated_total_savings_gb:.1f} GB potential savings → {output_path}"
    )


@app.command()
@handle_cli_errors
def library_rescrape(
    ctx: typer.Context,
    only: str = typer.Option(None, "--only", help="Only fix: nfo, artwork, episodes"),
    disk: str = typer.Option(None, "--disk", help="Rescrape only this disk"),
    category: str = typer.Option(None, "--category", help="Rescrape only this category"),
    interactive: bool = typer.Option(False, "--interactive", help="Confirm low-confidence matches"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying files"),
    max_items: int = typer.Option(None, "--max-items", help="Limit number of items to process"),
) -> None:
    """Targeted re-scrape of library items via TMDB/TVDB.

    Only repairs what is broken per item: missing NFO, missing artwork,
    unrenamed episodes. Items already conforming are skipped.

    Examples:
        personalscraper library-rescrape --dry-run
        personalscraper library-rescrape --only artwork
        personalscraper library-rescrape --disk <disk_id> --max-items 50
        personalscraper library-rescrape --interactive
    """
    from personalscraper.library.models import write_json
    from personalscraper.library.rescraper import rescrape_library

    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config
    settings = cli_compat.get_settings()

    valid_only = {"nfo", "artwork", "episodes"}
    if only and only not in valid_only:
        console.print(f"[red]Invalid --only value '{only}'. Valid: {', '.join(sorted(valid_only))}[/red]")
        raise typer.Exit(1)

    if not dry_run:
        if not cli_compat.acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        mode = "[bold yellow]DRY-RUN[/bold yellow]" if dry_run else "[bold green]LIVE[/bold green]"
        console.print(f"[bold]Rescraping library ({mode})...[/bold]")

        from personalscraper.cli_helpers import per_step_boundary  # noqa: PLC0415

        with per_step_boundary(config, settings) as app_context:
            result = rescrape_library(
                config,
                settings,
                disk_filter=disk,
                category_filter=category_id,
                only=only,
                interactive=interactive,
                dry_run=dry_run,
                max_items=max_items,
                event_bus=app_context.event_bus,
            )

        output_path = config.paths.data_dir / "library_rescrape.json"
        write_json(result, output_path)

        total = result.fixed_count + result.skipped_count + result.error_count
        console.print(
            f"[green]Fixed:[/green] {result.fixed_count}  "
            f"[yellow]Skipped:[/yellow] {result.skipped_count}  "
            f"[red]Errors:[/red] {result.error_count}  "
            f"(total: {total}) → {output_path}"
        )
    finally:
        if not dry_run:
            cli_compat.release_lock()


@app.command()
@handle_cli_errors
def library_report(
    ctx: typer.Context,
) -> None:
    """Display library statistics and health report.

    Aggregates data from the indexer DB (totals, NFO / artwork health, disk
    distribution, per-item sizes) and supplementary JSON outputs from
    ``library-validate``, ``library-recommend``, and ``library-rescrape``.
    Output format respects the global ``--format`` flag.

    Examples:
        personalscraper library-report
        personalscraper --format json library-report
    """
    import dataclasses

    from personalscraper.cli_helpers.output import emit  # noqa: PLC0415
    from personalscraper.dispatch.disk_scanner import get_disk_status
    from personalscraper.indexer.db import open_db
    from personalscraper.library.analyzer import analyze
    from personalscraper.library.models import read_json
    from personalscraper.library.reporter import format_report_text, generate_report

    config = ctx.obj.config
    console = state["console"]

    # Load supplementary JSON outputs (validation, recommendations, rescrape).
    def _load(name: str) -> dict[str, Any] | None:
        path = config.paths.data_dir / name
        if path.exists():
            try:
                return read_json(path)
            except (OSError, ValueError) as exc:
                log.warning("report_data_load_failed", file=name, error=str(exc))
                console.print(f"[yellow]Warning: {name} corrupted ({exc}), skipping.[/yellow]")
                return None
        return None

    validation_data = _load("library_validation.json")
    recommendation_data = _load("library_recommendations.json")
    rescrape_data = _load("library_rescrape.json")

    # Query the indexer DB for totals, NFO / artwork health, disk distribution.
    db_path = config.indexer.db_path
    analysis_result = None
    if db_path.exists():
        try:
            from personalscraper.cli_helpers import _build_app_context  # noqa: PLC0415

            _app_context = _build_app_context(config, cli_compat.get_settings())
            conn = open_db(db_path, event_bus=_app_context.event_bus)
            analysis_result = analyze(conn)
            conn.close()
        except Exception as exc:
            log.warning("report_indexer_query_failed", error=str(exc))
            console.print(f"[yellow]Warning: indexer DB query failed ({exc}), skipping analysis.[/yellow]")

    if not any([analysis_result, validation_data, recommendation_data, rescrape_data]):
        emit("No library data found. Run library-index first.")
        raise typer.Exit(1)

    # Get live disk free space
    disk_statuses = [get_disk_status(dc) for dc in config.disks]

    report = generate_report(
        analysis_result,
        validation_data,
        recommendation_data,
        disk_statuses=disk_statuses,
        rescrape_data=rescrape_data,
    )

    emit(
        dataclasses.asdict(report),
        rich_renderer=lambda: console.print(format_report_text(report)),
    )
