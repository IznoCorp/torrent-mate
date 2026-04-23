"""Shared filesystem helpers.

Atomic JSON write with directory fsync to survive machine crashes:
the standard tmp+rename pattern still leaves the parent directory
inode unflushed on most filesystems (notably ext4 and macFUSE-mounted
NTFS), so a power loss between write and journal flush can lose the
just-renamed entry.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def atomic_write_json(path: Path, data: Any, *, indent: int | None = 2) -> None:
    """Atomically write ``data`` as JSON to ``path``.

    Writes to ``<path>.tmp``, fsyncs that file, replaces ``path``, then
    fsyncs the parent directory so the rename is durable across crashes.

    Args:
        path: Destination file. Parent directory is created if missing.
        data: JSON-serializable payload.
        indent: ``json.dumps`` indent (None for compact output).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, indent=indent, ensure_ascii=False)

    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)

    os.replace(tmp_path, path)

    # Fsync the parent dir so the rename is durable; ignore on platforms
    # where directory fds are not openable for fsync (rare on POSIX).
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass
