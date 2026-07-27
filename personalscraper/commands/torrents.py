"""Torrent-client listing command (``personalscraper torrents-list``).

Split out of :mod:`personalscraper.commands.pipeline` (solidify — module-size
relief). This is a read-only inventory command, deliberately **not** a journaled
pipeline step: it uses :func:`per_step_boundary` directly (no ``stream_events``)
rather than the ``@boundary`` decorator the pipeline steps carry.
"""

from __future__ import annotations

import typer

from personalscraper import cli_helpers
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import (
    handle_cli_errors,
    per_step_boundary,
)
from personalscraper.cli_state import state


@command_with_telemetry("torrents-list")
@handle_cli_errors
def torrents_list(ctx: typer.Context) -> None:
    """List completed torrents from the active qBittorrent client.

    Prints one line per completed torrent (state / progress / size /
    seeding / name) and a summary count. Exits 2 with a friendly
    message when the torrent client is unreachable (auth lockout, IP
    ban, daemon down) so monitoring tools can branch on the exit
    code. Used by the ``pipeline-monitor`` skill's GATE 0 inventory.

    Output format respects the global ``--format`` flag.
    """
    from personalscraper.api.torrent._errors import TORRENT_LISTING_ERRORS  # noqa: PLC0415
    from personalscraper.cli_helpers.output import emit  # noqa: PLC0415

    config = ctx.obj.config
    assert config is not None
    console = state["console"]
    settings = cli_helpers.get_settings()

    # Torrent client is boot-wired into AppContext (DESIGN D3) and read here
    # rather than built inline. None when no torrent client is configured
    # (DESIGN D9) — exit 2 so monitoring tools can branch on the code.
    # No stream_events: a listing command is not a journaled pipeline step.
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        client = app_context.torrent_client
        if client is None:
            console.print("[yellow]No torrent client configured (set torrent.active in torrent.json5).[/yellow]")
            raise typer.Exit(2)

        try:
            torrents = client.get_completed()
            active_hashes = client.get_all_hashes()
        except TORRENT_LISTING_ERRORS as exc:
            console.print(f"[yellow]Torrent listing failed:[/yellow] {exc}")
            raise typer.Exit(2) from exc

        payload = {
            "torrents": [
                {
                    "name": t.name,
                    "state": t.state,
                    "progress": t.progress,
                    "size_gb": t.size_bytes / (1024**3),
                    "seeding": client.is_seeding(t),
                }
                for t in torrents
            ],
            "completed": len(torrents),
            "tracked": len(active_hashes),
        }
        emit(payload, rich_renderer=lambda: _print_torrents_rich(payload))


def _print_torrents_rich(payload: dict[str, object]) -> None:
    """Render the torrent list via Rich console.

    Args:
        payload: Dict with ``torrents`` list and ``completed``/``tracked`` counts.
    """
    from typing import cast  # noqa: PLC0415

    console = state["console"]
    torrents = cast("list[dict[str, object]]", payload.get("torrents", []))
    for t in torrents:
        seeding = "seeding" if t.get("seeding") else "idle"
        t_progress = cast(float, t.get("progress", 0))
        t_size_gb = cast(float, t.get("size_gb", 0))
        t_name = cast(str, t.get("name", ""))
        t_state = cast(str, t.get("state", ""))
        console.print(f"  {t_state:<14} {t_progress * 100:5.1f}%  {t_size_gb:7.2f} GB  {seeding:8}  {t_name}")
    console.print(f"[bold]Total:[/bold] {payload['completed']} completed (of {payload['tracked']} tracked torrents)")
