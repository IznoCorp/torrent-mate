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

from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer._macos_io import disable_cache
from personalscraper.indexer._throttle import acquire as _acquire_read_tokens

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
# FS-aware tier-1 normalisation (Phase 5)
# ---------------------------------------------------------------------------


def round_mtime_ns(mtime_ns: int, capability: FilesystemCapability = NTFS_MACFUSE) -> int:
    """Floor an mtime to the capability's granularity bucket.

    The default *capability* is ``NTFS_MACFUSE`` (granularity 1), so an
    un-threaded caller gets the identity transform — the value is returned
    unchanged.  Only filesystems with a coarser timestamp resolution (HFS+ 1 s,
    exFAT 2 s) actually bucket the mtime.

    Args:
        mtime_ns: Raw ``st_mtime_ns``.
        capability: Filesystem capability (provides ``mtime_granularity_ns``).
            Defaults to ``NTFS_MACFUSE`` so omitting it is a no-op.

    Returns:
        ``mtime_ns`` unchanged when granularity is 1 (NTFS/APFS/ext4); otherwise
        floored to the nearest ``mtime_granularity_ns`` bucket (HFS+ 1 s,
        exFAT 2 s).
    """
    gran = capability.mtime_granularity_ns
    return (mtime_ns // gran) * gran if gran > 1 else mtime_ns


def normalize_tier1(
    size: int,
    mtime_ns: int,
    ctime_ns: int,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> tuple[int, ...]:
    """Capability-aware tier-1 fingerprint used for drift comparison.

    For ``ntfs_macfuse`` (and APFS/ext4: granularity=1, ctime=True) this returns
    ``(size, mtime_ns, ctime_ns)`` — byte-identical to the legacy inline tuples,
    so the NTFS scan path is unchanged.  exFAT drops ctime (unreliable) and
    rounds mtime to 2 s; HFS+ keeps ctime but rounds mtime to 1 s.

    The default *capability* is ``NTFS_MACFUSE`` so any call site not yet
    threaded behaves exactly like the legacy tuple.

    Args:
        size: ``st_size``.
        mtime_ns: Raw ``st_mtime_ns``.
        ctime_ns: Raw ``st_ctime_ns`` (caller passes ``stored.ctime_ns or 0``).
        capability: Filesystem capability for the disk being scanned.  Defaults
            to ``NTFS_MACFUSE`` (legacy 3-tuple, no rounding).

    Returns:
        A 3-tuple ``(size, mtime_bucket, ctime_ns)`` when the FS has reliable
        ctime, else a 2-tuple ``(size, mtime_bucket)``.
    """
    m = round_mtime_ns(mtime_ns, capability)
    if capability.tier1_uses_ctime:
        return (size, m, ctime_ns)
    return (size, m)


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
    # Bypass the UBC for this fd: OSHash reads 128 KiB total (head + tail),
    # hashes them, and never re-reads the file in this session.  The page
    # cache contributes nothing after the read — disable it to avoid polluting
    # the UBC during cold scans of tens of thousands of video files.
    # See audit/13-ntfs-cache-pressure.md §Cause-2 and §Phase-B.
    fd: int = os.open(path, os.O_RDONLY)
    try:
        disable_cache(fd)
        # Throttle: acquire tokens before each read chunk.  In passthrough
        # mode (no active bucket / unlimited rate) these calls are no-ops.
        _acquire_read_tokens(_OSHASH_CHUNK)
        head_raw: bytes = os.read(fd, _OSHASH_CHUNK)
        # Pad with zero bytes if file is shorter than one chunk.
        if len(head_raw) < _OSHASH_CHUNK:
            head_raw = head_raw + b"\x00" * (_OSHASH_CHUNK - len(head_raw))

        # --- read tail chunk ---
        tail_offset: int = max(0, filesize - _OSHASH_CHUNK)
        os.lseek(fd, tail_offset, os.SEEK_SET)
        _acquire_read_tokens(_OSHASH_CHUNK)
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

    # Bypass the UBC for this fd: xxh3_partial reads at most 2 MiB (head +
    # tail), hashes them once, and never re-reads the file in this session.
    # See audit/13-ntfs-cache-pressure.md §Cause-2 and §Phase-B.
    fd: int = os.open(path, os.O_RDONLY)
    try:
        disable_cache(fd)
        if filesize <= 2 * partial_bytes:
            # File fits entirely — hash the whole thing in one pass.
            _acquire_read_tokens(filesize)
            data: bytes = os.read(fd, filesize)
            hasher.update(data)
        else:
            # Hash first N bytes.
            _acquire_read_tokens(partial_bytes)
            head: bytes = os.read(fd, partial_bytes)
            hasher.update(head)
            # Hash last N bytes.
            os.lseek(fd, filesize - partial_bytes, os.SEEK_SET)
            _acquire_read_tokens(partial_bytes)
            tail: bytes = os.read(fd, partial_bytes)
            hasher.update(tail)
    finally:
        os.close(fd)

    return f"{hasher.intdigest():016x}"
