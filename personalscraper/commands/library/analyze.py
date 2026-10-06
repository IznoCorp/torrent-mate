"""Analysis Typer commands for the library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from personalscraper import cli_helpers
from personalscraper.cli_app import app
from personalscraper.cli_helpers import CommandContext, _resolve_category, boundary, handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.i18n import Language, t
from personalscraper.logger import get_logger

log = get_logger("cli")


@app.command(help=t("cli_library.analyze.analyze_help", disk_id="<disk_id>", bold="**"))
@handle_cli_errors
@boundary(needs="config", staging=False)
def library_analyze(
    ctx: typer.Context,
    disk: str = typer.Option(None, "--disk", help=t("cli_library.analyze.disk_help")),
    category: str = typer.Option(None, "--category", help=t("cli_library.analyze.category_help")),
    max_items: int = typer.Option(None, "--max-items", help=t("cli_library.analyze.max_items_help")),
    from_index: bool = typer.Option(
        True,
        "--from-index/--no-from-index",
        help=t("cli_library.analyze.from_index_help"),
    ),
    *,
    bundle: CommandContext,
) -> None:
    """Summarize codec / audio / subtitle data read from the indexer DB.

    Reads the ``media_stream`` rows populated by the enrich pass — requires a
    prior ``library-index --mode enrich`` run. No ffprobe is launched and no
    filesystem walk happens (the legacy inline ffprobe re-scan was removed in
    favour of the single enrich-backed stream reader). HDR / Atmos detection
    reflects whatever the enrich pass persisted (see the
    ``analyze_from_index`` docstring for the per-field caveats).

    The result set is **not persisted to disk**. ``library-recommend`` runs
    this analysis inline before producing recommendations, so there is no need
    to call ``library-analyze`` first as a side-effect setup step.

    The ``--from-index`` flag is a deprecated no-op (always on) kept for
    back-compat.

    Examples:
        personalscraper library-analyze
        personalscraper library-analyze --disk <disk_id> --category series
        personalscraper library-analyze --max-items 50
    """
    import sqlite3  # noqa: PLC0415

    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415
    from personalscraper.insights.analytics import analyze_from_index  # noqa: PLC0415

    # ``from_index`` is accepted but ignored — the DB is the sole source.
    _ = from_index

    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    console.print("[bold]" + t("cli_library.analyze.analyzing") + "[/bold]")
    db_path = config.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent
    conn: sqlite3.Connection = open_db(db_path, event_bus=bundle.event_bus)
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

    # Aggregate codec / audio profile distributions for the summary.
    codec_counts: dict[str, int] = {}
    audio_counts: dict[str, int] = {}
    for item in result.items:
        for media_file in item.files:
            codec = media_file.video.codec or "unknown"
            codec_counts[codec] = codec_counts.get(codec, 0) + 1
            profile = media_file.audio_profile or "unknown"
            audio_counts[profile] = audio_counts.get(profile, 0) + 1

    console.print(
        "[green]"
        + t("cli_library.analyze.analysis_complete_label")
        + "[/green] "
        + t("cli_library.analyze.analysis_counts", items=result.item_count, files=result.file_count)
    )
    if result.item_count == 0:
        # No enriched media streams in the DB. The most common cause is that
        # ``library-index --mode enrich`` was never run (Stage A only), so the
        # ``media_stream`` rows the analysis reads do not exist yet. Surface an
        # explicit hint (mirrors the ``library_report`` no-data guidance)
        # instead of leaving the operator with a silent "0 items, 0 files".
        console.print("[yellow]" + t("cli_library.analyze.no_enriched_streams") + "[/yellow]")
    if codec_counts:
        codecs = ", ".join(f"{c}={n}" for c, n in sorted(codec_counts.items(), key=lambda kv: -kv[1]))
        console.print(t("cli_library.analyze.codecs_line", codecs=codecs))
    if audio_counts:
        audio = ", ".join(f"{p}={n}" for p, n in sorted(audio_counts.items(), key=lambda kv: -kv[1]))
        console.print(t("cli_library.analyze.audio_profiles_line", profiles=audio))


@app.command(help=t("cli_library.analyze.recommend_help"))
@handle_cli_errors
@boundary(needs="config", staging=False)
def library_recommend(
    ctx: typer.Context,
    sort: str = typer.Option("priority", "--sort", help=t("cli_library.analyze.sort_help")),
    export: str = typer.Option(None, "--export", help=t("cli_library.analyze.export_help")),
    disk: str = typer.Option(None, "--disk", help=t("cli_library.analyze.filter_disk_help")),
    category: str = typer.Option(None, "--category", help=t("cli_library.analyze.filter_category_help")),
    from_index: bool = typer.Option(
        True,
        "--from-index/--no-from-index",
        help=t("cli_library.analyze.recommend_from_index_help"),
    ),
    *,
    bundle: CommandContext,
) -> None:
    """Generate re-download recommendations from the indexer DB.

    Reads the ``media_stream`` rows populated by the enrich pass — requires a
    prior ``library-index --mode enrich`` run — and feeds the in-memory
    analysis to the recommender. No ffprobe is launched and no filesystem walk
    happens (the legacy inline ffprobe re-scan was removed). Preferences come
    from ``config.library``. Output is written to
    ``library_recommendations.json``.

    The ``--from-index`` flag is a deprecated no-op (always on) kept for
    back-compat.

    Examples:
        personalscraper library-recommend
        personalscraper library-recommend --sort size
        personalscraper library-recommend --export csv
    """
    import csv
    import sqlite3  # noqa: PLC0415

    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415
    from personalscraper.insights.analytics import analyze_from_index  # noqa: PLC0415
    from personalscraper.insights.recommender import generate_recommendations  # noqa: PLC0415
    from personalscraper.io_utils import write_json  # noqa: PLC0415

    # ``from_index`` is accepted but ignored — the DB is the sole source.
    _ = from_index

    # Resolve alias now so unknown --category values fail fast.
    category_id = _resolve_category(ctx, category)
    console = state["console"]
    config = ctx.obj.config

    # Validate --sort parameter
    valid_sorts = {"priority", "size", "codec"}
    if sort not in valid_sorts:
        console.print(
            "[red]" + t("cli_library.analyze.invalid_sort", value=sort, valid=", ".join(sorted(valid_sorts))) + "[/red]"
        )
        raise typer.Exit(1)

    console.print("[bold]" + t("cli_library.analyze.analyzing") + "[/bold]")
    db_path = config.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent
    conn: sqlite3.Connection = open_db(db_path, event_bus=bundle.event_bus)
    apply_migrations(conn, migrations_dir)
    try:
        analysis = analyze_from_index(
            conn,
            disk_filter=disk,
            category_filter=category_id,
        )
    finally:
        conn.close()

    if analysis.item_count == 0:
        # Same no-enrich guidance as ``library-analyze``: recommendations are
        # derived from enriched media streams, so an empty analysis means
        # ``library-index --mode enrich`` has not populated ``media_stream``.
        console.print("[yellow]" + t("cli_library.analyze.no_enriched_streams") + "[/yellow]")

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
        console.print("[green]" + t("cli_library.analyze.csv_exported_label") + "[/green] " + str(csv_path))

    console.print(
        "[green]"
        + t("cli_library.analyze.recommendations_label")
        + "[/green] "
        + t(
            "cli_library.analyze.recommendations_summary",
            items=result.total_recommendations,
            savings=f"{result.estimated_total_savings_gb:.1f}",
            path=output_path,
        )
    )


@app.command(help=t("cli_library.analyze.rescrape_help", disk_id="<disk_id>"))
@handle_cli_errors
def library_rescrape(
    ctx: typer.Context,
    only: str = typer.Option(None, "--only", help=t("cli_library.analyze.only_help")),
    disk: str = typer.Option(None, "--disk", help=t("cli_library.analyze.rescrape_disk_help")),
    category: str = typer.Option(None, "--category", help=t("cli_library.analyze.rescrape_category_help")),
    interactive: bool = typer.Option(False, "--interactive", help=t("cli_library.analyze.interactive_help")),
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_library.analyze.dry_run_help")),
    max_items: int = typer.Option(None, "--max-items", help=t("cli_library.analyze.max_items_rescrape_help")),
    item_id: int = typer.Option(None, "--item-id", help=t("cli_library.analyze.item_id_help")),
) -> None:
    """Targeted re-scrape of library items via TMDB/TVDB.

    Only repairs what is broken per item: missing NFO, missing artwork,
    unrenamed episodes. Items already conforming are skipped.

    When ``--item-id`` is given, exactly that item is targeted by indexer DB
    look-up, bypassing the needs-rescrape predicate so that items with a
    valid NFO can still be force-rescraped.  Requires the indexer DB to be
    configured.  Mutually exclusive with ``--disk`` and ``--category``.

    Examples:
        personalscraper library-rescrape --dry-run
        personalscraper library-rescrape --only artwork
        personalscraper library-rescrape --disk <disk_id> --max-items 50
        personalscraper library-rescrape --interactive
        personalscraper library-rescrape --item-id 1600
    """
    _rescrape(
        ctx,
        command="library-rescrape",
        only=only,
        disk=disk,
        category_id=_resolve_category(ctx, category),
        interactive=interactive,
        dry_run=dry_run,
        max_items=max_items,
        item_id=item_id,
        write_report=True,
    )


@app.command(help=t("cli_library.analyze.rescrape_item_help"))
@handle_cli_errors
def library_rescrape_item(
    ctx: typer.Context,
    item_id: int = typer.Argument(..., help=t("cli_library.analyze.rescrape_item_id_help")),
) -> None:
    """Re-scrape exactly one library item via TMDB/TVDB, live.

    The per-medium twin of ``library-rescrape --item-id``: no dry run, no filter,
    the needs-rescrape predicate bypassed. It takes ``pipeline.lock`` itself (exit 3
    when held, the code the maintenance runner re-queues on).

    Examples:
        personalscraper library-rescrape-item 1600
    """
    from personalscraper.app.supervisor.execution import rescrape_item  # noqa: PLC0415
    from personalscraper.cli_helpers import per_step_boundary  # noqa: PLC0415
    from personalscraper.commands._cli_run_row import cli_run_row  # noqa: PLC0415

    console = state["console"]
    config = ctx.obj.config
    settings = cli_helpers.get_settings()

    # Guard: the item look-up requires a configured and reachable indexer DB.
    db_path = config.indexer.db_path
    if not db_path.exists():
        console.print("[red]" + t("cli_library.analyze.indexer_db_missing", path=db_path) + "[/red]")
        raise typer.Exit(1)

    if not cli_helpers.acquire_pipeline_lock(
        config.paths.data_dir / "pipeline.lock",
        cli_helpers.scrape_locks_dir_for(config.paths.data_dir),
    ):
        # Exit 3 = lock busy (the maintenance runner re-queues on this code).
        console.print("[red]" + t("cli_library.analyze.lock_busy") + "[/red]")
        raise typer.Exit(3)

    try:
        code = rescrape_item(
            config,
            settings,
            item_id,
            console=console,
            run_row=cli_run_row,
            step_boundary=per_step_boundary,
        )
        if code:
            raise typer.Exit(code)
    finally:
        cli_helpers.release_lock()


def _rescrape(
    ctx: typer.Context,
    *,
    command: str,
    only: str | None,
    disk: str | None,
    category_id: str | None,
    interactive: bool,
    dry_run: bool,
    max_items: int | None,
    item_id: int | None,
    write_report: bool,
) -> None:
    """Run a library re-scrape under ``pipeline.lock`` and report it.

    Args:
        ctx: The Typer context (its ``obj.config``).
        command: The CLI command name the run row is recorded under.
        only: Restrict to ``nfo``, ``artwork`` or ``episodes``; ``None`` for all.
        disk: Restrict to this disk id.
        category_id: Restrict to this resolved category id.
        interactive: Confirm low-confidence matches.
        dry_run: Preview without modifying files (no lock, no run row).
        max_items: Limit the number of items processed.
        item_id: Target exactly this indexer item, bypassing the needs-rescrape predicate.
        write_report: Write ``library_rescrape.json``, the library-wide report
            ``library-report`` and the insights read; a per-medium rescrape leaves it alone.

    Raises:
        typer.Exit: 1 on a bad option, an unreachable index or an unresolved item;
            3 when ``pipeline.lock`` is held.
    """
    import sqlite3  # noqa: PLC0415

    from personalscraper.io_utils import write_json
    from personalscraper.maintenance.rescraper import rescrape_library

    console = state["console"]
    config = ctx.obj.config
    settings = cli_helpers.get_settings()

    valid_only = {"nfo", "artwork", "episodes"}
    if only and only not in valid_only:
        console.print(
            "[red]" + t("cli_library.analyze.invalid_only", value=only, valid=", ".join(sorted(valid_only))) + "[/red]"
        )
        raise typer.Exit(1)

    # Guard: --item-id requires a configured and reachable indexer DB.
    if item_id is not None:
        db_path = config.indexer.db_path
        if not db_path.exists():
            console.print("[red]" + t("cli_library.analyze.indexer_db_missing", path=db_path) + "[/red]")
            raise typer.Exit(1)

    if not dry_run:
        if not cli_helpers.acquire_pipeline_lock(
            config.paths.data_dir / "pipeline.lock",
            cli_helpers.scrape_locks_dir_for(config.paths.data_dir),
        ):
            # Exit 3 = lock busy (the maintenance runner re-queues on this code).
            console.print("[red]" + t("cli_library.analyze.lock_busy") + "[/red]")
            raise typer.Exit(3)

    try:
        mode = (
            "[bold yellow]" + t("cli_library.analyze.mode_dry_run") + "[/bold yellow]"
            if dry_run
            else "[bold green]" + t("cli_library.analyze.mode_live") + "[/bold green]"
        )
        console.print("[bold]" + t("cli_library.analyze.rescraping", mode=mode) + "[/bold]")

        from contextlib import nullcontext  # noqa: PLC0415

        from personalscraper.cli_helpers import per_step_boundary  # noqa: PLC0415
        from personalscraper.commands._cli_run_row import cli_run_row  # noqa: PLC0415

        # §1/§2 — the repair run is OBSERVABLE: a pipeline_run row (kind
        # maintenance) carries its numeric result, incl. how many items got
        # their artwork back (« Posters récupérés »). Dry-runs stay silent.
        run_row_cm = cli_run_row(config, command) if not dry_run else nullcontext(None)
        with run_row_cm as run_rec, per_step_boundary(config, settings) as app_context:
            # Open the indexer DB connection when item_id is provided so that
            # _collect_rescrape_candidates can look up the item by id.  The
            # connection is closed in the finally block below to avoid leaks.
            conn: sqlite3.Connection | None = None
            if item_id is not None:
                from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
                from personalscraper.indexer.db import (  # noqa: PLC0415
                    IndexerCorruptError,
                    IndexerDiskFullError,
                    IndexerInvalidPathError,
                    IndexerMigrationError,
                    apply_migrations,
                    open_db,
                )

                try:
                    conn = open_db(config.indexer.db_path, event_bus=app_context.event_bus)
                    apply_migrations(conn, Path(_migrations_pkg.__file__).parent)
                except (
                    IndexerCorruptError,
                    IndexerInvalidPathError,
                    IndexerDiskFullError,
                    IndexerMigrationError,
                ) as exc:
                    console.print("[red]" + t("cli_library.analyze.open_failed_label") + "[/red] " + str(exc))
                    if conn is not None:
                        conn.close()
                    raise typer.Exit(1) from exc

            try:
                result = rescrape_library(
                    config,
                    conn=conn,
                    disk_filter=disk,
                    category_filter=category_id,
                    item_id=item_id,
                    only=only,
                    interactive=interactive,
                    dry_run=dry_run,
                    max_items=max_items,
                    event_bus=app_context.event_bus,
                    registry=app_context.provider_registry,
                )
            except ValueError as exc:
                # Mutual-exclusion error from _collect_rescrape_candidates
                # (item_id combined with disk/category filter).
                console.print("[red]" + t("cli_library.analyze.invalid_combination_label") + "[/red] " + str(exc))
                raise typer.Exit(1) from exc
            finally:
                if conn is not None:
                    conn.close()

            # Warn clearly only when an explicit --item-id RESOLVED no candidate
            # (item not in DB, dispatch path missing, or directory gone). Gate on
            # candidate_count, NOT on fixed+skipped+error: an item that is found
            # but has nothing to do (e.g. --only artwork when artwork is already
            # present) legitimately produces 0 work and must NOT be reported as
            # not-found. Soft-skips in the bulk path are intentional.
            if item_id is not None and result.candidate_count == 0:
                console.print(
                    t(
                        "cli_library.analyze.item_not_found",
                        label="[yellow]" + t("cli_library.analyze.warning_label") + "[/yellow]",
                        item_id=item_id,
                    )
                )
                raise typer.Exit(1)

            if run_rec is not None:
                artwork_recovered = sum(1 for action in result.items if "artwork_downloaded" in action.actions_taken)
                run_rec.record_counts(
                    {
                        "fixed": result.fixed_count,
                        "skipped": result.skipped_count,
                        "errors": result.error_count,
                        "artwork_recovered": artwork_recovered,
                    }
                )

        total = result.fixed_count + result.skipped_count + result.error_count
        summary = t(
            "cli_library.analyze.rescrape_summary",
            fixed_label="[green]" + t("cli_library.analyze.fixed_label") + "[/green]",
            fixed=result.fixed_count,
            skipped_label="[yellow]" + t("cli_library.analyze.skipped_label") + "[/yellow]",
            skipped=result.skipped_count,
            errors_label="[red]" + t("cli_library.analyze.errors_label") + "[/red]",
            errors=result.error_count,
            total=t("cli_library.analyze.total", total=total),
        )
        if write_report:
            output_path = config.paths.data_dir / "library_rescrape.json"
            write_json(result, output_path)
            summary += f" → {output_path}"
        console.print(summary)
    finally:
        if not dry_run:
            cli_helpers.release_lock()


@app.command(help=t("cli_library.analyze.report_help"))
@handle_cli_errors
@boundary(needs="config", staging=False)
def library_report(
    ctx: typer.Context,
    *,
    bundle: CommandContext,
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
    from personalscraper.insights.analytics import analyze
    from personalscraper.insights.reporter import format_report_text, generate_report
    from personalscraper.io_utils import read_json

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
                console.print(
                    "[yellow]" + t("cli_library.analyze.report_data_corrupted", name=name, error=str(exc)) + "[/yellow]"
                )
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
            conn = open_db(db_path, event_bus=bundle.event_bus)
            analysis_result = analyze(conn)
            conn.close()
        except Exception as exc:
            log.warning("report_indexer_query_failed", error=str(exc))
            console.print("[yellow]" + t("cli_library.analyze.report_query_failed", error=str(exc)) + "[/yellow]")

    if not any([analysis_result, validation_data, recommendation_data, rescrape_data]):
        # A JSON payload is a machine value: it stays English whatever the language; only the other formats speak it.
        emit(t("cli_library.analyze.no_library_data", language=Language.EN if state["format"] == "json" else None))
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

    # Defer ``asdict`` evaluation: rich mode never needs the dict and the
    # report may be a non-dataclass MagicMock in unit tests.
    if state["format"] == "rich":
        console.print(format_report_text(report))
    else:
        emit(dataclasses.asdict(report))
