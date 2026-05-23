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


def seed_scan_run(
    conn: sqlite3.Connection,
    status: str = "ok",
    mode: str = "full",
    generation: int = 1,
    disk_filter: str | None = None,
    finished_at: int | None = None,
) -> int:
    """Insert a completed scan_run row and return its id."""
    now = int(time.time())
    conn.execute(
        "INSERT INTO scan_run (generation, mode, disk_filter, started_at, finished_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (generation, mode, disk_filter, now - 60, finished_at or now, status),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_index_outbox(
    conn: sqlite3.Connection,
    status: str = "pending",
    processed_at: int | None = None,
    event_type: str = "test.event",
    source: str = "scanner",
    op: str = "move",
) -> int:
    """Insert an index_outbox row and return its id."""
    now = int(time.time())
    conn.execute(
        "INSERT INTO index_outbox (source, op, payload_json, created_at, processed_at, status) "
        "VALUES (?, ?, '{}', ?, ?, ?)",
        (source, op, now, processed_at, status),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_repair_queue(
    conn: sqlite3.Connection,
    scope: str = "item",
    scope_id: int = 1,
    reason: str = "test.reason",
    status: str = "pending",
) -> int:
    """Insert a repair_queue row and return its id."""
    now = int(time.time())
    conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, payload_json, enqueued_at, status) "
        "VALUES (?, ?, ?, '{}', ?, ?)",
        (scope, scope_id, reason, now, status),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def seed_media_file_on_disk(
    conn: sqlite3.Connection,
    disk_id: int,
    mount_path: Path,
    rel_path: str,
    filename: str,
    size_bytes: int | None = None,
    mtime_ns: int | None = None,
    release_id: int | None = None,
) -> tuple[int, int, int]:
    """Create a real file on disk and seed matching DB rows.

    Creates the directory structure under *mount_path*, writes a file with
    deterministic content, stats it, and inserts ``path`` + ``media_file``
    rows with the actual on-disk values.

    Args:
        conn: Open SQLite connection.
        disk_id: FK to ``disk.id``.
        mount_path: The disk mount path root (must exist).
        rel_path: Relative directory under mount_path.
        filename: Name of the file to create.
        size_bytes: Override stored size (for mismatch tests).  Defaults to
            actual file size.
        mtime_ns: Override stored mtime (for mismatch tests).  Defaults to
            actual file mtime.
        release_id: FK to ``media_release.id``.  When ``None``, a minimal
            media_item + media_release pair is auto-created.

    Returns:
        ``(path_id, file_id, actual_size)`` tuple.
    """
    import hashlib as _hashlib
    import os as _os

    now = int(time.time())

    # Create directory and file.
    dir_path = mount_path / rel_path
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    content = f"test content for {filename} at {now}".encode()
    file_path.write_bytes(content)
    actual_size = _os.stat(file_path).st_size
    actual_mtime_ns = _os.stat(file_path).st_mtime_ns

    # Compute oshash.
    oshash = _hashlib.new("sha1")
    oshash.update(content)
    oshash_hex = oshash.hexdigest()[:16]

    stored_size = size_bytes if size_bytes is not None else actual_size
    stored_mtime = mtime_ns if mtime_ns is not None else actual_mtime_ns

    # Ensure release_id.
    if release_id is None:
        release_id = seed_media_item_with_release(conn)

    # Insert path row.
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns) VALUES (?, ?, ?)",
        (disk_id, rel_path, int(dir_path.stat().st_mtime_ns)),
    )
    path_id: int = cursor.lastrowid  # type: ignore[assignment]

    # Insert media_file row.
    conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, scan_generation, last_verified_at, enriched_at, deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, NULL, NULL)
        """,
        (release_id, path_id, filename, stored_size, stored_mtime, now, oshash_hex, now),
    )
    conn.commit()
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return (path_id, file_id, actual_size)


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
