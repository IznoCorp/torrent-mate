"""Audit Typer commands for the library."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import CommandContext, boundary, handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.core.sqlite._fs_probe import is_mounted
from personalscraper.i18n import t
from personalscraper.logger import get_logger

log = get_logger("cli")

_BOLD_GREEN = "bold green"
_BOLD_RED = "bold red"


def _styled(style: str, text: str) -> str:
    """Wrap a looked-up line in a Rich style tag (markup stays in code, never in the catalogue).

    Args:
        style: The Rich style name, e.g. ``"red"`` or ``"bold green"``.
        text: The already translated text.

    Returns:
        ``text`` between the opening and closing tags of ``style``.
    """
    return f"[{style}]{text}[/{style}]"


@app.command("library-reconcile", help=t("cli_library.audit.reconcile_command_help"))
@handle_cli_errors
@boundary(needs="app", lock=False, journal=False, staging=False)
def library_reconcile(
    ctx: typer.Context,
    scope: list[str] = typer.Option(
        [],
        "--scope",
        help=t("cli_library.audit.reconcile_scope_help"),
    ),
    read_only: bool = typer.Option(
        False,
        "--read-only",
        help=t("cli_library.audit.reconcile_read_only_help"),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=t("cli_library.audit.reconcile_dry_run_help"),
    ),
    enqueue_repairs: bool = typer.Option(
        False,
        "--enqueue-repairs",
        help=t("cli_library.audit.reconcile_enqueue_repairs_help"),
    ),
    clean_fk_orphans: bool = typer.Option(
        False,
        "--clean-fk-orphans",
        help=t("cli_library.audit.reconcile_clean_fk_orphans_help"),
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help=t("cli_library.audit.reconcile_config_help")),
    *,
    bundle: CommandContext,
) -> None:
    """Detect index ↔ filesystem divergences without a full rescan.

    Read-only by default — runs DB-only checks (one ``Path.exists()``
    for the dispatch_path detector — every other detector is pure SQL)
    and prints a JSON report of findings.  Optionally enqueues each
    finding into ``repair_queue`` so ``library-repair`` can fix them
    within a bounded budget (opt-in via ``--enqueue-repairs``).

    Mode summary:

    - Default (no flags) — read-only: report divergences, no writes.
    - ``--read-only`` — explicit alias for the default read-only mode.
    - ``--dry-run`` — alias for ``--read-only`` (same behaviour).
    - ``--enqueue-repairs`` — opt-in write mode; pushes findings into
      ``repair_queue``.

    Detector scopes:

    - ``merkle`` — disk merkle drift between stored and computed roots.
    - ``dispatch_path`` — items whose dispatch_path attribute is gone.
    - ``enrich`` — files whose enriched_at is older than mtime.
    - ``release`` — orphan media_release rows + null-release files.
    - ``season`` — denormalised season.episode_count drift.
    - ``item`` — media_item rows with no file evidence.
    - ``path_missing`` — path rows whose resolved absolute path no longer
      exists on the filesystem (mounted disks only).

    Examples:
        personalscraper library-reconcile
        personalscraper library-reconcile --read-only
        personalscraper library-reconcile --dry-run
        personalscraper library-reconcile --scope enrich --scope release
        personalscraper library-reconcile --scope path_missing
        personalscraper library-reconcile --enqueue-repairs
    """
    from personalscraper.cli_helpers.output import emit  # noqa: PLC0415
    from personalscraper.indexer.cli import library_reconcile_command  # noqa: PLC0415

    # --read-only / --dry-run are mutually exclusive with --enqueue-repairs.
    # Both flags mean the same thing: stay in the default read-only mode.
    if enqueue_repairs and (read_only or dry_run):
        typer.echo(t("cli_library.audit.reconcile_modes_exclusive"), err=True)
        raise typer.Exit(1)

    # --read-only and --dry-run are aliases for each other; both simply
    # assert the default mode.  No flag means read-only as well.
    effective_enqueue = enqueue_repairs

    # FK-orphan cleanup is a write; applied only when not in a read-only/dry-run
    # preview (dry-run-first: the FK-orphan counts + cascade impact are always
    # reported, and --clean-fk-orphans --dry-run previews without deleting).
    apply_fk_clean = clean_fk_orphans and not (read_only or dry_run)

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)

    # The boundary's "app" tier already built the process-scoped AppContext (via
    # per_step_boundary, binding a fresh correlation_id) so the pre-open
    # free-space guard inside ``open_db`` emits ``DiskFullWarning`` on the bus
    # subscribers are wired to (consistency with library-index).
    app_context = bundle.app_context
    assert app_context is not None
    loaded_config = ctx.obj.config
    rc, payload = library_reconcile_command(
        scopes=scope if scope else None,
        enqueue_repairs=effective_enqueue,
        clean_fk_orphans=apply_fk_clean,
        config_path=effective_config,
        event_bus=app_context.event_bus,
    )

    # Proactive no-NFO visibility (DESIGN decision #3): surface items the
    # scanner flagged with the folder-name fallback so the audit output points
    # the operator straight at the repair command.
    if isinstance(payload, dict):
        payload.setdefault("nfo_missing_count", _count_nfo_missing(loaded_config))

    emit(payload, rich_renderer=lambda: _print_reconcile_rich(payload))
    if rc != 0:
        raise typer.Exit(rc)


def _count_nfo_missing(loaded_config: object) -> int:
    """Count distinct items flagged ``nfo_missing`` / ``nfo_incomplete``.

    A read-only helper for the proactive no-NFO line in ``library-reconcile``
    output. Returns 0 for the benign pre-migration / missing-table case
    (``sqlite3.OperationalError``) — and logs a warning first so the advisory
    line is silently dropped only when the ``item_issue`` table genuinely does
    not exist yet. A real DB error (corruption, lock) is a different
    ``sqlite3.Error`` subclass and is intentionally allowed to propagate rather
    than masquerading as "0 items without NFO" (mirrors the narrowed contract
    of ``doctor._check_nfo_missing``).

    Args:
        loaded_config: The loaded config object (``ctx.obj.config``), or ``None``.

    Returns:
        Number of distinct items with a missing/incomplete NFO, or 0 when the
        ``item_issue`` table is absent (pre-migration DB).

    Raises:
        sqlite3.Error: For non-OperationalError DB failures (corruption, lock,
            disk failure) — surfaced instead of silently returning 0.
    """
    import sqlite3 as _sqlite3  # noqa: PLC0415

    from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415

    if loaded_config is None:
        return 0
    db_path = getattr(getattr(loaded_config, "indexer", None), "db_path", None)
    if db_path is None or not Path(db_path).exists():
        return 0
    try:
        conn = _sqlite3.connect(str(db_path))
        _apply_pragmas(conn)
        try:
            row = conn.execute(
                "SELECT COUNT(DISTINCT item_id) FROM item_issue WHERE type IN ('nfo_missing','nfo_incomplete')"
            ).fetchone()
        finally:
            conn.close()
    except _sqlite3.OperationalError as exc:
        # Pre-migration / missing-table case only (mirrors
        # ``doctor._check_nfo_missing``): the ``item_issue`` table does not
        # exist yet. A genuine DB error (corruption, lock, disk failure) is a
        # different sqlite3.Error subclass and is intentionally NOT swallowed
        # here so it surfaces instead of reading as "0 items without NFO".
        log.warning("nfo_missing_count_unavailable", db_path=str(db_path), error=str(exc))
        return 0
    return int(row[0]) if row and row[0] is not None else 0


def _print_reconcile_rich(payload: dict[str, object]) -> None:
    """Render a reconcile summary via Rich with severity-coloured counts.

    Args:
        payload: The summary dict returned by :func:`~personalscraper.indexer.cli.library_reconcile_command`.
    """
    from typing import cast  # noqa: PLC0415

    from personalscraper.cli_state import state  # noqa: PLC0415

    console = state["console"]
    if "error" in payload:
        console.print(_styled("red", t("cli_library.audit.error_label")) + " " + str(payload["error"]))
        return

    console.print(
        _styled("bold", t("cli_library.audit.total_findings_label")) + " " + str(payload.get("total_findings", 0))
    )
    console.print(t("cli_library.audit.merkle_drift", value=str(payload.get("merkle_drift", 0))))
    console.print(
        t("cli_library.audit.dispatch_path_missing_count", value=str(payload.get("dispatch_path_missing_count", 0)))
    )
    console.print(t("cli_library.audit.enrich_stale", value=str(payload.get("enrich_stale", 0))))
    console.print(t("cli_library.audit.release_orphans_count", value=str(payload.get("release_orphans_count", 0))))
    console.print(t("cli_library.audit.files_without_release", value=str(payload.get("files_without_release", 0))))
    console.print(
        t("cli_library.audit.season_count_drift_count", value=str(payload.get("season_count_drift_count", 0)))
    )
    console.print(
        t("cli_library.audit.items_without_files_count", value=str(payload.get("items_without_files_count", 0)))
    )
    console.print(t("cli_library.audit.path_missing_count", value=str(payload.get("path_missing_count", 0))))

    samples: list[tuple[str, str]] = [
        ("dispatch_path_missing", "dispatch_path_missing_sample"),
        ("release_orphans", "release_orphans_sample"),
        ("season_count_drift", "season_count_drift_sample"),
        ("items_without_files", "items_without_files_sample"),
        ("path_missing", "path_missing_sample"),
    ]
    for label, key in samples:
        sample = cast("list[str]", payload.get(key, []))
        if sample:
            console.print(_styled("yellow", t("cli_library.audit.sample_header", label=label, number=len(sample))))
            for s in sample[:5]:
                console.print("  " + s)

    if payload.get("enqueued_repairs", 0):
        console.print(
            _styled(_BOLD_GREEN, t("cli_library.audit.enqueued_repairs_label")) + " " + str(payload["enqueued_repairs"])
        )

    # Proactive no-NFO visibility (DESIGN decision #3): a yellow advisory line
    # pointing the operator at the targeted re-scrape repair command.
    nfo_missing_count = cast("int", payload.get("nfo_missing_count", 0))
    if nfo_missing_count > 0:
        console.print(_styled("yellow", t("cli_library.audit.nfo_missing_advisory", number=nfo_missing_count)))


@app.command("library-ghost-audit", help=t("cli_library.audit.ghost_command_help"))
@handle_cli_errors
def library_ghost_audit(
    ctx: typer.Context,
    disk: str = typer.Option(None, "--disk", help=t("cli_library.audit.ghost_disk_help")),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help=t("cli_library.audit.ghost_config_help")),
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
        if not is_mounted(d.path):
            console.print(_styled("yellow", t("cli_library.audit.ghost_not_mounted", disk=d.id)))
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
            console.print(_styled("red", t("cli_library.audit.ghost_walk_error", disk=d.id, error=str(exc))))
            continue

        total_ghosts += len(ghosts)
        if ghosts:
            console.print(_styled("red", t("cli_library.audit.ghost_found", disk=d.id, number=len(ghosts))))
            for g in ghosts[:10]:
                console.print("  " + g)
            if len(ghosts) > 10:
                console.print("  " + t("cli_library.audit.ghost_more", number=len(ghosts) - 10))
        else:
            console.print(_styled("green", t("cli_library.audit.ghost_clean", disk=d.id)))

    if total_ghosts == 0:
        console.print(_styled(_BOLD_GREEN, t("cli_library.audit.ghost_all_clean")))
    else:
        console.print(
            _styled(_BOLD_RED, t("cli_library.audit.ghost_total", number=total_ghosts))
            + "\n"
            + t("cli_library.audit.ghost_recovery")
        )
        raise typer.Exit(1)


@app.command("library-relink", help=t("cli_library.audit.relink_command_help"))
@handle_cli_errors
def library_relink(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help=t("cli_library.audit.relink_apply_help")),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=t("cli_library.audit.relink_dry_run_help"),
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help=t("cli_library.audit.relink_config_help")),
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
    ``--apply`` to commit; ``--dry-run`` or the default no-flag mode
    reports the same numbers without touching the database.

    Examples:
        personalscraper library-relink
        personalscraper library-relink --dry-run
        personalscraper library-relink --apply
    """
    import sqlite3 as _sqlite3  # noqa: PLC0415
    from pathlib import Path as _Path  # noqa: PLC0415

    from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415
    from personalscraper.indexer.release_linker import link_file_to_release, parse_episode_span  # noqa: PLC0415

    console = state["console"]

    # --dry-run and --apply are mutually exclusive.
    if dry_run and apply:
        console.print(_styled("red", t("cli_library.audit.relink_modes_exclusive")))
        raise typer.Exit(1)

    cfg = ctx.obj.config
    assert cfg is not None
    db_path = cfg.indexer.db_path

    conn = _sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    _apply_pragmas(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        disks = {did: _Path(mp) for did, mp in conn.execute("SELECT id, mount_path FROM disk WHERE is_mounted = 1")}
        if not disks:
            console.print(_styled("yellow", t("cli_library.audit.relink_no_disks")))
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
        linked = unmatched = errors = 0
        if rows:
            console.print(t("cli_library.audit.relink_found", number=_styled("bold", str(len(rows)))))
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
        else:
            console.print(_styled("green", t("cli_library.audit.relink_none")))

        # Pass 2 — span repair: files linked BEFORE multi-episode support
        # (migration 014) carry a release whose episode_end_id is NULL even
        # though the filename covers a span (« S09E23-24 »). Re-linking such a
        # file is idempotent and upgrades the release in place, creating the
        # covered episode rows (Friends double finales stayed « manquant »
        # without this).
        span_rows = list(
            conn.execute(
                """
                SELECT mf.id, mf.filename, p.disk_id, p.rel_path
                FROM media_file mf
                JOIN path p ON p.id = mf.path_id
                JOIN media_release mr ON mr.id = mf.release_id
                WHERE mr.episode_id IS NOT NULL
                  AND mr.episode_end_id IS NULL
                  AND mf.deleted_at IS NULL
                  AND (mf.filename GLOB '*[sS][0-9]*[eE][0-9]*-*'
                       OR mf.filename GLOB '*[sS][0-9]*[eE][0-9]*–*')
                """,
            )
        )
        span_repaired = 0
        for mf_id, filename, disk_id, rel_path in span_rows:
            span = parse_episode_span(filename)
            if span is None or span[1] <= span[0]:
                continue  # GLOB over-matches (`E23 - title`); the parser is the authority.
            mount = disks.get(disk_id)
            if mount is None:
                continue
            abs_path = mount / rel_path / filename
            try:
                if link_file_to_release(conn, mf_id, str(abs_path)) is not None:
                    span_repaired += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                log.warning("library_relink_span_repair_failed", file_id=mf_id, path=str(abs_path), error=str(exc))

        if apply:
            conn.commit()
            console.print(
                t(
                    "cli_library.audit.relink_applied",
                    label=_styled("green", t("cli_library.audit.applied_label")),
                    linked=linked,
                    unmatched=unmatched,
                    span_repaired=span_repaired,
                    errors=errors,
                ),
            )
        else:
            conn.rollback()
            console.print(
                t(
                    "cli_library.audit.relink_dry_run",
                    label=_styled("yellow", t("cli_library.audit.dry_run_label")),
                    linked=linked,
                    unmatched=unmatched,
                    span_repaired=span_repaired,
                    errors=errors,
                ),
            )
    finally:
        conn.close()


@app.command("library-refresh-path", help=t("cli_library.audit.refresh_path_command_help"))
@handle_cli_errors
def library_refresh_path(
    ctx: typer.Context,
    path: str = typer.Argument(..., help=t("cli_library.audit.refresh_path_path_help")),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=t("cli_library.audit.refresh_path_dry_run_help"),
    ),
) -> None:
    """Targeted index reconciliation after a MANUAL rename/move of one folder.

    The incremental scan short-circuits unchanged subtrees, so a folder the
    operator renamed by hand can stay invisible to the index exactly like a
    dispatched merge (NTFS/macFUSE mtime blindness). This command reuses the
    post-dispatch maintenance machinery on ONE path: invalidate the subtree
    (dir_mtime/last_walked_at reset + disk merkle cleared, NFC+NFD variants),
    incremental scan of the owning disk (rename detection via OSHash drift),
    then the global relink + season-count repair + repair-queue drain.

    Examples:
        personalscraper library-refresh-path "/Volumes/Disk1/medias/series/Show (2020)" --dry-run
        personalscraper library-refresh-path "/Volumes/Disk1/medias/series/Show (2020)"
    """
    from personalscraper.dispatch.post_maintenance import (  # noqa: PLC0415
        run_post_dispatch_maintenance,
    )

    console = state["console"]
    cfg = ctx.obj.config
    assert cfg is not None

    target = Path(path)
    if not target.is_absolute():
        console.print(_styled("red", t("cli_library.audit.refresh_path_not_absolute")))
        raise typer.Exit(2)
    if not target.exists():
        console.print(_styled("red", t("cli_library.audit.refresh_path_missing_label")) + " " + str(target))
        raise typer.Exit(2)

    # Resolve the owning disk: the config disk whose root is an ancestor.
    owning_label: str | None = None
    for disk_cfg in cfg.disks:
        try:
            target.relative_to(disk_cfg.path)
        except ValueError:
            continue
        owning_label = disk_cfg.id
        break
    if owning_label is None:
        console.print(
            _styled("red", t("cli_library.audit.refresh_path_no_disk"))
            + " "
            + t("cli_library.audit.refresh_path_disks", disks=", ".join(d.id for d in cfg.disks))
        )
        raise typer.Exit(2)

    if dry_run:
        console.print(
            t(
                "cli_library.audit.refresh_path_dry_run",
                label=_styled("yellow", t("cli_library.audit.dry_run_label")),
                target=_styled("bold", str(target)),
                disk=_styled("bold", str(owning_label)),
            )
        )
        return

    console.print(
        t("cli_library.audit.refresh_path_refreshing", target=_styled("bold", str(target)), disk=owning_label)
    )
    # This command IS a composition root: it owns its bus, and no acquire subscriber
    # is wired on this path (a targeted manual re-index must not gain a reconciliation
    # side effect). Constructing the bus here is therefore correct — the D4 defect was
    # a bus built INSIDE a call chain that already carried one, hiding live subscribers.
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415

    run_post_dispatch_maintenance(
        cfg,
        {owning_label},
        event_bus=EventBus(),
        destinations={owning_label: {target}},
        enabled=True,
    )
    console.print(t("cli_library.audit.refresh_path_done", label=_styled("green", t("cli_library.audit.done_label"))))
