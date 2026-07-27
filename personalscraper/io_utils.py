"""Shared filesystem helpers.

Atomic write with directory fsync to survive machine crashes:
the standard tmp+rename pattern still leaves the parent directory
inode unflushed on most filesystems (notably ext4 and macFUSE-mounted
NTFS), so a power loss between write and journal flush can lose the
just-renamed entry.

Also hosts the ``serialize_to_json`` / ``write_json`` / ``read_json``
(de)serialization helpers (moved here in 0.19.0).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast


def _atomic_write_bytes(path: Path, payload: bytes, *, mode: int = 0o644) -> None:
    """Atomically write ``payload`` as bytes to ``path``.

    Writes to ``<path>.tmp``, fsyncs that file, replaces ``path``, then
    fsyncs the parent directory so the rename is durable across crashes.

    Args:
        path: Destination file. Parent directory is created if missing.
        payload: Raw bytes to write.
        mode: Permission bits for the created file. Applied to the temp fd via
            ``fchmod`` BEFORE any payload byte is written — so a restrictive
            ``mode`` (e.g. ``0o600`` for a secrets file) leaves no window where
            the temp, or the freshly-renamed ``path``, is group/other-readable.
            ``fchmod`` also forces the mode even if a stale temp pre-existed at
            looser permissions. Default ``0o644`` preserves prior behaviour.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        if mode != 0o644:
            # A non-default (e.g. secrets 0o600) mode is enforced before any byte
            # is written: os.open honours the umask and would not tighten a
            # pre-existing stale temp — fchmod does both, closing the window. The
            # default 0o644 path skips this so existing callers are byte-for-byte
            # unchanged (no extra syscall on macFUSE/NTFS targets).
            os.fchmod(fd, mode)
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


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8", mode: int = 0o644) -> None:
    """Atomically write ``content`` as text to ``path``.

    Writes to ``<path>.tmp``, fsyncs that file, replaces ``path``, then
    fsyncs the parent directory so the rename is durable across crashes.

    Args:
        path: Destination file. Parent directory is created if missing.
        content: Text payload.
        encoding: Text encoding to use (default ``"utf-8"``).
        mode: Permission bits for the created file (default ``0o644``). Pass
            ``0o600`` for secrets so there is no world-readable window; see
            :func:`_atomic_write_bytes`.
    """
    _atomic_write_bytes(path, content.encode(encoding), mode=mode)


# --- Dataclass JSON serialization helpers ---


def _json_default(obj: object) -> str:
    """JSON encoder fallback for Path and other non-serializable types."""
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def serialize_to_json(obj: object) -> str:
    """Serialize a dataclass instance to JSON string.

    Handles Path objects via custom encoder. Uses dataclasses.asdict()
    for conversion, matching the IndexEntry serialization pattern.

    Args:
        obj: A dataclass instance.

    Returns:
        JSON string with 2-space indentation.
    """
    # mypy: asdict requires DataclassInstance; callers always pass a dataclass instance.
    return json.dumps(asdict(obj), default=_json_default, indent=2, ensure_ascii=False)  # type: ignore[call-overload]


def write_json(obj: object, path: Path) -> None:
    """Atomically write a dataclass to a JSON file.

    Writes to a .tmp file first, then renames to target path.
    Prevents corruption from interrupted writes.

    Args:
        obj: A dataclass instance.
        path: Target file path.
    """
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(serialize_to_json(obj), encoding="utf-8")
    tmp_path.rename(path)


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file and return parsed dict.

    Args:
        path: Path to JSON file.

    Returns:
        Parsed dictionary.
    """
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
