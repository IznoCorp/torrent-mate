"""CLI command group: ``personalscraper seed`` — manual seed-pure tagger (O1).

Sub-commands:
- ``seed mark <info_hash>``   — apply the ``seed-pure`` tag to a torrent.
- ``seed unmark <info_hash>`` — remove the ``seed-pure`` tag from a torrent.
- ``seed list``               — list all completed torrents tagged ``seed-pure``.
- ``seed sweep``              — one obligation sweep: stamp ``satisfied_at`` / ``released_at``.
- ``seed purge``              — the preprod's nightly purge of its met torrents (``staging`` only).

Registered as a Typer sub-group (``seed_app = typer.Typer(...)`` mounted via
``_root_app.add_typer``). Sub-commands use ``@seed_app.command("name")``
(NOT ``@command_with_telemetry`` which is root-app-only).
Uses ``@handle_cli_errors``, ``per_step_boundary``,
``build_torrent_client=True`` (all four sub-commands touch the torrent client, and
``sweep`` also guards the acquire store; the guard ``torrent_client is not None``
is checked at command entry and exits 1 with a clear message otherwise).

Import direction: commands/ imports core/, conf/, acquire/, api/torrent/, the indexer's
destructive journal (the purge's journal is wired here), cli_app, cli_helpers.
"""

from __future__ import annotations

import dataclasses
import json
import time
from collections.abc import Callable
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from personalscraper import cli_helpers
from personalscraper.acquire.obligations import DEFAULT_SEED_RULE, sweep_obligations
from personalscraper.acquire.preprod_purge import PurgeVerdict, purge_preprod_downloads
from personalscraper.api.torrent._base import scoped
from personalscraper.api.torrent._errors import TorrentClientError
from personalscraper.cli_app import app as _root_app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.conf.environment import Environment, StoreName, current_environment, store_path
from personalscraper.conf.sandbox_guard import SandboxGuardError
from personalscraper.core.event_bus import current_run_uid
from personalscraper.core.tags import SEED_PURE
from personalscraper.i18n import t
from personalscraper.indexer.destructive_journal import OP_DELETE, record_destruction
from personalscraper.logger import get_logger

log = get_logger("cli.seed")

# Typer sub-group for the ``seed`` command.
seed_app = typer.Typer(help=t("cli_acquisition.seed.group_help"))

console = Console()


@seed_app.command("mark", help=t("cli_acquisition.seed.mark.help"))
@handle_cli_errors
def seed_mark(
    ctx: typer.Context,
    info_hash: str = typer.Argument(..., help=t("cli_acquisition.seed.mark.hash_help")),
) -> None:
    """Apply the ``seed-pure`` tag to a torrent already in the client.

    Idempotent: tagging a torrent that already carries ``seed-pure`` is a
    no-op at the client level.

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.
        info_hash: Lowercase-hex info hash of the torrent to tag.

    Raises:
        typer.Exit: Exit code 1 when no torrent client is configured.
    """
    config = ctx.obj.config
    settings = cli_helpers.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        if app_context.torrent_client is None:
            log.error("seed_mark_no_client", info_hash=info_hash)
            console.print(
                "[red]" + t("cli_acquisition.seed.error_label") + "[/red] " + t("cli_acquisition.seed.no_client")
            )
            raise typer.Exit(code=1)
        app_context.torrent_client.add_tags(info_hash, [SEED_PURE])
        log.info("seed_marked", info_hash=info_hash, tag=SEED_PURE)
        tag = "[bold]" + SEED_PURE + "[/bold]"
        done = t("cli_acquisition.seed.mark.done", info_hash=info_hash, tag=tag)
        console.print("[green]" + t("cli_acquisition.seed.mark.done_label") + "[/green] " + str(done))


@seed_app.command("unmark", help=t("cli_acquisition.seed.unmark.help"))
@handle_cli_errors
def seed_unmark(
    ctx: typer.Context,
    info_hash: str = typer.Argument(..., help=t("cli_acquisition.seed.unmark.hash_help")),
) -> None:
    """Remove the ``seed-pure`` tag from a torrent in the client.

    Idempotent: removing the tag from a torrent that does not carry it is a
    no-op at the client level.

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.
        info_hash: Lowercase-hex info hash of the torrent to untag.

    Raises:
        typer.Exit: Exit code 1 when no torrent client is configured.
    """
    config = ctx.obj.config
    settings = cli_helpers.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        if app_context.torrent_client is None:
            log.error("seed_unmark_no_client", info_hash=info_hash)
            console.print(
                "[red]" + t("cli_acquisition.seed.error_label") + "[/red] " + t("cli_acquisition.seed.no_client")
            )
            raise typer.Exit(code=1)
        app_context.torrent_client.remove_tags(info_hash, [SEED_PURE])
        log.info("seed_unmarked", info_hash=info_hash, tag=SEED_PURE)
        tag = "[bold]" + SEED_PURE + "[/bold]"
        done = t("cli_acquisition.seed.unmark.done", info_hash=info_hash, tag=tag)
        console.print("[green]" + t("cli_acquisition.seed.unmark.done_label") + "[/green] " + str(done))


@seed_app.command("list", help=t("cli_acquisition.seed.list.help"))
@handle_cli_errors
def seed_list(ctx: typer.Context) -> None:
    """List all completed torrents currently tagged ``seed-pure``.

    Queries the torrent client for completed torrents and filters those
    whose ``tags`` list contains ``SEED_PURE``. Output is a Rich table
    with columns: Hash, Name, Tags, State.

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.

    Raises:
        typer.Exit: Exit code 1 when no torrent client is configured.
    """
    config = ctx.obj.config
    settings = cli_helpers.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        if app_context.torrent_client is None:
            log.error("seed_list_no_client")
            console.print(
                "[red]" + t("cli_acquisition.seed.error_label") + "[/red] " + t("cli_acquisition.seed.no_client")
            )
            raise typer.Exit(code=1)
        torrents = scoped(app_context.torrent_client.get_completed(), config.torrent.active_scope())
        seed_pure_torrents = [x for x in torrents if SEED_PURE in (getattr(x, "tags", None) or [])]
        log.info("seed_list", total=len(torrents), seed_pure=len(seed_pure_torrents))
        if not seed_pure_torrents:
            console.print(t("cli_acquisition.seed.list.none", tag="[bold]" + SEED_PURE + "[/bold]"))
            return
        table = Table(title=t("cli_acquisition.seed.list.title", tag=SEED_PURE), show_lines=True)
        table.add_column(t("cli_acquisition.seed.list.col_hash"), style="dim", no_wrap=True)
        table.add_column(t("cli_acquisition.seed.list.col_name"))
        table.add_column(t("cli_acquisition.seed.list.col_tags"))
        table.add_column(t("cli_acquisition.seed.list.col_state"))
        for torrent in seed_pure_torrents:
            table.add_row(
                torrent.hash,
                torrent.name,
                ", ".join(torrent.tags),
                torrent.state,
            )
        console.print(table)


@seed_app.command("sweep", help=t("cli_acquisition.seed.sweep.help"))
@handle_cli_errors
def seed_sweep(ctx: typer.Context) -> None:
    """Run one seed-obligation sweep and print its report as one JSON line.

    Asks the torrent client once about every open obligation, stamps
    ``satisfied_at`` on those whose floor is reached and ``released_at`` on those
    whose torrent stayed gone for the confirmation delay, and emits the matching
    events. Meant to run under ``personalscraper schedule`` (hourly).

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.

    Raises:
        typer.Exit: Exit code 1 when no torrent client or no acquire store is
            configured, or when the client failed (nothing was written).
    """
    config = ctx.obj.config
    settings = cli_helpers.get_settings()
    with (
        cli_run_row(config, "seed-sweep") as run_rec,
        per_step_boundary(config, settings, build_torrent_client=True) as app_context,
    ):
        store = app_context.acquire.store if app_context.acquire is not None else None
        if app_context.torrent_client is None or store is None:
            log.error(
                "seed_sweep_not_configured",
                has_client=app_context.torrent_client is not None,
                has_store=store is not None,
            )
            console.print(
                "[red]"
                + t("cli_acquisition.seed.error_label")
                + "[/red] "
                + t("cli_acquisition.seed.sweep.not_configured")
            )
            raise typer.Exit(code=1)
        report = sweep_obligations(
            store,
            app_context.torrent_client,
            now=int(time.time()),
            rule=DEFAULT_SEED_RULE,
            event_bus=app_context.event_bus,
        )
        typer.echo(json.dumps(dataclasses.asdict(report)))
        if report.client_error:
            raise typer.Exit(code=1)
        # §5 « résultat chiffré »: the pass's numbers on its pipeline_run row, so
        # Système shows the sweep's last run like the other scheduled jobs.
        run_rec.record_counts(
            {
                "open": report.open,
                "satisfied": report.satisfied,
                "marked_absent": report.marked_absent,
                "released": report.released,
            }
        )


#: ``destructive_op.actor`` of the preprod purge's journal rows.
_PURGE_ACTOR = "preprod-purge"


def _purge_journal(library_db: Path) -> Callable[[Path], None]:
    """Build the purge's destruction journal over the preprod's ``library-staging.db``.

    The journal never creates the database: before the preprod's first full scan the
    file does not exist, and an empty one would be skipped by nothing that migrates
    it. A missing file is logged instead (the journal is best-effort by contract).

    Args:
        library_db: The preprod's library store.

    Returns:
        A callable recording one ``delete`` row, actor ``preprod-purge``, per content path.
    """
    run_uid = current_run_uid()

    def journal(path: Path) -> None:
        if not library_db.is_file():
            log.warning("seed_purge_journal_unavailable", db_path=str(library_db), path=str(path))
            return
        record_destruction(library_db, op=OP_DELETE, path=path, actor=_PURGE_ACTOR, run_uid=run_uid)

    return journal


def _purge_error(message: str, code: int) -> typer.Exit:
    """Print an error line and return the exit to raise.

    Args:
        message: The error, already translated (or a refusal's own text).
        code: The exit code.

    Returns:
        The :class:`typer.Exit` carrying *code*.
    """
    console.print("[red]" + t("cli_acquisition.seed.error_label") + "[/red] " + message)
    return typer.Exit(code=code)


@seed_app.command("purge", help=t("cli_acquisition.seed.purge.help"))
@handle_cli_errors
def seed_purge(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli_acquisition.seed.purge.dry_run_help")),
    max_purged: int = typer.Option(20, "--max", min=1, help=t("cli_acquisition.seed.purge.max_help")),
) -> None:
    """Run the preprod's purge: delete its torrents whose seed obligation is met, keep every other.

    Refused outside ``staging`` before the client is built. Prints one line per
    decision (verdict code, info hash, name), then a summary.

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.
        dry_run: Decide and report only; nothing is deleted, released or journaled.
        max_purged: The most torrents this run deletes.

    Raises:
        typer.Exit: Exit code 2 outside ``staging`` or when the client scope is
            refused; 1 when no torrent client or acquire store is configured, or the
            client cannot list its torrents.
    """
    env = current_environment()
    if env is not Environment.STAGING:
        log.error("seed_purge_not_staging", env=env.value)
        raise _purge_error(t("cli_acquisition.seed.purge.not_staging", env=env.value), 2)
    config = ctx.obj.config
    settings = cli_helpers.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        store = app_context.acquire.store if app_context.acquire is not None else None
        if app_context.torrent_client is None or store is None:
            log.error(
                "seed_purge_not_configured",
                has_client=app_context.torrent_client is not None,
                has_store=store is not None,
            )
            raise _purge_error(t("cli_acquisition.seed.sweep.not_configured"), 1)
        try:
            decisions = purge_preprod_downloads(
                store,
                app_context.torrent_client,
                config,
                now=int(time.time()),
                dry_run=dry_run,
                max_purged=max_purged,
                event_bus=app_context.event_bus,
                journal=_purge_journal(store_path(config.paths.data_dir, StoreName.LIBRARY, env)),
            )
        except SandboxGuardError as exc:
            log.error("seed_purge_refused", reason=str(exc))
            raise _purge_error(t("cli_acquisition.seed.purge.refused", reason=str(exc)), 2) from exc
        except TorrentClientError as exc:
            log.error("seed_purge_client_error", error=str(exc))
            raise _purge_error(t("cli_acquisition.seed.purge.client_error", error=str(exc)), 1) from exc
        for decision in decisions:
            typer.echo(
                t(
                    "cli_acquisition.seed.purge.decision",
                    verdict=decision.verdict.value,
                    info_hash=decision.info_hash,
                    name=decision.name,
                )
            )
        purged = sum(1 for d in decisions if d.verdict is PurgeVerdict.PURGED)
        key = "summary_dry_run" if dry_run else "summary"
        typer.echo(t(f"cli_acquisition.seed.purge.{key}", purged=purged, kept=len(decisions) - purged))


# Register the seed sub-group on the root Typer app (import side-effect, called by cli.py).
_root_app.add_typer(seed_app, name="seed")

__all__ = ["seed_app", "seed_list", "seed_mark", "seed_purge", "seed_sweep", "seed_unmark"]
