"""Cross-seed CLI command — ``personalscraper cross-seed --sweep``.

Drive the :class:`~personalscraper.acquire.cross_seed.CrossSeedService`
from the CLI.  This command touches only qBittorrent + acquire.db (via the
service), not staging or library — it does **not** acquire ``pipeline.lock``.

Registered against the shared Typer ``app`` via ``@command_with_telemetry``
(imported side-effect in ``cli.py``).

Options:
- ``--sweep`` — Run the throttled back-catalog cross-seed sweep (X2).
- ``--hash`` (future, sub-phase 5.3) — Cross-seed a single torrent by info-hash.
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
) -> None:
    """Native cross-seeding engine — find matching torrents on other trackers and inject them.

    The ``--sweep`` flag iterates all completed torrents in the client and
    cross-seeds each eligible one (exclude ``SEED_PURE``-tagged, exclude
    recently-searched, honour daily quota + inter-search delay).

    When ``cross_seed.enabled`` is ``False`` in config the service returns
    immediately — the command still exits 0 but echoes the disabled state.

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.
        sweep: When ``True``, run the full back-catalog sweep.

    Raises:
        typer.Exit: Exit code 1 when no compatible torrent client is
            configured (e.g. Transmission which lacks ``TorrentInjector``).
        typer.Exit: Exit code 2 when invoked without ``--sweep``.
    """
    config = ctx.obj.config
    assert config is not None  # guaranteed by the callback in cli.py
    console = state["console"]
    settings = cli_compat.get_settings()

    if not sweep:
        typer.echo("Use --sweep", err=True)
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

        # Echo disabled state before calling sweep() so the operator knows the
        # reason for an immediate zero-result return.
        if not config.cross_seed.enabled:
            console.print("[yellow]Cross-seed is disabled in config (cross_seed.enabled=false).[/yellow]")

        result = cs.sweep()

        console.print(
            f"[green]Sweep complete:[/green] "
            f"{result.checked} checked, "
            f"{result.injected} injected" + (" [yellow](quota exhausted)[/yellow]" if result.quota_exhausted else "")
        )
        log.info(
            "cross_seed_sweep_done",
            checked=result.checked,
            injected=result.injected,
            quota_exhausted=result.quota_exhausted,
        )
