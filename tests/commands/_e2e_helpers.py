"""Shared E2E helpers for library-* command tests.

Centralized to avoid copy-paste in 25+ test files.
Each helper is importable by individual _e2e.py files without pulling in
transitive test dependencies (Typer CliRunner, pytest fixtures, etc.).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from personalscraper.conf.models.config import Config


def make_synthetic_db(tmp_path: Path) -> Path:
    """Create a fully-migrated DB in tmp_path/library.db. Return the path."""
    from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

    db_path = tmp_path / "test_indexer.db"
    migrations_dir = Path(_migrations_pkg.__file__).parent
    conn = open_db(db_path, event_bus=EventBus())
    apply_migrations(conn, migrations_dir)
    conn.commit()
    conn.close()
    return db_path


def make_test_config_with_db(test_config: Config, db_path: Path) -> Config:
    """Return a copy of *test_config* with ``indexer.db_path`` pointed at *db_path*."""
    return test_config.model_copy(
        update={"indexer": test_config.indexer.model_copy(update={"db_path": db_path})}
    )


def seed_disk(conn: sqlite3.Connection, label: str, mount_path: Path) -> int:
    """Insert a mounted disk row and return its id."""
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        (f"uuid-{label}", label, str(mount_path), now),
    )
    conn.commit()
    return cursor.lastrowid


def seed_phantom_path(
    conn: sqlite3.Connection,
    disk_id: int,
    rel_path: str,
    n_files: int = 3,
) -> int:
    """Seed a path row whose absolute path doesn't exist + *n_files* media_files under it.

    Returns the path_id.  ``detect_path_missing`` will flag it because
    ``mount_path / rel_path`` does not exist on the filesystem.
    """
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, 0)",
        (disk_id, rel_path),
    )
    path_id: int = cursor.lastrowid  # type: ignore[assignment]
    for i in range(n_files):
        conn.execute(
            """
            INSERT INTO media_file (
                release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
                oshash, enriched_at, scan_generation, last_verified_at, deleted_at
            ) VALUES (NULL, ?, ?, 1000, 1700000000000000000, 1700000000000000000,
                      NULL, NULL, 1, ?, NULL)
            """,
            (path_id, f"file_{i}.mkv", now),
        )
    conn.commit()
    return path_id


def seed_media_item_with_release(
    conn: sqlite3.Connection,
    title: str = "Test Movie",
    category_id: str = "movies",
) -> int:
    """Insert a minimal media_item + media_release pair and return the release_id."""
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
        "VALUES ('movie', ?, ?, ?, ?, ?)",
        (title, title, category_id, now, now),
    )
    item_id: int = cursor.lastrowid  # type: ignore[assignment]
    cursor2 = conn.execute(
        "INSERT INTO media_release (item_id, edition) VALUES (?, 'Standard')",
        (item_id,),
    )
    conn.commit()
    return cursor2.lastrowid  # type: ignore[return-value]


def run_cli(args: list[str]) -> Any:
    """Invoke the Typer CLI app via CliRunner and return the result object.

    Args:
        args: CLI arguments as a list of strings (e.g. ``['library-reconcile', '--format', 'json']``).

    Returns:
        The ``Result`` object from ``CliRunner.invoke``.
    """
    from personalscraper.cli import app  # noqa: PLC0415

    runner = CliRunner()
    return runner.invoke(app, args)


def json_from_result(result: Any) -> dict[str, Any]:
    """Extract a JSON dict from CliRunner result output.

    Handles Rich-formatted output where JSON may be interleaved with
    escape codes.  Returns the first JSON object found.
    """
    raw: str = result.output.strip()
    # Strip Rich ANSI escape codes.
    import re

    clean = re.sub(r"\x1b\[[0-9;]*m", "", raw)
    start = clean.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in output: {raw!r}")
    return json.loads(clean[start:])  # type: ignore[no-any-return]
