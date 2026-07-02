"""Cross-seed CLI command — ``personalscraper cross-seed --sweep`` | ``--hash <H>``.

Drive the :class:`~personalscraper.acquire.cross_seed.CrossSeedService`
from the CLI.  This command touches only qBittorrent + acquire.db (via the
service), not staging or library — it does **not** acquire ``pipeline.lock``.

Registered against the shared Typer ``app`` via ``@command_with_telemetry``
(imported side-effect in ``cli.py``).

Options:
- ``--sweep`` — Run the throttled back-catalog cross-seed sweep (X2).
- ``--hash`` — Cross-seed a single torrent by info-hash (X1 per-completion path).
"""

from __future__ import annotations

import typer

from personalscraper import cli as cli_compat
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.cli_state import state
from personalscraper.logger import get_logger

log = get_logger("cli.cross_seed")


@command_with_telemetry("cross-seed")
@handle_cli_errors
def cross_seed(
    ctx: typer.Context,
    sweep: bool = typer.Option(
        False,
        "--sweep",
        help="Run throttled back-catalog cross-seed sweep (X2).",
    ),
    info_hash: str | None = typer.Option(
        None,
        "--hash",
        help="Cross-seed a single torrent by info-hash (X1 per-completion path).",
    ),
) -> None:
    """Native cross-seeding engine — find matching torrents on other trackers and inject them.

    The ``--sweep`` flag iterates all completed torrents in the client and
    cross-seeds each eligible one (exclude ``SEED_PURE``-tagged, exclude
    recently-searched, honour daily quota + inter-search delay).

    The ``--hash`` flag cross-seeds a single torrent identified by its V1
    info-hash.  Idempotent — re-running the same hash is a no-op (recently-searched
    guard).  This is the form the Watcher daemon spawns per completion (W5).

    ``--sweep`` and ``--hash`` are mutually exclusive.

    When ``cross_seed.enabled`` is ``False`` in config the service returns
    immediately — the command still exits 0 but echoes the disabled state.

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.
        sweep: When ``True``, run the full back-catalog sweep.
        info_hash: V1 info-hash of a single torrent to cross-seed.

    Raises:
        typer.Exit: Exit code 1 when no compatible torrent client is
            configured (e.g. Transmission which lacks ``TorrentInjector``).
        typer.Exit: Exit code 2 when invoked with both ``--sweep`` and
            ``--hash``, or with neither.
    """
    config = ctx.obj.config
    assert config is not None  # guaranteed by the callback in cli.py
    console = state["console"]
    settings = cli_compat.get_settings()

    # --sweep and --hash are mutually exclusive; at least one is required.
    if sweep and info_hash is not None:
        typer.echo("--sweep and --hash are mutually exclusive", err=True)
        raise typer.Exit(code=2)

    if not sweep and info_hash is None:
        typer.echo("Use --sweep or --hash", err=True)
        raise typer.Exit(code=2)

    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        acquire = app_context.acquire
        if acquire is None or acquire.cross_seed is None:
            console.print(
                "[red]Cross-seed not available: no compatible torrent client configured.[/red]"
                "  The active torrent client must support TorrentInjector"
                " (qBittorrent; Transmission lacks this capability)."
            )
            raise typer.Exit(code=1)

        cs = acquire.cross_seed

        # Echo disabled state before calling the service so the operator knows
        # the reason for an immediate zero-result return.
        if not config.cross_seed.enabled:
            console.print("[yellow]Cross-seed is disabled in config (cross_seed.enabled=false).[/yellow]")

        if sweep:
            sweep_result = cs.sweep()

            if sweep_result.lister_failed:
                console.print(
                    "[red]Sweep failed:[/red] could not enumerate completed torrents "
                    "(torrent client unreachable or error)."
                )
                raise typer.Exit(code=1)

            console.print(
                f"[green]Sweep complete:[/green] "
                f"{sweep_result.checked} checked, "
                f"{sweep_result.injected} injected"
                + (" [yellow](quota exhausted)[/yellow]" if sweep_result.quota_exhausted else "")
            )
            log.info(
                "cross_seed_sweep_done",
                checked=sweep_result.checked,
                injected=sweep_result.injected,
                quota_exhausted=sweep_result.quota_exhausted,
                lister_failed=sweep_result.lister_failed,
            )
        else:
            assert info_hash is not None  # guaranteed by mutual-exclusion gate above
            check_result = cs.check(info_hash)

            if check_result.skipped:
                console.print(f"[dim]Skipped: {check_result.skip_reason}[/dim]")
            if check_result.injected:
                for inj_hash in check_result.injected:
                    console.print(f"[green]Injected: {inj_hash}[/green]")
            if check_result.rejected:
                for rej_hash, tracker, reason in check_result.rejected:
                    console.print(f"[yellow]Rejected: {rej_hash} @ {tracker} — {reason}[/yellow]")

            log.info(
                "cross_seed_check_done",
                info_hash=info_hash,
                injected=len(check_result.injected),
                rejected=len(check_result.rejected),
                skipped=check_result.skipped,
                skip_reason=check_result.skip_reason,
            )
