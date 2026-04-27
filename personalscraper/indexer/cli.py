"""CLI command implementations for the media indexer sub-system.

Provides callable functions (not Typer decorators) that are wired into the
top-level :mod:`personalscraper.cli` application.  Each function returns an
integer exit code so it can be tested without invoking Typer machinery.

Commands:
- :func:`library_status_command` — show the latest completed scan run summary.
"""

from __future__ import annotations

import sys
from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("indexer.cli")

# ---------------------------------------------------------------------------
# library-status
# ---------------------------------------------------------------------------


def library_status_command(config_path: Path | None = None) -> int:
    """Print a one-line summary of the latest completed scan run.

    Loads the PersonalScraper config, opens (or creates) the indexer database,
    applies any pending migrations, then queries ``scan_run`` for the most
    recently finished ``'completed'`` row.

    If no completed scan exists the message ``"no scans yet"`` is printed to
    stdout and exit code 0 is returned.

    On any indexer infrastructure error (:class:`~personalscraper.indexer.db.IndexerLockError`,
    :class:`~personalscraper.indexer.db.IndexerCorruptError`,
    :class:`~personalscraper.indexer.db.IndexerDiskFullError`,
    :class:`~personalscraper.indexer.db.IndexerInvalidPathError`,
    :class:`~personalscraper.indexer.db.IndexerMigrationError`) the error
    message is printed to stderr and exit code 1 is returned.

    Args:
        config_path: Optional explicit path to the config file (or config
            directory for v2 split layout).  When ``None`` the standard
            resolution order is used (``$PERSONALSCRAPER_CONFIG``, then
            ``./config.json5``).

    Returns:
        ``0`` on success (even when no scans exist), ``1`` on infrastructure error.
    """
    log.info("indexer.cli.status", config_path=str(config_path) if config_path else None)

    from personalscraper.conf.loader import (  # noqa: PLC0415
        ConfigNotFoundError,
        ConfigValidationError,
        load_config,
        resolve_config_path,
    )
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import (  # noqa: PLC0415
        IndexerCorruptError,
        IndexerDiskFullError,
        IndexerInvalidPathError,
        IndexerLockError,
        IndexerMigrationError,
        apply_migrations,
        open_db,
    )

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    # --- Open DB and apply pending migrations ---
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = open_db(db_path)
        apply_migrations(conn, migrations_dir)
    except (
        IndexerLockError,
        IndexerCorruptError,
        IndexerDiskFullError,
        IndexerInvalidPathError,
        IndexerMigrationError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # --- Query latest successful scan ---
    # The schema CHECK allows: 'running', 'ok', 'failed', 'aborted'.
    # 'ok' is the terminal success status.
    row = conn.execute(
        "SELECT id, finished_at, status FROM scan_run WHERE status = 'ok' ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()

    if row is None:
        print("no scans yet")
        return 0

    run_id, finished_at, status = row
    print(f"latest scan: {run_id}, finished_at={finished_at}, status={status}")
    return 0
