"""Audit Typer commands for the library."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.logger import get_logger

log = get_logger("cli")


@app.command("library-reconcile")
@handle_cli_errors
def library_reconcile(
    ctx: typer.Context,
    scope: list[str] = typer.Option(
        [],
        "--scope",
        help=(
            "Restrict to a detector scope (repeatable). "
            "Choices: merkle, dispatch_path, enrich, release, season, item. "
            "Omit to run every detector."
        ),
    ),
    enqueue_repairs: bool = typer.Option(
        False,
        "--enqueue-repairs",
        help="Push every divergence into repair_queue for library-repair to drain.",
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Detect index ↔ filesystem divergences without a full rescan.

    Runs DB-only checks (one ``Path.exists()`` for the dispatch_path
    detector — every other detector is pure SQL) and prints a JSON
    report of findings.  Optionally enqueues each finding into
    ``repair_queue`` so ``library-repair`` can fix them within a
    bounded budget.

    Detector scopes:

    - ``merkle`` — disk merkle drift between stored and computed roots.
    - ``dispatch_path`` — items whose dispatch_path attribute is gone.
    - ``enrich`` — files whose enriched_at is older than mtime.
    - ``release`` — orphan media_release rows + null-release files.
    - ``season`` — denormalised season.episode_count drift.
    - ``item`` — media_item rows with no file evidence.

    Examples:
        personalscraper library-reconcile
        personalscraper library-reconcile --scope enrich --scope release
        personalscraper library-reconcile --enqueue-repairs
    """
    from personalscraper.indexer.cli import library_reconcile_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_reconcile_command(
        scopes=scope if scope else None,
        enqueue_repairs=enqueue_repairs,
        config_path=effective_config,
    )
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-ghost-audit")
@handle_cli_errors
def library_ghost_audit(
    ctx: typer.Context,
    disk: str = typer.Option(None, "--disk", help="Audit only this disk (id from config)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Audit storage disks for NTFS-via-macFUSE ghost dirents.

    Walks every directory on each storage disk and lists every entry
    that ``os.scandir`` reports but ``os.stat`` cannot reach. These
    "ghost" entries are produced by macFUSE-NTFS when the directory
    listing returns a filename in one Unicode normalisation form (NFD)
    while the kernel inode is keyed under the other (NFC). Once a ghost
    exists, the directory cannot be emptied — neither ``rm -rf`` nor
    the project's own ``_scandir_rmtree`` walker can remove it.

    The audit is read-only: it only reports the paths. Recovery
    requires unmounting the affected NTFS volume and either running
    fsck on it or mounting it on a Windows host that can repair the
    directory entry.

    Output: per-disk count and a sample list of ghost paths.

    Examples:
        personalscraper library-ghost-audit
        personalscraper library-ghost-audit --disk Disk1
    """
    import os as _os  # noqa: PLC0415

    console = state["console"]
    cfg = ctx.obj.config
    assert cfg is not None

    total_ghosts = 0
    for d in cfg.disks:
        if disk and d.id != disk:
            continue
        if not d.path.exists():
            console.print(f"[yellow]{d.id}: not mounted, skipped[/yellow]")
            continue
        ghosts: list[str] = []
        try:
            for root, dirs, files in _os.walk(str(d.path)):
                for entry_name in list(dirs) + list(files):
                    full = _os.path.join(root, entry_name)
                    try:
                        _os.stat(full)
                    except FileNotFoundError:
                        ghosts.append(full)
                    except OSError:
                        # Permission denied / EIO are not ghosts; skip.
                        continue
        except OSError as exc:
            console.print(f"[red]{d.id}: walk error: {exc}[/red]")
            continue

        total_ghosts += len(ghosts)
        if ghosts:
            console.print(f"[red]{d.id}: {len(ghosts)} ghost dirent(s)[/red]")
            for g in ghosts[:10]:
                console.print(f"  {g}")
            if len(ghosts) > 10:
                console.print(f"  … and {len(ghosts) - 10} more")
        else:
            console.print(f"[green]{d.id}: clean[/green]")

    if total_ghosts == 0:
        console.print("[bold green]All disks clean — no ghost dirents.[/bold green]")
    else:
        console.print(
            f"[bold red]{total_ghosts} total ghost dirent(s) across all audited disks.[/bold red]\n"
            "Recovery: unmount the affected NTFS volume and run fsck, or "
            "remount on a Windows host to repair the directory entries."
        )
        raise typer.Exit(1)


@app.command("library-relink")
@handle_cli_errors
def library_relink(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Persist link updates (default: dry-run)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Relink ``media_file`` rows whose ``release_id`` is NULL.

    Walks every ``media_file`` row with ``release_id IS NULL AND
    deleted_at IS NULL`` and replays
    :func:`~personalscraper.indexer.release_linker.link_file_to_release`
    against the file's absolute path. The function resolves the owning
    item via the same dispatch_path / title / title-year strategies the
    enrich pass uses, so this is a self-healing recovery for files that
    were inserted before their item was dispatched (cold Stage A) or
    after a release_linker bug left the link behind.

    Output is the count of (linked, unmatched, errored) files. Use
    ``--apply`` to commit; the dry-run mode reports the same numbers
    without touching the database.

    Examples:
        personalscraper library-relink
        personalscraper library-relink --apply
    """
    import sqlite3 as _sqlite3  # noqa: PLC0415
    from pathlib import Path as _Path  # noqa: PLC0415

    from personalscraper.indexer.release_linker import link_file_to_release  # noqa: PLC0415

    console = state["console"]
    cfg = ctx.obj.config
    assert cfg is not None
    db_path = cfg.indexer.db_path

    conn = _sqlite3.connect(str(db_path))
    try:
        disks = {did: _Path(mp) for did, mp in conn.execute("SELECT id, mount_path FROM disk WHERE is_mounted = 1")}
        if not disks:
            console.print("[yellow]No mounted disks — nothing to relink.[/yellow]")
            raise typer.Exit(0)

        rows = list(
            conn.execute(
                """
                SELECT mf.id, mf.filename, p.disk_id, p.rel_path
                FROM media_file mf
                JOIN path p ON p.id = mf.path_id
                WHERE mf.release_id IS NULL AND mf.deleted_at IS NULL
                """,
            )
        )
        if not rows:
            console.print("[green]No orphan media_file rows. Library is fully linked.[/green]")
            raise typer.Exit(0)

        console.print(f"Found [bold]{len(rows)}[/bold] orphan media_file row(s).")
        linked = unmatched = errors = 0
        for mf_id, filename, disk_id, rel_path in rows:
            mount = disks.get(disk_id)
            if mount is None:
                continue
            abs_path = mount / rel_path / filename
            try:
                result = link_file_to_release(conn, mf_id, str(abs_path))
                if result is not None:
                    linked += 1
                else:
                    unmatched += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                log.warning("library_relink_failed", file_id=mf_id, path=str(abs_path), error=str(exc))

        if apply:
            conn.commit()
            console.print(
                f"[green]Applied:[/green] linked={linked}, unmatched={unmatched}, errors={errors}",
            )
        else:
            conn.rollback()
            console.print(
                f"[yellow]DRY-RUN:[/yellow] would link={linked}, unmatched={unmatched}, errors={errors}",
            )
    finally:
        conn.close()
