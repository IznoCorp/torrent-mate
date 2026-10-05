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

from personalscraper import cli_helpers
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.cli_state import state
from personalscraper.i18n import t
from personalscraper.logger import get_logger

log = get_logger("cli.cross_seed")


@command_with_telemetry("cross-seed", help=t("cli_acquisition.cross_seed.help"))
@handle_cli_errors
def cross_seed(
    ctx: typer.Context,
    sweep: bool = typer.Option(
        False,
        "--sweep",
        help=t("cli_acquisition.cross_seed.sweep_help"),
    ),
    info_hash: str | None = typer.Option(
        None,
        "--hash",
        help=t("cli_acquisition.cross_seed.hash_help"),
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

    Exit codes (``--sweep``): 0 on success or partial success (some items
    errored but others succeeded); 1 when ``lister_failed`` is True (torrent
    client unreachable) or when ALL attempted items errored (``item_errors > 0``
    and ``checked == 0`` — total failure); 2 on invalid argument combination.

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
    settings = cli_helpers.get_settings()

    # --sweep and --hash are mutually exclusive; at least one is required.
    if sweep and info_hash is not None:
        typer.echo(t("cli_acquisition.cross_seed.exclusive"), err=True)
        raise typer.Exit(code=2)

    if not sweep and info_hash is None:
        typer.echo(t("cli_acquisition.cross_seed.need_flag"), err=True)
        raise typer.Exit(code=2)

    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        acquire = app_context.acquire
        if acquire is None or acquire.cross_seed is None:
            console.print(
                "[red]"
                + t("cli_acquisition.cross_seed.not_available")
                + "[/red]  "
                + t("cli_acquisition.cross_seed.not_available_detail")
            )
            raise typer.Exit(code=1)

        cs = acquire.cross_seed

        # Echo disabled state before calling the service so the operator knows
        # the reason for an immediate zero-result return.
        if not config.cross_seed.enabled:
            console.print("[yellow]" + t("cli_acquisition.cross_seed.disabled") + "[/yellow]")

        if sweep:
            sweep_result = cs.sweep()

            if sweep_result.lister_failed:
                console.print(
                    "[red]"
                    + t("cli_acquisition.cross_seed.sweep_failed_label")
                    + "[/red] "
                    + t("cli_acquisition.cross_seed.lister_failed")
                )
                raise typer.Exit(code=1)

            # Per-item errors: warn + total-failure exit.
            # The threshold is: yellow warning when any items errored (but some
            # succeeded → partial success), hard exit 1 when ALL attempted items
            # errored (checked == 0 and item_errors > 0 → total failure).
            if sweep_result.item_errors > 0:
                console.print(
                    "[yellow]"
                    + t("cli_acquisition.cross_seed.item_errors", errors=sweep_result.item_errors)
                    + "[/yellow]"
                )
                if sweep_result.checked == 0:
                    console.print(
                        "[red]"
                        + t("cli_acquisition.cross_seed.sweep_failed_label")
                        + "[/red] "
                        + t("cli_acquisition.cross_seed.all_items_failed")
                    )
                    raise typer.Exit(code=1)

            summary = t(
                "cli_acquisition.cross_seed.sweep_summary",
                checked=sweep_result.checked,
                injected=sweep_result.injected,
            )
            quota = ""
            if sweep_result.quota_exhausted:
                quota = " [yellow]" + t("cli_acquisition.cross_seed.quota_exhausted") + "[/yellow]"
            console.print(
                "[green]" + t("cli_acquisition.cross_seed.sweep_complete_label") + "[/green] " + summary + quota
            )
            log.info(
                "cross_seed_sweep_done",
                checked=sweep_result.checked,
                injected=sweep_result.injected,
                quota_exhausted=sweep_result.quota_exhausted,
                lister_failed=sweep_result.lister_failed,
                item_errors=sweep_result.item_errors,
            )
        else:
            assert info_hash is not None  # guaranteed by mutual-exclusion gate above
            check_result = cs.check(info_hash)

            if check_result.skipped:
                console.print(
                    "[dim]" + t("cli_acquisition.cross_seed.skipped", reason=str(check_result.skip_reason)) + "[/dim]"
                )
            if check_result.injected:
                for inj_hash in check_result.injected:
                    console.print("[green]" + t("cli_acquisition.cross_seed.injected", info_hash=inj_hash) + "[/green]")
            if check_result.rejected:
                for rej_hash, tracker, reason in check_result.rejected:
                    rejected = t(
                        "cli_acquisition.cross_seed.rejected", info_hash=rej_hash, tracker=tracker, reason=reason
                    )
                    console.print("[yellow]" + rejected + "[/yellow]")

            log.info(
                "cross_seed_check_done",
                info_hash=info_hash,
                injected=len(check_result.injected),
                rejected=len(check_result.rejected),
                skipped=check_result.skipped,
                skip_reason=check_result.skip_reason,
            )
