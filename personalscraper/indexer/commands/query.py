"""Query and read-only indexer command functions."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import typer

from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

log = get_logger("indexer.cli")


def library_status_command(
    config_path: Path | None = None,
    *,
    event_bus: EventBus,
    output_format: str = "rich",
) -> int:
    """Print a tabular summary of disk inventory, scan health, and queue depths.

    Loads the PersonalScraper config, opens (or creates) the indexer database,
    applies any pending migrations, then queries multiple tables for a rich
    status view.

    Output includes:
    - Disk inventory: label, mounted state, last scan time, generation.
    - Last completed scan run per disk (or global).
    - Repair queue: pending depth, age of oldest row.
    - Outbox: pending depth.
    - Deleted items: count.
    - Enrich-pending count (``media_file.enriched_at IS NULL``).
    - Category-orphan count (DESIGN §17.2): items with a ``category_id`` not
      present in the current config's declared categories.

    Exit codes:
    - ``0`` — healthy.
    - ``1`` — repair queue oldest > 7 days OR depth > 1 000 OR any category
      orphans exist, or an infrastructure error occurred.

    Args:
        config_path: Optional explicit path to the config directory. When
            ``None`` the standard resolution order is used
            (``$PERSONALSCRAPER_CONFIG``, then ``./config``).
        event_bus: Required :class:`EventBus` forwarded to ``open_db`` so
            the pre-open free-space guard emits ``DiskFullWarning`` on the
            run's subscriber-wired bus.
        output_format: Output format: ``"rich"`` (default, prints a tabular
            view), ``"json"`` (prints JSON dict), or ``"plain"`` (prints
            key: value lines).

    Returns:
        ``0`` on success, ``1`` on infrastructure error or unhealthy state.
    """
    log.info("indexer.cli.status", config_path=str(config_path) if config_path else None)

    from personalscraper.conf.loader import (  # noqa: PLC0415
        ConfigNotFoundError,
        ConfigValidationError,
        load_config,
        resolve_config_path,
    )
    from personalscraper.indexer.commands._ceremony import (  # noqa: PLC0415
        IndexerCeremonyError,
        open_indexer_db,
    )

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    db_path = cfg.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    # --- DB drift guard ---
    # Warn loudly if ``db_path`` is not absolute or is being created here.
    # The resolver in IndexerConfig validates the default to absolute on
    # load, but a third-party caller can still pass a relative override; an
    # absolute-but-nonexistent path is also worth surfacing because that's
    # exactly how the orphan ``.data/library.db`` was created at some point.
    if not db_path.is_absolute():
        typer.echo(
            f"WARNING: indexer db_path is relative: {db_path}. "
            "It will be resolved against the current working directory and "
            "may produce divergent DB files depending on how the CLI is "
            "invoked. Set an absolute path in indexer.json5.",
            err=True,
        )
        log.warning("indexer.status.db_path_relative", db_path=str(db_path))
    elif not db_path.exists():
        typer.echo(
            f"WARNING: indexer db_path does not exist yet: {db_path}. "
            "A new empty database will be created on first write. If you "
            "expected to read an existing library, double-check the "
            "configured path.",
            err=True,
        )
        log.warning("indexer.status.db_path_missing", db_path=str(db_path))

    # --- Open DB and apply pending migrations ---
    try:
        with open_indexer_db(db_path, event_bus=event_bus) as conn:
            # --- Disk inventory ---
            disk_rows = conn.execute(
                "SELECT id, label, is_mounted, last_seen_at, merkle_root FROM disk ORDER BY label"
            ).fetchall()
            typer.echo(f"{'DISK':<20} {'MOUNTED':<10} {'LAST_SEEN':<20} {'MERKLE_ROOT'}")
            disks_data: list[dict[str, object]] = []
            for d_id, label, is_mounted, last_seen_at, merkle_root in disk_rows:
                mounted_str = "yes" if is_mounted else "no"
                last_seen_str = str(last_seen_at) if last_seen_at is not None else "never"
                root_str = (merkle_root or "")[:12] if merkle_root else ""
                typer.echo(f"  {label:<18} {mounted_str:<10} {last_seen_str:<20} {root_str}")
                disks_data.append(
                    {
                        "label": label,
                        "mounted": is_mounted == 1,
                        "last_seen": last_seen_str,
                        "merkle_root_prefix": root_str,
                    }
                )

            # --- Query latest successful scan ---
            row = conn.execute(
                "SELECT id, finished_at, status, generation, disk_filter FROM scan_run "
                "WHERE status = 'ok' ORDER BY finished_at DESC LIMIT 1"
            ).fetchone()

            latest_scan: dict[str, object] | None = None
            if row is None:
                typer.echo("no scans yet")
            else:
                run_id, finished_at, status, generation, disk_filter = row
                disk_scope = f" (disk={disk_filter})" if disk_filter else ""
                typer.echo(
                    f"latest scan: id={run_id}, finished_at={finished_at}, status={status},"
                    f" generation={generation}{disk_scope}"
                )
                latest_scan = {
                    "id": run_id,
                    "finished_at": str(finished_at),
                    "status": status,
                    "generation": generation,
                    "disk_filter": disk_filter,
                }

            # --- Repair queue health ---
            from personalscraper.indexer import repair  # noqa: PLC0415

            oldest_pending_age_seconds, pending_depth = repair.get_queue_health(conn)
            if oldest_pending_age_seconds is None:
                oldest_label = "never"
            else:
                oldest_label = f"{oldest_pending_age_seconds // 3600}h"
            typer.echo(f"repair queue: depth={pending_depth}, oldest={oldest_label}")

            # --- Outbox pending depth ---
            outbox_depth = conn.execute("SELECT COUNT(*) FROM index_outbox WHERE status = 'pending'").fetchone()[0]
            typer.echo(f"outbox pending: {outbox_depth}")

            # --- Deleted items count ---
            deleted_count = conn.execute("SELECT COUNT(*) FROM deleted_item").fetchone()[0]
            typer.echo(f"deleted items: {deleted_count}")

            # --- Enrich-pending count ---
            enrich_pending = conn.execute(
                "SELECT COUNT(*) FROM media_file WHERE enriched_at IS NULL AND deleted_at IS NULL"
            ).fetchone()[0]
            typer.echo(f"enrich pending: {enrich_pending}")

            # --- Category-orphan count (DESIGN §17.2) ---
            known_ids: frozenset[str] = cfg.all_category_ids
            orphan_count: int = 0
            if known_ids:
                placeholders = ",".join("?" * len(known_ids))
                orphan_count = conn.execute(
                    f"SELECT COUNT(*) FROM media_item WHERE category_id NOT IN ({placeholders})",
                    list(known_ids),
                ).fetchone()[0]
            typer.echo(f"category orphans: {orphan_count}")

            # --- Health warnings ---
            unhealthy = False
            if (
                oldest_pending_age_seconds is not None and oldest_pending_age_seconds > 7 * 86400
            ) or pending_depth > 1000:
                typer.echo(
                    f"WARNING: repair queue: depth={pending_depth},"
                    f" oldest pending {(oldest_pending_age_seconds or 0) // 86400} days",
                    err=True,
                )
                unhealthy = True

            if orphan_count > 0:
                typer.echo(
                    f"WARNING: {orphan_count} media_item row(s) with unknown category_id. "
                    "Run 'config migrate-category' to fix.",
                    err=True,
                )
                unhealthy = True

            if output_format == "json":
                import json  # noqa: PLC0415

                status_dict: dict[str, object] = {
                    "disks": disks_data,
                    "latest_scan": latest_scan,
                    "repair_queue": {
                        "depth": pending_depth,
                        "oldest_age_hours": (oldest_pending_age_seconds or 0) // 3600
                        if oldest_pending_age_seconds
                        else None,
                    },
                    "outbox_pending": outbox_depth,
                    "deleted_items": deleted_count,
                    "enrich_pending": enrich_pending,
                    "category_orphans": orphan_count,
                    "healthy": not unhealthy,
                }
                typer.echo(json.dumps(status_dict, default=str, indent=2))
                return 0

            return 1 if unhealthy else 0
    except IndexerCeremonyError:
        return 1


# ---------------------------------------------------------------------------
# library-index
# ---------------------------------------------------------------------------


def library_verify_command(
    *,
    disk: str | None = None,
    budget_seconds: float | None = None,
    no_enqueue: bool = False,
    config_path: Path | None = None,
    event_bus: EventBus,
) -> int:
    """Re-stat every indexed file and escalate mismatches to the repair queue.

    Wraps ``scan(mode='verify')`` for a targeted re-verification pass.  Unlike
    a full rescan, verify mode does NOT soft-delete missing files — it only marks
    them for repair so they can be investigated before any destructive action.

    With ``no_enqueue=True`` the verify pass walks every file and reports
    mismatches but does NOT insert any rows into ``repair_queue`` (read-only
    audit mode).

    Args:
        disk: Optional disk label to restrict verification to a single disk.
        budget_seconds: Maximum wall-clock seconds for the verify pass. ``None``
            means unlimited.  Per-file commit guarantees partial progress is
            preserved when the budget is exhausted; the next invocation
            resumes from rows whose ``last_verified_at`` is older than this run.
        no_enqueue: When ``True``, skip inserting rows into ``repair_queue``
            for detected drift or absent files.
        config_path: Optional explicit path to config.json5 or config directory.
        event_bus: Required :class:`EventBus` forwarded to ``open_db`` + the
            verify-mode scan so disk-circuit and ``DiskFullWarning`` emits
            reach the run's subscriber-wired bus.

    Returns:
        ``0`` on success, ``1`` on infrastructure error, ``2`` on unknown disk.
    """
    import json  # noqa: PLC0415

    from personalscraper.conf.loader import (  # noqa: PLC0415
        ConfigNotFoundError,
        ConfigValidationError,
        load_config,
        resolve_config_path,
    )
    from personalscraper.indexer.commands._ceremony import (  # noqa: PLC0415
        IndexerCeremonyError,
        open_indexer_db,
    )
    from personalscraper.indexer.scanner import (  # noqa: PLC0415
        IndexerConfigError,
        ScanMode,
        filter_disks,
        scan,
    )
    from personalscraper.indexer.schema import DiskRow  # noqa: PLC0415

    log.info("indexer.cli.verify", disk=disk)

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    db_path = cfg.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    try:
        with open_indexer_db(db_path, event_bus=event_bus, writer_lock_timeout=0) as conn:
            conn.row_factory = sqlite3.Row
            raw_rows = conn.execute(
                "SELECT id, uuid, label, mount_path, last_seen_at, merkle_root, "
                "is_mounted, unreachable_strikes FROM disk"
            ).fetchall()
            disks: list[DiskRow] = [
                DiskRow(
                    id=r["id"],
                    uuid=r["uuid"],
                    label=r["label"],
                    mount_path=r["mount_path"],
                    last_seen_at=r["last_seen_at"],
                    merkle_root=r["merkle_root"],
                    is_mounted=r["is_mounted"],
                    unreachable_strikes=r["unreachable_strikes"],
                )
                for r in raw_rows
            ]

            try:
                filtered_disks = filter_disks(disks, disk)
            except IndexerConfigError as exc:
                typer.echo(str(exc), err=True)
                return 2

            gen_row = conn.execute("SELECT MAX(scan_generation) FROM media_file").fetchone()
            next_gen: int = (gen_row[0] or 0) + 1

            result = scan(
                disks=filtered_disks,
                mode=ScanMode.verify,
                generation=next_gen,
                conn=conn,
                disk_filter=disk,
                budget_seconds=budget_seconds,
                merkle_delta_freeze_threshold=cfg.indexer.drift.merkle_delta_freeze_threshold,
                paranoia_window_seconds=cfg.indexer.scan.paranoia_window_seconds,
                no_enqueue=no_enqueue,
                event_bus=event_bus,
            )

            summary = {
                "mode": "verify",
                "no_enqueue": no_enqueue,
                "files_walked": result.files_visited,
                "dirs_walked": result.dirs_visited,
                "disks_skipped": result.disks_skipped,
                "scan_run_id": result.scan_run_id,
                "status": result.status,
            }
            typer.echo(json.dumps(summary))
            return 0
    except IndexerCeremonyError:
        return 1


# ---------------------------------------------------------------------------
# library-search
# ---------------------------------------------------------------------------


def library_search_command(
    query_str: str,
    *,
    limit: int = 50,
    config_path: Path | None = None,
    event_bus: EventBus,
) -> tuple[int, list[dict[str, object]]]:
    """Execute a flex-attr query and return matching media items.

    Delegates to :func:`~personalscraper.indexer.query.execute` for tokenisation,
    SQL compilation, and execution.  Returns a ``(rc, rows)`` tuple where each
    row is a dict with keys ``id``, ``title``, ``year``, ``kind``, ``nfo_status``.

    Args:
        query_str: Query string in the flex-attr syntax, e.g.
            ``"year:2024 disk:Disk1 -nfo:valid"``.
        limit: Maximum number of rows to return.  Defaults to 50.
        config_path: Optional explicit path to config.json5 or config directory.
        event_bus: Required :class:`EventBus` forwarded to ``open_db`` so the
            pre-open free-space guard emits ``DiskFullWarning`` on the run's
            subscriber-wired bus.

    Returns:
        ``(0, rows)`` on success (rows may be empty), ``(1, [])`` on
        infrastructure error, ``(2, [])`` on query syntax / unknown-field error.
    """
    from personalscraper.conf.loader import (  # noqa: PLC0415
        ConfigNotFoundError,
        ConfigValidationError,
        load_config,
        resolve_config_path,
    )
    from personalscraper.indexer.commands._ceremony import (  # noqa: PLC0415
        IndexerCeremonyError,
        open_indexer_db,
    )
    from personalscraper.indexer.query import QueryError, execute  # noqa: PLC0415

    log.info("indexer.cli.search", query=query_str, limit=limit)

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1, []

    db_path = cfg.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    try:
        with open_indexer_db(db_path, event_bus=event_bus) as conn:
            try:
                items = execute(conn, query_str, limit=limit)
            except QueryError as exc:
                typer.echo(str(exc), err=True)
                return 2, []

            rows: list[dict[str, object]] = []
            for item in items:
                rows.append(
                    {
                        "id": item.id,
                        "title": item.title or "",
                        "year": item.year,
                        "kind": item.kind or "",
                        "nfo_status": item.nfo_status or "",
                    }
                )

            return 0, rows
    except IndexerCeremonyError:
        return 1, []


# ---------------------------------------------------------------------------
# library-reconcile
# ---------------------------------------------------------------------------


def library_show_command(
    item_id: int,
    *,
    config_path: Path | None = None,
    event_bus: EventBus,
) -> tuple[int, dict[str, object]]:
    """Return all stored data for a single media item.

    Returns a ``(rc, payload)`` tuple where *payload* has keys:
    ``item`` (dict), ``seasons`` (list), ``files`` (list with ``streams``
    sub-list), ``attributes`` (list), ``deleted_history`` (list).

    Args:
        item_id: PK of the ``media_item`` to display.
        config_path: Optional explicit path to config.json5 or config directory.
        event_bus: Required :class:`EventBus` forwarded to ``open_db`` so the
            pre-open free-space guard emits ``DiskFullWarning`` on the run's
            subscriber-wired bus.

    Returns:
        ``(0, payload)`` on success, ``(1, {})`` on infrastructure error,
        ``(2, {"error": ...})`` if no item with the given id exists.
    """
    from personalscraper.conf.loader import (  # noqa: PLC0415
        ConfigNotFoundError,
        ConfigValidationError,
        load_config,
        resolve_config_path,
    )
    from personalscraper.indexer.commands._ceremony import (  # noqa: PLC0415
        IndexerCeremonyError,
        open_indexer_db,
    )

    log.info("indexer.cli.show", item_id=item_id)

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1, {}

    db_path = cfg.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    try:
        with open_indexer_db(db_path, event_bus=event_bus) as conn:
            conn.row_factory = sqlite3.Row

            # --- Fetch media_item ---
            item_row = conn.execute("SELECT * FROM media_item WHERE id = ?", (item_id,)).fetchone()
            if item_row is None:
                return 2, {"error": f"no item with id {item_id}"}

            item_dict: dict[str, object] = dict(item_row)

            # --- Seasons and episodes (shows) ---
            seasons_raw = conn.execute("SELECT * FROM season WHERE item_id = ? ORDER BY number", (item_id,)).fetchall()
            seasons: list[dict[str, object]] = []
            for s in seasons_raw:
                sd: dict[str, object] = dict(s)
                eps_raw = conn.execute(
                    "SELECT * FROM episode WHERE season_id = ? ORDER BY number", (s["id"],)
                ).fetchall()
                sd["episodes"] = [dict(ep) for ep in eps_raw]
                seasons.append(sd)

            # --- media_file rows ---
            files_raw = conn.execute(
                "SELECT mf.*, p.rel_path, p.disk_id FROM media_file mf "
                "JOIN media_release mr ON mf.release_id = mr.id "
                "JOIN path p ON mf.path_id = p.id "
                "WHERE mr.item_id = ? ORDER BY mf.id",
                (item_id,),
            ).fetchall()
            if not files_raw:
                files_raw = conn.execute(
                    "SELECT mf.*, p.rel_path, p.disk_id FROM media_file mf "
                    "JOIN path p ON mf.path_id = p.id "
                    "WHERE p.disk_id IN (SELECT id FROM disk) "
                    "AND mf.release_id IS NULL "
                    "LIMIT 0"
                ).fetchall()

            files: list[dict[str, object]] = []
            for f in files_raw:
                fd: dict[str, object] = dict(f)
                streams_raw = conn.execute(
                    "SELECT * FROM media_stream WHERE file_id = ? ORDER BY idx",
                    (f["id"],),
                ).fetchall()
                fd["streams"] = [dict(st) for st in streams_raw]
                files.append(fd)

            # --- item_attribute rows ---
            attrs_raw = conn.execute(
                "SELECT key, value FROM item_attribute WHERE item_id = ? ORDER BY key",
                (item_id,),
            ).fetchall()
            attributes: list[dict[str, object]] = [dict(a) for a in attrs_raw]

            # --- deleted_item history ---
            deleted_raw = conn.execute(
                "SELECT * FROM deleted_item WHERE original_id = ? ORDER BY deleted_at",
                (item_id,),
            ).fetchall()
            deleted_history: list[dict[str, object]] = [dict(d) for d in deleted_raw]

            payload: dict[str, object] = {
                "item": item_dict,
                "item_id": item_id,
                "seasons": seasons,
                "files": files,
                "attributes": attributes,
                "deleted_history": deleted_history,
            }
            return 0, payload
    except IndexerCeremonyError:
        return 1, {}


# ---------------------------------------------------------------------------
# config migrate-category
# ---------------------------------------------------------------------------
