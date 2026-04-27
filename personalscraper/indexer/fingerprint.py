"""Fingerprinting utilities for the media indexer.

Provides three tiers of file identity:

* **Tier 1** — ``(size, mtime_ns, ctime_ns)`` read directly from a ``stat`` result.
  Fast, zero I/O beyond the ``stat`` call already performed by the scanner walk.
* **OSHash** — OpenSubtitles content hash: ``(filesize + sum(first 64 KiB as u64LE)
  + sum(last 64 KiB as u64LE)) mod 2^64``.  Survives renames; 128 KiB read per file.
* **xxh3_partial** — ``xxh3_64(first N bytes || last N bytes)``.  Used as a
  fast drift-detection fallback when tier-1 is racy or contradictory.

Racy-mtime detection follows the git racy-index rule: a file whose mtime falls
within the scan window (or in the future) is considered *racy* and escalated to
tier-2 fingerprinting.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

import xxhash

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Video-file extensions eligible for OSHash computation (lowercase, no dot).
#: Sidecars (.nfo, .srt, .jpg, …) are deliberately excluded to avoid 128 KiB
#: reads on thousands of small files during a cold scan.  See DESIGN §11.6.
OSHASH_EXTENSIONS: frozenset[str] = frozenset(
    {
        "mkv",
        "mp4",
        "avi",
        "mov",
        "wmv",
        "flv",
        "mpg",
        "mpeg",
        "m4v",
        "webm",
        "ts",
        "m2ts",
        "mts",
        "3gp",
        "vob",
        "ogv",
        "rmvb",
    }
)

# OSHash reads exactly 64 KiB from the head and 64 KiB from the tail.
_OSHASH_CHUNK: int = 65536  # 64 KiB
_U64_COUNT: int = _OSHASH_CHUNK // 8  # 8192 uint64 values per chunk
_U64_MOD: int = 1 << 64  # 2^64  — hash wraps mod 2^64


# ---------------------------------------------------------------------------
# Tier-1 fingerprint
# ---------------------------------------------------------------------------


def fingerprint_tier1(stat: os.stat_result) -> tuple[int, int, int]:
    """Return a lightweight ``(size, mtime_ns, ctime_ns)`` fingerprint.

    Reads directly from an ``os.stat_result`` object — no additional I/O
    beyond the ``stat`` call the caller already performed.

    Args:
        stat: A ``stat_result`` as returned by ``os.stat()``,
            ``os.lstat()``, or ``os.scandir()`` entry methods.

    Returns:
        A 3-tuple ``(st_size, st_mtime_ns, st_ctime_ns)``.
    """
    return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


# ---------------------------------------------------------------------------
# Racy-mtime detection
# ---------------------------------------------------------------------------


def is_racy(file_mtime_ns: int, scan_started_at_ns: int, window_ns: int) -> bool:
    """Detect a racy mtime using the git racy-index escalation rule.

    A file is *racy* if its mtime falls within the racy window before the scan
    start, **or** if it is in the future relative to the scan start (clock
    skew protection).  Formally: ``file_mtime_ns >= (scan_started_at_ns - window_ns)``.

    The window boundary is **inclusive** — a file whose mtime equals
    ``scan_started_at_ns - window_ns`` is considered racy.

    Args:
        file_mtime_ns: File modification time in nanoseconds (``st_mtime_ns``).
        scan_started_at_ns: Timestamp when the scan started, in nanoseconds
            (typically ``time.time_ns()`` captured before the walk begins).
        window_ns: Racy window width in nanoseconds.  A common default is
            ``2_000_000_000`` (2 seconds), matching git's heuristic.

    Returns:
        ``True`` if the file should be treated as racy (escalate to tier-2
        fingerprinting); ``False`` if tier-1 alone is trustworthy.
    """
    return file_mtime_ns >= (scan_started_at_ns - window_ns)


# ---------------------------------------------------------------------------
# OSHash
# ---------------------------------------------------------------------------


def oshash(path: Path) -> str:
    """Compute the OpenSubtitles hash for a media file.

    Algorithm:
        ``hash = (filesize + sum_head_u64 + sum_tail_u64) mod 2^64``

    where ``sum_head_u64`` is the sum of the first 65 536 bytes interpreted as
    8 192 little-endian ``uint64`` values, and ``sum_tail_u64`` is the same
    for the last 65 536 bytes.

    Files smaller than 65 536 bytes are treated as *both* head and tail,
    zero-padded to 65 536 bytes each.  This double-counts the content for
    small files, which is the canonical OpenSubtitles specification behaviour.

    Files smaller than 128 KiB but larger than 65 536 bytes have overlapping
    head/tail reads — the overlap is correct per spec.

    Args:
        path: Absolute or relative path to the file.

    Returns:
        A 16-character lowercase hex string representing the ``uint64`` hash.

    Raises:
        OSError: If the file cannot be opened or read.
    """
    filesize: int = path.stat().st_size

    if filesize == 0:
        return "0000000000000000"

    # --- read head chunk ---
    fd: int = os.open(path, os.O_RDONLY)
    try:
        head_raw: bytes = os.read(fd, _OSHASH_CHUNK)
        # Pad with zero bytes if file is shorter than one chunk.
        if len(head_raw) < _OSHASH_CHUNK:
            head_raw = head_raw + b"\x00" * (_OSHASH_CHUNK - len(head_raw))

        # --- read tail chunk ---
        tail_offset: int = max(0, filesize - _OSHASH_CHUNK)
        os.lseek(fd, tail_offset, os.SEEK_SET)
        tail_raw: bytes = os.read(fd, _OSHASH_CHUNK)
        if len(tail_raw) < _OSHASH_CHUNK:
            tail_raw = tail_raw + b"\x00" * (_OSHASH_CHUNK - len(tail_raw))
    finally:
        os.close(fd)

    # --- sum chunks as little-endian uint64 values ---
    sum_head: int = sum(struct.unpack_from("<Q", head_raw, i * 8)[0] for i in range(_U64_COUNT))
    sum_tail: int = sum(struct.unpack_from("<Q", tail_raw, i * 8)[0] for i in range(_U64_COUNT))

    hash_value: int = (filesize + sum_head + sum_tail) % _U64_MOD
    return f"{hash_value:016x}"


# ---------------------------------------------------------------------------
# xxh3_partial
# ---------------------------------------------------------------------------


def xxh3_partial(path: Path, partial_bytes: int = 1_048_576) -> str:
    """Compute an ``xxh3_64`` hash over the first and last *N* bytes of a file.

    Used as a fast drift-detection fallback when tier-1 fingerprinting is racy
    or contradictory.  The read cost is at most ``2 * partial_bytes`` (2 MiB
    by default), making it far cheaper than hashing the full file.

    For files smaller than ``2 * partial_bytes``, the entire file content is
    hashed (no double-reading).

    Args:
        path: Path to the file.
        partial_bytes: Number of bytes to read from each end.  Defaults to
            1 048 576 (1 MiB).

    Returns:
        A 16-character lowercase hex string representing the ``xxh3_64`` digest.

    Raises:
        OSError: If the file cannot be opened or read.
    """
    filesize: int = path.stat().st_size
    hasher = xxhash.xxh3_64()

    fd: int = os.open(path, os.O_RDONLY)
    try:
        if filesize <= 2 * partial_bytes:
            # File fits entirely — hash the whole thing in one pass.
            data: bytes = os.read(fd, filesize)
            hasher.update(data)
        else:
            # Hash first N bytes.
            head: bytes = os.read(fd, partial_bytes)
            hasher.update(head)
            # Hash last N bytes.
            os.lseek(fd, filesize - partial_bytes, os.SEEK_SET)
            tail: bytes = os.read(fd, partial_bytes)
            hasher.update(tail)
    finally:
        os.close(fd)

    return f"{hasher.intdigest():016x}"
