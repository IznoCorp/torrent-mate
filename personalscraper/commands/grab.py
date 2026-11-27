"""CLI command: ``personalscraper grab`` — batch acquisition run (RP5b).

Drives ``AcquisitionService.run()`` over the pending wanted queue.
``--dry-run`` searches + filters + ranks but never fetches or adds.
``--limit N`` caps the number of items attempted in one run.

Registered against the shared Typer ``app`` (imported side-effect in cli.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from rich.console import Console

from personalscraper import cli_helpers
from personalscraper.app.supervisor.acquisition_execution import grab_counts
from personalscraper.app.supervisor.model import JobKind
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import (
    handle_cli_errors,
    per_step_boundary,
)
from personalscraper.cli_state import state
from personalscraper.commands import acquisition_queue
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.commands.acquisition_surroundings import (
    build_acq_telegram_subscriber as _build_acq_telegram_subscriber,
)
from personalscraper.commands.acquisition_surroundings import reconcile_before_run as _reconcile_before_run
from personalscraper.commands.acquisition_surroundings import reswitch_before_run as _reswitch_before_run
from personalscraper.i18n import t
from personalscraper.subscribers.redis_stream import build_redis_publisher

if TYPE_CHECKING:
    from collections.abc import Mapping

    from personalscraper.acquire.context import AcquireContext
    from personalscraper.api.tracker._base import TrackerResult
    from personalscraper.conf.models.api_config import TrackerProviderConfig
    from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber


@command_with_telemetry("grab", help=t("cli_acquisition.grab.help"))
@handle_cli_errors
def grab(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=t("cli_acquisition.grab.dry_run_help"),
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help=t("cli_acquisition.grab.limit_help"),
    ),
    followed_id: int | None = typer.Option(
        None,
        "--followed-id",
        help=t("cli_acquisition.grab.followed_id_help"),
    ),
) -> None:
    """Run the grab loop — search trackers and add top-ranked torrents.

    While a supervisor's lease is live the pass is asked through the queue and followed instead
    (:mod:`personalscraper.commands.acquisition_queue`); ``--dry-run`` always runs here.
    """
    config = ctx.obj.config
    assert config is not None  # guaranteed by callback
    console = state["console"]

    if not dry_run and acquisition_queue.supervised(config, console):
        acquisition_queue.queue_pass(config, console, JobKind.GRAB, followed_id=followed_id, limit=limit)
        return

    settings = cli_helpers.get_settings()
    with (
        cli_run_row(config, "grab") as run_rec,
        per_step_boundary(config, settings, build_torrent_client=not dry_run) as app_context,
    ):
        redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
        # D8 — the reconcile pass below emits DownloadCompleted; without this
        # subscriber the event had no Telegram consumer on the grab path (the
        # pipeline command wires it, but never calls reconcile_wanted). Built
        # INSIDE the try (pipeline.py pattern) so a construction failure still
        # reaches the finally and closes the redis publisher.
        acq_telegram_subscriber: AcquisitionTelegramSubscriber | None = None
        try:
            acq_telegram_subscriber = _build_acq_telegram_subscriber(config, settings, app_context.event_bus)
            acquire = app_context.acquire
            if acquire is None:
                msg = t("cli_acquisition.grab.no_context")
                console.print("[red]" + msg + "[/red]")
                raise typer.Exit(1)

            if dry_run:
                _run_dry(
                    acquire, console, limit=limit, followed_id=followed_id, tracker_providers=config.tracker.providers
                )
            else:
                grab_core = acquire.grab
                if grab_core is None:
                    msg = t("cli_acquisition.grab.no_client")
                    console.print("[red]" + msg + "[/red]")
                    raise typer.Exit(1)

                # P0-B.3 — reconcile grabbed rows BEFORE searching: rows whose
                # work the library owns close ``done``; rows whose torrent
                # vanished from the client (and are unowned) requeue pending
                # and re-enter this very run's queue.
                reconcile = _reconcile_before_run(
                    acquire, app_context.event_bus, console, scope=config.torrent.active_scope()
                )

                # reswitch #342 — AFTER reconcile (review ordering note): reconcile
                # closes library-owned rows to ``done`` first, so reswitch only
                # acts on rows that are genuinely still downloading. For each
                # dead-stalled grab (dead swarm / broken / stuck past the deadline)
                # the dead torrent is removed and the row requeued with the failed
                # hash remembered, so the next search+grab picks a DIFFERENT
                # release. A vanished torrent is left to reconcile.
                _reswitch_before_run(acquire, app_context.event_bus, console, scope=config.torrent.active_scope())

                summary = grab_core.service.run(limit=limit, followed_id=followed_id, run_uid=run_rec.run_uid)
                counts = t(
                    "cli_acquisition.grab.complete_counts",
                    grabbed=summary.grabbed,
                    retried=summary.retried,
                    abandoned=summary.abandoned,
                    absorbed=summary.absorbed,
                    skipped=summary.skipped,
                )
                console.print("[green]" + t("cli_acquisition.grab.complete_label") + "[/green] " + counts)
                # §5 « résultat chiffré »: persist the run's numbers on its
                # pipeline_run row (self-owned for cron/CLI; the web runner's
                # row when spawned by POST /followed/{id}/search).
                run_rec.record_counts(grab_counts(summary, reconcile))
        finally:
            if acq_telegram_subscriber is not None:
                acq_telegram_subscriber.close()
            if redis_publisher is not None:
                redis_publisher.close()


def _run_dry(
    acquire: AcquireContext,
    console: Console,
    *,
    limit: int | None,
    followed_id: int | None = None,
    tracker_providers: Mapping[str, TrackerProviderConfig] | None = None,
) -> None:
    """Dry-run: search + filter + dedup + rank, print top candidates. No add.

    Args:
        acquire: :class:`~personalscraper.acquire.context.AcquireContext`.
        console: Rich Console for output.
        limit: Max items to inspect.
        followed_id: When set, restrict the dry-run to one followed series'
            pending items (mirrors the real run's OBJ3 per-series scoping).
        tracker_providers: The configured trackers (``config.tracker.providers``), whose
            ``economy`` blocks give each tracker's ratio standing, as the real grab reads it
            (F4). ``None`` or empty leaves every standing ``None``.
    """
    from personalscraper.api._contracts import MediaType  # noqa: PLC0415

    store = acquire.store
    if store is None:
        msg = t("cli_acquisition.grab.dry_run_no_store")
        console.print("[yellow]" + msg + "[/yellow]")
        return

    pending = store.wanted.list_pending()
    if followed_id is not None:
        pending = [item for item in pending if item.followed_id == followed_id]
    if limit is not None:
        pending = pending[:limit]

    if not pending:
        msg = t("cli_acquisition.grab.dry_run_empty")
        console.print("[yellow]" + msg + "[/yellow]")
        return

    from personalscraper.acquire.orchestrator import build_search_query, rank_candidates  # noqa: PLC0415
    from personalscraper.acquire.standing import RatioStanding, tracker_economies  # noqa: PLC0415
    from personalscraper.core._contracts import CircuitOpenError  # noqa: PLC0415

    standing = RatioStanding(store.ratio, tracker_economies(tracker_providers or {}))
    registry = acquire.tracker_registry
    for item in pending:
        item_line = f"{item.media_ref} ({item.kind})"
        console.print("\n[bold]" + t("cli_acquisition.grab.item_label") + "[/bold] " + item_line)
        # A `season` row is TV too — it was classified as MOVIE here while the
        # orchestrator (orchestrator.py) says `in ("episode", "season")`. The
        # preview therefore hit the movie endpoint AND, once the year stopped
        # being appended to TV queries, kept appending it to season queries:
        # exactly the « … S01 2025 » → 0 result that stranded Pan Am 103.
        media_type = MediaType.TV if item.kind in ("episode", "season") else MediaType.MOVIE
        # Follow D3: same title + year resolution as the real grab (see
        # build_search_query) so the preview reflects the ACTUAL query the
        # trackers receive — for a movie that means « {title} {year} » (#28,
        # review F4: a preview that ranks a different film than the grab is a lie).
        title = None
        year: int | None = None
        original_title = None
        if item.followed_id is not None:
            row = store.follow.get(item.followed_id)
            if row is not None:
                title = row.title
                year = row.year
                original_title = row.original_title
        # #435 — mirror the real grab's original-title retry: a fruitless
        # display-title query replays once in the original language, so the
        # preview reflects the SAME candidates the grab would rank (review F4:
        # a preview that diverges from the run is a lie).
        queries = [build_search_query(item, title, year)]
        if original_title and original_title != title:
            queries.append(build_search_query(item, original_title, year))
        results: list[TrackerResult] | None = None
        circuit_open = False
        for attempt_no, attempt_query in enumerate(queries):
            try:
                outcome = registry.search_candidates(attempt_query, media_type, year)
            except CircuitOpenError:
                # A dead tracker's OPEN circuit must not crash the preview (the
                # real grab already catches this in the orchestrator).
                console.print("  [yellow]" + t("cli_acquisition.grab.circuit_open") + "[/yellow]")
                circuit_open = True
                break
            label = (
                t("cli_acquisition.grab.attempt_search") if attempt_no == 0 else t("cli_acquisition.grab.attempt_retry")
            )
            attempt = t(
                "cli_acquisition.grab.attempt_line",
                label=label,
                results=len(outcome.results),
                queried=outcome.trackers_queried,
                errored=outcome.trackers_errored,
            )
            console.print("  " + attempt)
            if not outcome.results:
                continue

            # Episode-exactness: mirror the real grab so the preview's Top is
            # the actual episode, not a fuzzy same-show match.
            narrowed = outcome.results
            if item.kind == "episode" and item.season is not None and item.episode is not None:
                from personalscraper.acquire.orchestrator import filter_to_episode  # noqa: PLC0415

                narrowed = filter_to_episode(narrowed, item.season, item.episode, titles=[title, original_title])
            elif item.kind == "season" and item.season is not None:
                # Mirror the real grab's season narrowing (#489 identity guard
                # + F4 coverage): a wrong-show pack must not green-light in the
                # preview while the run would drop it — the same lie F4 is about.
                from personalscraper.acquire.orchestrator import filter_to_season  # noqa: PLC0415

                expected_count = None
                if item.followed_id is not None:
                    aired = store.aired.list_for_followed(item.followed_id)
                    expected_count = len([r for r in aired if r.season == item.season]) or None
                narrowed = filter_to_season(
                    narrowed, item.season, expected_count=expected_count, titles=[title, original_title]
                )
            elif item.kind == "movie" and title is not None:
                # #28 (review F4) — mirror the real grab's movie identity filter
                # so the preview's Top is the SAME film the grab would take, not
                # a higher-seeded « Wicker* » of a different year. Every known
                # title (#435): a release named in the original language must
                # survive here exactly as it does in the real grab.
                from personalscraper.acquire.orchestrator import filter_to_movie  # noqa: PLC0415

                narrowed = filter_to_movie(narrowed, [title, original_title], year)
            if narrowed:
                results = narrowed
                break
        if circuit_open:
            continue
        if not results:
            console.print("  [yellow]" + t("cli_acquisition.grab.no_match") + "[/yellow]")
            continue

        # Resolve the SAME effective profile the real grab uses (series
        # quality_profile_json overlaid with item criteria) and pass the
        # media_ref for TMDB-identity parity — otherwise the preview's Top can
        # diverge from the real run for a series with a custom profile
        # (exclude_3d=False, min_resolution, required_audio).
        from personalscraper.acquire.service import resolve_effective_profile  # noqa: PLC0415

        profile = resolve_effective_profile(store, item)
        # F4: run the SAME hard-filter → dedup → rank tail the real grab runs
        # (rank_candidates), with the SAME ranking source (config.ranking, held
        # by the registry). The old preview printed dedup[0] — the UNRANKED first
        # candidate — so the operator validated a decision the real run would
        # never make (a lower-seeder / wrong-variant release); the dry-run-first
        # rule needs the Top to be the actual ranked winner, rank[0].
        # The SAME standing the real grab's orchestrator reads (``RatioStanding`` over the
        # same tracker economies): without it a criterion on ``tracker_ratio_state`` would
        # score 0 here and the Top could differ.
        representatives, ranked = rank_candidates(
            results,
            profile,
            item.media_ref,
            registry.ranking,
            tracker_ratio_state_of=standing.of,
        )
        console.print("  " + t("cli_acquisition.grab.after_filter", candidates=len(representatives)))
        if not representatives:
            console.print("  [yellow]" + t("cli_acquisition.grab.all_filtered") + "[/yellow]")
            continue
        if not ranked:
            # Survivors exist but none meets min_seeders — the real grab returns
            # no_seeders (retryable), so there is no candidate to act on today.
            console.print("  [yellow]" + t("cli_acquisition.grab.no_seeders") + "[/yellow]")
            continue
        top, _score = ranked[0]
        top_line = t(
            "cli_acquisition.grab.top_line",
            provider=top.provider,
            title=top.title,
            seeders=top.seeders,
            resolution=str(top.resolution),
        )
        console.print("  [green]" + t("cli_acquisition.grab.top_label") + "[/green] " + top_line)
