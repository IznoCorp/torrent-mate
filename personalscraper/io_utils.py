"""Shared filesystem helpers.

Atomic write with directory fsync to survive machine crashes:
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


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Atomically write ``payload`` as bytes to ``path``.

    Writes to ``<path>.tmp``, fsyncs that file, replaces ``path``, then
    fsyncs the parent directory so the rename is durable across crashes.

    Args:
        path: Destination file. Parent directory is created if missing.
        payload: Raw bytes to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, payload)
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


def atomic_write_json(path: Path, data: Any, *, indent: int | None = 2) -> None:
    """Atomically write ``data`` as JSON to ``path``.

    Writes to ``<path>.tmp``, fsyncs that file, replaces ``path``, then
    fsyncs the parent directory so the rename is durable across crashes.

    Args:
        path: Destination file. Parent directory is created if missing.
        data: JSON-serializable payload.
        indent: ``json.dumps`` indent (None for compact output).
    """
    payload = json.dumps(data, indent=indent, ensure_ascii=False)
    _atomic_write_bytes(path, payload.encode("utf-8"))


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Atomically write ``content`` as text to ``path``.

    Writes to ``<path>.tmp``, fsyncs that file, replaces ``path``, then
    fsyncs the parent directory so the rename is durable across crashes.

    Args:
        path: Destination file. Parent directory is created if missing.
        content: Text payload.
        encoding: Text encoding to use (default ``"utf-8"``).
    """
    _atomic_write_bytes(path, content.encode(encoding))
