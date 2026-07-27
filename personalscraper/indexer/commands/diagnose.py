"""Diagnostic and maintenance indexer command functions."""

from __future__ import annotations

from pathlib import Path

import typer

from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

log = get_logger("indexer.cli")


def config_migrate_category_command(
    *,
    from_category: str,
    to_category: str,
    config_path: Path | None = None,
    event_bus: EventBus,
) -> int:
    """Rewrite every ``media_item.category_id`` from *from_category* to *to_category*.

    Run this after renaming a category in ``categories.json5`` to clear orphan-tagged
    rows detected by ``library status``.  The command is idempotent: running twice
    with the same args is a no-op the second time.

    The operation is:

    1. Verify ``to_category`` is a declared category id in ``Config.all_category_ids``
       (i.e. the rename has already been applied to the config).  Exit 2 if not.
    2. Issue ``UPDATE media_item SET category_id = ? WHERE category_id = ?`` inside
       a single transaction.
    3. Print the number of rows updated.

    Args:
        from_category: The old category_id string to replace (may or may not still
            be in the config — it is the source of the orphan rows).
        to_category: The new category_id string to write.  Must be a declared id
            in the current config.
        config_path: Optional explicit path to config.json5 or config directory.
        event_bus: Required :class:`EventBus` forwarded to ``open_db`` so the
            pre-open free-space guard emits ``DiskFullWarning`` on the run's
            subscriber-wired bus.

    Returns:
        ``0`` on success (including no-op when zero rows matched), ``1`` on
        infrastructure error, ``2`` when ``to_category`` is not a declared id.
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

    log.info(
        "indexer.cli.migrate_category",
        from_category=from_category,
        to_category=to_category,
    )

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    # --- Validate to_category is a declared id ---
    known_ids: frozenset[str] = cfg.all_category_ids
    if to_category not in known_ids:
        known_sorted = ", ".join(sorted(known_ids))
        typer.echo(
            f"unknown category '{to_category}'; declared ids: {known_sorted}",
            err=True,
        )
        return 2

    db_path = cfg.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    try:
        with open_indexer_db(db_path, event_bus=event_bus) as conn:
            # --- Execute the migration in a transaction ---
            conn.execute("BEGIN")
            try:
                cur = conn.execute(
                    "UPDATE media_item SET category_id = ? WHERE category_id = ?",
                    (to_category, from_category),
                )
                updated = cur.rowcount
                conn.execute("COMMIT")
            except Exception as exc:  # noqa: BLE001
                conn.execute("ROLLBACK")
                typer.echo(f"migration failed: {exc}", err=True)
                return 1

            if updated == 0:
                typer.echo(f"no rows matched category_id='{from_category}' (already migrated or no such rows)")
            else:
                typer.echo(f"updated {updated} media_item row(s): '{from_category}' → '{to_category}'")

            return 0
    except IndexerCeremonyError:
        return 1
