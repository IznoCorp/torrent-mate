"""Pipeline-related Typer commands."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import typer

from personalscraper import cli_helpers
from personalscraper.app.supervisor.execution import RunOptions, execute_run
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import (
    CommandContext,
    boundary,
    handle_cli_errors,
)
from personalscraper.cli_state import state
from personalscraper.conf.staging import find_ingest_dir, staging_path
from personalscraper.i18n import t, t_code
from personalscraper.logger import get_logger
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.pipeline_step_codes import StepCode

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.models import StepReport
    from personalscraper.verify.checks.base import CheckSpec


def _journal_lock_conflict(config: Config, *, dry_run: bool) -> None:
    """R9: leave a terminal ``pipeline_run`` row when a run loses the lock race.

    The web ``POST /api/pipeline/run`` returns a ``run_uid`` in its 202 *before*
    the spawned ``personalscraper run`` subprocess acquires ``pipeline.lock``. If
    that subprocess loses the race it exits here without writing any row, so
    ``GET /api/pipeline/history/{run_uid}`` would 404 forever (orphan run_uid).

    When a web run_uid was injected via ``PERSONALSCRAPER_RUN_UID``, write a
    terminal ``error`` row for it so the identifier always resolves. Fail-soft:
    journaling a lock conflict must never change the exit behaviour.

    Args:
        config: The active configuration (for ``indexer.db_path``).
        dry_run: Whether the losing run was a dry run (recorded on the row).
    """
    run_uid = os.environ.get("PERSONALSCRAPER_RUN_UID")
    if not run_uid:
        return
    db_path = config.indexer.db_path
    if db_path is None:
        return
    log = get_logger("pipeline")
    try:
        writer = PipelineRunWriter(db_path)
        writer.insert(run_uid, trigger="web", dry_run=dry_run, pid=os.getpid(), if_absent=True)
        writer.finalize(
            run_uid,
            "error",
            # Stored in a DB row: a literal, whatever the process language.
            error="Could not acquire pipeline.lock — another run is already active.",
        )
    except Exception:
        log.warning("pipeline_lock_conflict_row_write_failed", run_uid=run_uid, exc_info=True)


def _counts(report: StepReport) -> str:
    """Return the ``N OK, N skipped, N errors`` tally of a step report.

    Args:
        report: The step report to tally.

    Returns:
        The tally in the current language.
    """
    return t(
        "cli_core.pipeline.counts",
        ok=report.success_count,
        skipped=report.skip_count,
        errors=report.error_count,
    )


def _step_label(step: StepCode) -> str:
    """Return a step's summary-line label: its ``cli_core.step`` word, capitalised, then the colon.

    One word per step for the whole CLI (the progress table and the summary lines read the same
    ``cli_core.step.*`` keys); only the colon's typography is the catalogue's, per language.

    Args:
        step: The pipeline step.

    Returns:
        E.g. ``"Ingest:"`` in English.
    """
    return t("cli_core.pipeline.step_label", step=t_code("cli_core.step", step).capitalize())


def _summary_line(label: str, body: str) -> str:
    """Return a step summary line: the bold label, then its body.

    Args:
        label: The step's label, colon included.
        body: What the step did.

    Returns:
        The Rich-markup line to print.
    """
    return "[bold]" + label + "[/bold] " + body


def _check_row(spec: CheckSpec) -> str:
    """Return one ``--list-checks`` row.

    Args:
        spec: The check to describe.

    Returns:
        The row, columns padded as the listing has always been.
    """
    fix = t("cli_core.pipeline.check_fixable") if spec.fixable else "-"
    idx = t("cli_core.pipeline.check_indexable") if spec.indexable else "-"
    return t(
        "cli_core.pipeline.check_row",
        name=f"{spec.name:<34}",
        group=spec.group,
        severity=f"{spec.default_severity.value:<7}",
        fixable=f"{fix:<8}",
        indexable=f"{idx:<9}",
        description=spec.description,
    )


def _run_help() -> str:
    """Build the help string for the ``run`` command from the live step registry.

    Reads :data:`~personalscraper.pipeline_steps.DEFAULT_STEPS` at import time so
    the help text automatically reflects any future step additions or removals
    without requiring a manual docstring update.

    Returns:
        Human-readable one-liner listing every pipeline step in order,
        e.g. ``"Run full pipeline (ingest → sort → … → dispatch)."``.
    """
    from personalscraper.pipeline_steps import DEFAULT_STEPS  # noqa: PLC0415

    steps = " → ".join(DEFAULT_STEPS.keys())
    return t("cli_core.pipeline.run_help", steps=steps)


@command_with_telemetry(help=t("cli_core.pipeline.ingest.help"))
@handle_cli_errors
@boundary(stream_events=True, build_torrent_client=True)
def ingest(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_moving")),
    *,
    bundle: CommandContext,
) -> None:
    """Ingest completed torrents from qBittorrent."""
    config = ctx.obj.config
    assert config is not None  # guaranteed non-None by callback
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    staging_dir = config.paths.staging_dir
    ingest_dir = staging_path(config, find_ingest_dir(config))
    # Fail-safe copy-vs-move (§7 HnR): inject the seed-obligation
    # checker from the acquire context via the core port.
    _acquire = getattr(app_context, "acquire", None)
    _seed_checker = getattr(_acquire, "delete_authority", None)
    # Advisory provenance writer (feature provenance / #30) — same injection as the
    # pipeline IngestStep; None ⇒ no provenance recorded (manual/direct unaffected).
    _provenance = getattr(getattr(_acquire, "store", None), "provenance", None)
    report = cli_helpers.run_ingest(
        bundle.settings,
        dry_run=dry_run,
        ingest_dir=ingest_dir,
        staging_dir=staging_dir,
        config=config,
        event_bus=app_context.event_bus,
        torrent_client=app_context.torrent_client,
        seed_checker=_seed_checker,
        provenance=_provenance,
    )
    console.print(_summary_line(_step_label(StepCode.INGEST), _counts(report)))


@command_with_telemetry(help=t("cli_core.pipeline.sort.help"))
@handle_cli_errors
@boundary(stream_events=True)
def sort(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_moving")),
    *,
    bundle: CommandContext,
) -> None:
    """Sort and clean media files."""
    from personalscraper.sorter.run import run_sort

    config = ctx.obj.config
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    report = run_sort(
        bundle.settings,
        staging_dir=config.paths.staging_dir,
        dry_run=dry_run,
        config=config,
        event_bus=app_context.event_bus,
    )
    console.print(_summary_line(_step_label(StepCode.SORT), _counts(report)))
    if state["verbose"]:
        for detail in report.details:
            console.print("  " + detail)


@command_with_telemetry(help=t("cli_core.pipeline.scrape.help"))
@handle_cli_errors
@boundary(stream_events=True)
def scrape(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_writing")),
    interactive: bool = typer.Option(False, "--interactive", "-i", help=t("cli_core.pipeline.opt.interactive")),
    movies_only: bool = typer.Option(False, "--movies-only", help=t("cli_core.pipeline.opt.movies_only")),
    tvshows_only: bool = typer.Option(False, "--tvshows-only", help=t("cli_core.pipeline.opt.tvshows_only")),
    *,
    bundle: CommandContext,
) -> None:
    """Scrape metadata and artwork from TMDB/TVDB."""
    from personalscraper.scraper.run import run_scrape

    config = ctx.obj.config  # Guaranteed non-None by callback.
    assert config is not None
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    report = run_scrape(
        bundle.settings,
        config=config,
        dry_run=dry_run,
        interactive=interactive,
        movies_only=movies_only,
        tvshows_only=tvshows_only,
        event_bus=app_context.event_bus,
        registry=app_context.provider_registry,
    )
    console.print(_summary_line(_step_label(StepCode.SCRAPE), _counts(report)))
    if state["verbose"]:
        for detail in report.details:
            console.print("  " + detail)


@command_with_telemetry(help=t("cli_core.pipeline.verify.help", marker="**"))
@handle_cli_errors
def verify(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_modifying_files")),
    movies_only: bool = typer.Option(False, "--movies-only", help=t("cli_core.pipeline.opt.movies_only")),
    tvshows_only: bool = typer.Option(False, "--tvshows-only", help=t("cli_core.pipeline.opt.tvshows_only")),
    check: list[str] = typer.Option(None, "--check", help=t("cli_core.pipeline.opt.check")),
    list_checks: bool = typer.Option(False, "--list-checks", help=t("cli_core.pipeline.opt.list_checks")),
) -> None:
    """Verify and qualify scraped media before dispatch.

    The ``--list-checks`` listing and the unknown-``--check`` validation run
    **before** any lock/journal scaffold — a pure listing or an argument error
    must not take ``pipeline.lock`` nor write a ``pipeline_run`` row. Only once
    the arguments are accepted does the real work run inside the shared
    :func:`~personalscraper.cli_helpers.boundary` scaffold via
    :func:`_verify_run`.
    """
    console = state["console"]
    if list_checks:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list

        for spec in (s for s in _list() if s.stage == CheckStage.DISPATCH):
            console.print(_check_row(spec))
        raise typer.Exit(0)
    only = frozenset(check) if check else None
    if only is not None:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list_checks

        _available = {s.name for s in _list_checks() if s.stage == CheckStage.DISPATCH}
        _unknown = only - _available
        if _unknown:
            raise typer.BadParameter(
                t(
                    "cli_core.pipeline.unknown_dispatch_check",
                    unknown=str(sorted(_unknown)),
                    available=str(sorted(_available)),
                )
            )
    _verify_run(ctx, dry_run=dry_run, movies_only=movies_only, tvshows_only=tvshows_only, only=only)


@boundary(stream_events=True, command="verify")
def _verify_run(
    ctx: typer.Context,
    *,
    dry_run: bool,
    movies_only: bool,
    tvshows_only: bool,
    only: frozenset[str] | None,
    bundle: CommandContext,
) -> None:
    """Run the verify step inside the shared boundary scaffold.

    Split out from :func:`verify` so the pre-lock ``--list-checks`` /
    unknown-check early exits stay OUTSIDE the lock + journal, byte-identical to
    the pre-boundary command. Journals under ``command="verify"``.

    Args:
        ctx: The Typer context (``ctx.obj.config`` holds the loaded config).
        dry_run: Preview without modifying files.
        movies_only: Restrict to movies.
        tvshows_only: Restrict to TV shows.
        only: The validated ``--check`` subset, or ``None`` for all checks.
        bundle: The boundary-injected service bundle (``needs="app"``).
    """
    from personalscraper.verify.run import run_verify

    config = ctx.obj.config
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        report, dispatchable = run_verify(
            bundle.settings,
            config,
            dry_run=dry_run,
            movies_only=movies_only,
            tvshows_only=tvshows_only,
            only=only,
            event_bus=app_context.event_bus,
        )
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(
        _summary_line(
            _step_label(StepCode.VERIFY),
            t("cli_core.pipeline.verify_counts", ok=report.success_count, blocked=report.skip_count),
        )
    )
    console.print(t("cli_core.pipeline.verify_ready", ready=len(dispatchable)))
    if state["verbose"]:
        for detail in report.details:
            console.print("  " + detail)


@command_with_telemetry(help=t("cli_core.pipeline.enforce.help", marker="**"))
@handle_cli_errors
def enforce(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_modifying")),
    check: list[str] = typer.Option(None, "--check", help=t("cli_core.pipeline.opt.check")),
    list_checks: bool = typer.Option(False, "--list-checks", help=t("cli_core.pipeline.opt.list_checks")),
) -> None:
    """Enforce staging conventions: sanitize filenames, validate structure, check coherence.

    ``--list-checks`` and the unknown-``--check`` validation run **before** the
    lock/journal scaffold (they must not take ``pipeline.lock`` nor journal a
    run); the accepted-argument path runs the real work inside the shared
    :func:`~personalscraper.cli_helpers.boundary` scaffold via :func:`_enforce_run`.
    """
    console = state["console"]
    if list_checks:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list

        for spec in (s for s in _list() if s.stage == CheckStage.STAGING):
            console.print(_check_row(spec))
        raise typer.Exit(0)
    only = frozenset(check) if check else None
    if only is not None:
        from personalscraper.verify.checks.base import CheckStage
        from personalscraper.verify.checks.catalog import list_checks as _list_checks

        _available = {s.name for s in _list_checks() if s.stage == CheckStage.STAGING}
        _unknown = only - _available
        if _unknown:
            raise typer.BadParameter(
                t(
                    "cli_core.pipeline.unknown_staging_check",
                    unknown=str(sorted(_unknown)),
                    available=str(sorted(_available)),
                )
            )
    _enforce_run(ctx, dry_run=dry_run, only=only)


@boundary(stream_events=True, command="enforce")
def _enforce_run(
    ctx: typer.Context,
    *,
    dry_run: bool,
    only: frozenset[str] | None,
    bundle: CommandContext,
) -> None:
    """Run the enforce step inside the shared boundary scaffold.

    Split out from :func:`enforce` so the pre-lock ``--list-checks`` /
    unknown-check early exits stay OUTSIDE the lock + journal, byte-identical to
    the pre-boundary command. Journals under ``command="enforce"``.

    Args:
        ctx: The Typer context (``ctx.obj.config`` holds the loaded config).
        dry_run: Preview without modifying.
        only: The validated ``--check`` subset, or ``None`` for all checks.
        bundle: The boundary-injected service bundle (``needs="app"``).
    """
    from personalscraper.enforce.run import run_enforce

    config = ctx.obj.config
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        report = run_enforce(bundle.settings, config, dry_run=dry_run, only=only, event_bus=app_context.event_bus)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(
        t(
            "cli_core.pipeline.enforce_counts",
            fixed=report.success_count,
            ok=report.skip_count,
            errors=report.error_count,
        )
    )
    if state["verbose"]:
        for detail in report.details:
            console.print("  " + detail)


@command_with_telemetry(help=t("cli_core.pipeline.dispatch.help"))
@handle_cli_errors
@boundary(stream_events=True)
def dispatch(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_moving")),
    no_post_maintenance: bool = typer.Option(
        False,
        "--no-post-maintenance",
        help=t("cli_core.pipeline.opt.no_post_maintenance"),
    ),
    *,
    bundle: CommandContext,
) -> None:
    """Move media to storage disks."""
    from personalscraper.dispatch.run import run_dispatch
    from personalscraper.pipeline_steps import resolve_dispatch_authority
    from personalscraper.subscribers.dispatch_reconcile import build_post_dispatch_reconcile_subscriber
    from personalscraper.subscribers.plex import build_plex_subscriber

    config = ctx.obj.config
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    # ACQUIRE-02: the post-dispatch reconcile subscriber closes owned wanted
    # rows + retires acquired films after the dispatch step's enrich scan
    # refreshes the library. Wired here (a dispatch composition root) so a plain
    # library-index scan never gains a reconciliation side effect. The app
    # bundle is destructured HERE (boundary rule) — the builder takes only the
    # narrow services it consumes (bus + acquire lobe handle).
    reconcile_sub = build_post_dispatch_reconcile_subscriber(
        app_context.event_bus,
        getattr(app_context, "acquire", None),
    )
    # Plex refresh trigger, through the SAME single owner the full run uses:
    # this command is a dispatch composition root too, and a dispatch that
    # happens here must land in Plex exactly like one from ``run`` (the
    # Margin Call bug reproduces verbatim on this path otherwise).
    plex_subscriber = build_plex_subscriber(app_context.event_bus, bundle.settings)
    try:
        # F2 parity: resolve the SAME permit/recorder the full-run
        # DispatchStep injects, via the shared single owner.
        report, results = run_dispatch(
            bundle.settings,
            config=config,
            dry_run=dry_run,
            event_bus=app_context.event_bus,
            **resolve_dispatch_authority(app_context),
        )

        # Post-dispatch index maintenance runs through the single owner
        # shared with the full-run DispatchStep (PIPELINE-CORE-01): the
        # enablement resolution, touched-disk collection, and dry-run guard
        # live in one place so both entry points behave identically.
        #
        # D4 — INSIDE the try on purpose: this call's incremental scan is what
        # indexes the freshly dispatched files, so its LibraryScanCompleted is the
        # one the reconcile subscriber must hear. Running it after the ``finally``
        # closed that subscriber is half of why owned wanted rows stayed 'grabbed'.
        from personalscraper.dispatch.post_maintenance import maybe_run_post_dispatch_maintenance

        maybe_run_post_dispatch_maintenance(
            config,
            results,
            dry_run=dry_run,
            # D4 — the process bus: a fresh EventBus() reaches nobody.
            event_bus=app_context.event_bus,
            no_post_maintenance=no_post_maintenance,
        )

        # §14.3 — « la fermeture suit la médiathèque, pas une horloge ». Le balayage
        # déclenché par LibraryScanCompleted part du ``finally`` du scan lui-même : il
        # peut donc tomber pendant que la médiathèque est encore réécrite (un dispatch
        # qui FUSIONNE une série renomme tous les épisodes en conflit, et la réponse de
        # possession d'une saison est tout-ou-rien). Ce second passage est
        # DÉTERMINISTE : toute la maintenance post-dispatch a rendu la main, la
        # médiathèque est stable par construction et non par chance.
        if reconcile_sub is not None:
            reconcile_sub.settle()
    finally:
        if reconcile_sub is not None:
            reconcile_sub.close()
        if plex_subscriber is not None:
            plex_subscriber.close()

    console.print(_summary_line(_step_label(StepCode.DISPATCH), _counts(report)))
    if state["verbose"]:
        for detail in report.details:
            console.print("  " + detail)


@command_with_telemetry(help=t("cli_core.pipeline.clean.help"))
@handle_cli_errors
@boundary(stream_events=True)
def clean(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_modifying")),
    *,
    bundle: CommandContext,
) -> None:
    """Run reclean + dedup only (process sub-step, SH-21 / AR-C).

    Standalone CLI surface around :func:`personalscraper.process.run.run_clean`.
    Useful for debugging the clean sub-step in isolation and for composition
    with other operator workflows (e.g. dry-run a clean pass before launching
    the full process step). The full pipeline still invokes ``run_clean``
    internally via ``run_process`` — this command does not alter that flow.
    """
    from personalscraper.process.run import run_clean

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        report = run_clean(
            bundle.settings,
            config=config,
            dry_run=dry_run,
            event_bus=app_context.event_bus,
        )
    except Exception as exc:
        console.print(
            "[red]" + t("cli_core.pipeline.clean_failed", error_class=type(exc).__name__, error=str(exc)) + "[/red]"
        )
        get_logger("pipeline").exception("clean_command_failed", error=str(exc))
        raise typer.Exit(1) from exc

    console.print(_summary_line(_step_label(StepCode.CLEAN), _counts(report)))
    if state["verbose"]:
        for detail in report.details:
            console.print("  " + detail)


@command_with_telemetry(help=t("cli_core.pipeline.cleanup.help"))
@handle_cli_errors
@boundary(stream_events=True)
def cleanup(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_deleting")),
    *,
    bundle: CommandContext,
) -> None:
    """Run empty-directory cleanup only (process sub-step, SH-21 / AR-C).

    Standalone CLI surface around :func:`personalscraper.process.run.run_cleanup`.
    Removes empty directories left behind by previous steps. Distinct from
    ``clean`` (which performs reclean + dedup of polluted folder names); this
    command only operates on empty directories. Useful for tidying staging
    between manual operator interventions. The full pipeline still invokes
    ``run_cleanup`` internally via ``run_process`` — this command does not
    alter that flow.
    """
    from personalscraper.process.run import run_cleanup

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        report = run_cleanup(
            bundle.settings,
            config=config,
            dry_run=dry_run,
            event_bus=app_context.event_bus,
        )
    except Exception as exc:
        console.print(
            "[red]" + t("cli_core.pipeline.cleanup_failed", error_class=type(exc).__name__, error=str(exc)) + "[/red]"
        )
        get_logger("pipeline").exception("cleanup_command_failed", error=str(exc))
        raise typer.Exit(1) from exc

    console.print(
        _summary_line(
            _step_label(StepCode.CLEANUP), t("cli_core.pipeline.cleanup_counts", removed=report.success_count)
        )
    )
    if state["verbose"]:
        for detail in report.details:
            console.print("  " + detail)


@command_with_telemetry(help=t("cli_core.pipeline.process.help"))
@handle_cli_errors
@boundary(stream_events=True)
def process(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_modifying")),
    interactive: bool = typer.Option(False, "--interactive", "-i", help=t("cli_core.pipeline.opt.interactive")),
    *,
    bundle: CommandContext,
) -> None:
    """Run process phase only (reclean + dedup + scrape + cleanup)."""
    from personalscraper.process.run import run_process

    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    app_context = bundle.app_context
    assert app_context is not None
    try:
        clean, scrape, cleanup = run_process(
            bundle.settings,
            dry_run=dry_run,
            interactive=interactive,
            config=config,
            event_bus=app_context.event_bus,
            registry=app_context.provider_registry,
        )
    except Exception as exc:
        console.print(
            "[red]" + t("cli_core.pipeline.process_failed", error_class=type(exc).__name__, error=str(exc)) + "[/red]"
        )
        get_logger("pipeline").exception("process_command_failed", error=str(exc))
        raise typer.Exit(1) from exc

    for label, report in [
        (_step_label(StepCode.CLEAN), clean),
        (_step_label(StepCode.SCRAPE), scrape),
        (_step_label(StepCode.CLEANUP), cleanup),
    ]:
        console.print(_summary_line(label, _counts(report)))
        if state["verbose"]:
            for detail in report.details:
                console.print("  " + detail)


#: Valid ``--trigger-reason`` values. MUST include every reason any web-side caller
#: passes to :func:`~personalscraper.app.pipeline_trigger.spawn_pipeline_run` — in
#: particular ``"scrape-resolve"`` (the §4 continuation after a manual resolve).
#: A missing value here makes the spawned continuation ``run`` crash on argv
#: validation, so the resolved media never dispatches (product-intent.md §4
#: dénaturation: "un média qui reste échoué en staging après résolution").
_VALID_TRIGGER_REASONS: frozenset[str] = frozenset({"", "completion", "safety_net", "manual", "web", "scrape-resolve"})


def _validate_trigger_reason(value: str) -> str:
    """Validate the ``--trigger-reason`` value against :data:`_VALID_TRIGGER_REASONS`.

    Args:
        value: Raw string from the CLI option.

    Returns:
        The validated value unchanged.

    Raises:
        typer.BadParameter: If *value* is not one of the allowed reasons.
    """
    if value not in _VALID_TRIGGER_REASONS:
        allowed = ", ".join(sorted(r for r in _VALID_TRIGGER_REASONS if r))
        raise typer.BadParameter(t("cli_core.pipeline.trigger_reason_invalid", allowed=allowed, value=value))
    return value


@command_with_telemetry("run", help=_run_help())
@handle_cli_errors
def run(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_core.pipeline.opt.dry_run_full")),
    interactive: bool = typer.Option(False, "--interactive", "-i", help=t("cli_core.pipeline.opt.interactive")),
    skip_trailers: bool = typer.Option(
        False,
        "--skip-trailers",
        help=t("cli_core.pipeline.opt.skip_trailers"),
    ),
    continue_on_trailer_error: bool = typer.Option(
        False,
        "--continue-on-trailer-error",
        help=t("cli_core.pipeline.opt.continue_on_trailer_error"),
    ),
    headless: bool = typer.Option(
        False,
        "--headless",
        help=t("cli_core.pipeline.opt.headless"),
    ),
    no_console: bool = typer.Option(
        False,
        "--no-console",
        help=t("cli_core.pipeline.opt.no_console"),
    ),
    trigger_reason: str = typer.Option(
        "",
        "--trigger-reason",
        hidden=True,
        callback=_validate_trigger_reason,
        help=t("cli_core.pipeline.opt.trigger_reason"),
    ),
    no_post_maintenance: bool = typer.Option(
        False,
        "--no-post-maintenance",
        help=t("cli_core.pipeline.opt.no_post_maintenance"),
    ),
) -> None:
    """Execute all pipeline phases via ``Pipeline.run``.

    The step list displayed in ``--help`` is generated from
    :data:`~personalscraper.pipeline_steps.DEFAULT_STEPS` at import time via
    :func:`_run_help`, so it always reflects the actual registered steps.
    """
    config = ctx.obj.config  # Guaranteed non-None by callback.
    console = state["console"]
    verbose = state["verbose"]

    if not cli_helpers.acquire_pipeline_lock(
        config.paths.data_dir / "pipeline.lock",
        cli_helpers.scrape_locks_dir_for(config.paths.data_dir),
    ):
        console.print("[red]" + t("cli_core.pipeline.another_instance") + "[/red]")
        _journal_lock_conflict(config, dry_run=dry_run)
        raise typer.Exit(1)

    try:
        settings = cli_helpers.get_settings()
        code = execute_run(
            config,
            settings,
            RunOptions(
                dry_run=dry_run,
                skip_trailers=skip_trailers,
                continue_on_trailer_error=continue_on_trailer_error,
                no_post_maintenance=no_post_maintenance,
            ),
            trigger=trigger_reason,
            console=console,
            verbose=verbose,
            headless=headless,
            interactive=interactive,
            no_console=no_console,
        )
        if code:
            raise typer.Exit(code)
    finally:
        cli_helpers.release_lock(lock_file=config.paths.data_dir / "pipeline.lock")


# Torrent-client listing (``torrents-list``) lives in
# :mod:`personalscraper.commands.torrents` (solidify — module-size relief).
